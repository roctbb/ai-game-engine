import secrets
import shlex
from datetime import timedelta
from io import BytesIO
import tarfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from execution.infrastructure.remote_workers import (
    SqlAlchemyRemoteWorkerRepository,
    RemoteWorkerCredentialOrm,
)
from shared.kernel import utc_now
from test_lobby_duels import fixture_lobby

BASE = "/api/v1/worker/v1"


def admin_headers(client):
    session = client.post(
        "/api/v1/auth/dev-login", json={"nickname": "runner-admin", "role": "admin"}
    ).json()
    return {"X-Session-Id": session["session_id"]}


def add_node(client, *, slots=1):
    response = client.post(
        "/api/v1/workers/external",
        headers=admin_headers(client),
        json={"name": "External test machine", "slots": slots, "labels": {"pool": "external"}},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    key = next(
        item.split("=", 1)[1]
        for item in shlex.split(result["command"])
        if item.startswith("ENROLLMENT_KEY=")
    )
    token = "worker." + result["worker"]["worker_id"] + "." + secrets.token_urlsafe(32)
    headers = {"Authorization": "Bearer " + token}
    return result, key, token, headers


def enroll(client, key, token):
    return client.post(BASE + "/enroll", json={"enrollment_key": key, "token": token})


class Queue:
    def __init__(self):
        self.pending = []
        self.leases = {}
        self.generation = 0
        self.pull_payloads = []

    def schedule_run(self, run_id, required_worker_labels=None):
        self.pending.append(run_id)

    def worker_request(self, operation, data):
        if operation == "pull":
            self.pull_payloads.append(data)
            if (
                not self.pending
                or sum(lease[0] == data["worker_id"] for lease in self.leases.values())
                >= data["max_slots"]
            ):
                return {"run_id": None, "status": "empty"}
            run_id = self.pending.pop(0)
            self.generation += 1
            lease = "lease-" + str(self.generation)
            self.leases[run_id] = (data["worker_id"], lease)
            return {
                "run_id": run_id,
                "lease_id": lease,
                "lease_generation": self.generation,
                "lease_ttl_seconds": 90,
                "status": "assigned",
            }
        valid = self.leases.get(data["run_id"]) == (data["worker_id"], data["lease_id"])
        if operation == "renew":
            return {"renewed": valid}
        if valid:
            del self.leases[data["run_id"]]
        return {"status": "acknowledged" if valid else "stale_lease_ignored"}


def test_admin_only_and_one_time_enrollment_with_durable_retry(client, container, teacher_headers):
    assert (
        client.post(
            "/api/v1/workers/external", headers=teacher_headers, json={"name": "no"}
        ).status_code
        == 403
    )
    result, key, token, headers = add_node(client)
    assert result["worker"]["status"] == "offline"
    assert result["worker"]["token_status"] == "pending"
    assert enroll(client, key, token).status_code == 200
    assert enroll(client, key, token).status_code == 200  # Lost reply: same proposed token.
    assert enroll(client, key, token[:-1] + ("A" if token[-1] != "A" else "B")).status_code == 401
    assert client.post(BASE + "/register", headers=headers).status_code == 200
    disabled = client.patch(
        f"/api/v1/workers/{result['worker']['worker_id']}/status",
        headers=admin_headers(client),
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert client.post(BASE + "/register", headers=headers).json()["status"] == "disabled"
    assert client.post(BASE + "/pull-next", headers=headers, json={}).json()["status"] == "paused"
    client.patch(
        f"/api/v1/workers/{result['worker']['worker_id']}/status",
        headers=admin_headers(client),
        json={"status": "online"},
    )
    listing = client.get("/api/v1/workers", headers=admin_headers(client))
    assert (
        key not in listing.text and token not in listing.text and "token_hash" not in listing.text
    )
    assert listing.json()[0]["token_status"] == "active"
    credential = container.remote_workers.repository.get(result["worker"]["worker_id"])
    assert credential.token_hash != token and credential.enrollment_hash != key
    # The separate bearer token cannot be used on shared internal endpoints or as an admin session.
    assert (
        client.get(
            "/api/v1/internal/workers", headers={**headers, "X-Test-No-Internal-Token": "1"}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/workers", headers=headers).status_code == 403
    assert client.post(BASE + "/register").status_code == 401


def test_expiry_revocation_rotation_and_sql_persistence(client, container):
    result, key, token, headers = add_node(client)
    worker_id = result["worker"]["worker_id"]
    repository = container.remote_workers.repository
    with repository.mutate(worker_id) as credential:
        credential.enrollment_expires_at = utc_now() - timedelta(seconds=1)
    assert enroll(client, key, token).status_code == 401
    fresh = client.post(
        f"/api/v1/workers/{worker_id}/connection", headers=admin_headers(client)
    ).json()
    fresh_key = next(
        item.split("=", 1)[1]
        for item in shlex.split(fresh["command"])
        if item.startswith("ENROLLMENT_KEY=")
    )
    assert enroll(client, fresh_key, token).status_code == 200
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    RemoteWorkerCredentialOrm.__table__.create(engine)
    sql = SqlAlchemyRemoteWorkerRepository(sessionmaker(engine))
    sql.save(repository.get(worker_id))
    container.remote_workers.repository = sql
    assert client.post(BASE + "/register", headers=headers).status_code == 200
    response = client.post(f"/api/v1/workers/{worker_id}/revoke", headers=admin_headers(client))
    assert response.status_code == 200 and response.json()["token_status"] == "revoked"
    assert client.post(BASE + "/register", headers=headers).status_code == 401
    assert enroll(client, fresh_key, token).status_code == 401
    assert sql.get(worker_id).revoked_at is not None


def test_scoped_match_lifecycle_result_retry_and_foreign_access(client, container, teacher_headers):
    queue = Queue()
    container.scheduler = container.execution._scheduler_gateway = queue
    lobby, teams, students = fixture_lobby(client, teacher_headers, count=2)
    ids = container.training_lobby.create_duel(lobby, "duel-0", teams[1])
    result, key, token, headers = add_node(client)
    assert enroll(client, key, token).status_code == 200
    other, other_key, other_token, other_headers = add_node(client)
    assert enroll(client, other_key, other_token).status_code == 200
    assert (
        client.get(BASE + f"/runs/{ids[0]}/execution-context", headers=headers).status_code == 403
    )
    pulled = client.post(
        BASE + "/pull-next", headers=headers, json={"worker_id": other["worker"]["worker_id"]}
    )
    assert pulled.status_code == 200, pulled.text
    lease = pulled.json()
    own = {**headers, "X-Lease-Id": lease["lease_id"]}
    assert queue.pull_payloads[-1]["worker_id"] == result["worker"]["worker_id"]
    assert queue.pull_payloads[-1]["worker_labels"] == {"pool": "external"}
    assert client.post(BASE + "/pull-next", headers=headers, json={}).json()["run_id"] is None
    assert client.get(BASE + f"/runs/{ids[0]}/execution-context", headers=own).status_code == 200
    assert client.get(BASE + f"/runs/{ids[0]}/package", headers=own).status_code == 200
    assert (
        client.get(
            BASE + f"/runs/{ids[0]}/execution-context",
            headers={**other_headers, "X-Lease-Id": lease["lease_id"]},
        ).status_code
        == 403
    )
    assert client.get(BASE + f"/runs/{ids[1]}/execution-context", headers=own).status_code == 403
    assert client.post(BASE + f"/runs/{ids[0]}/started", headers=own).status_code == 200
    payload = {
        "status": "finished",
        "scores": {team: 0.5 for team in teams},
        "placements": {team: 1 for team in teams},
        "metrics": {"draw": True},
        "frames": [{"tick": 0, "frame": {}}],
    }
    bad = {**payload, "scores": {"foreign-team": 1}}
    assert (
        client.post(
            BASE + f"/runs/{ids[0]}/finished",
            headers=own,
            json={"payload": bad, "lease_id": lease["lease_id"]},
        ).status_code
        == 422
    )
    paused = client.patch(
        f"/api/v1/workers/{result['worker']['worker_id']}/status",
        headers=admin_headers(client),
        json={"status": "draining"},
    )
    assert paused.status_code == 200
    assert client.post(BASE + "/pull-next", headers=headers, json={}).json()["status"] == "paused"
    finished = client.post(
        BASE + f"/runs/{ids[0]}/finished",
        headers=own,
        json={"payload": payload, "lease_id": lease["lease_id"]},
    )
    assert finished.status_code == 200, finished.text
    changed = {**payload, "scores": {team: 99 for team in teams}}
    assert (
        client.post(
            BASE + f"/runs/{ids[0]}/finished",
            headers=own,
            json={"payload": changed, "lease_id": lease["lease_id"]},
        ).status_code
        == 200
    )
    assert container.execution.get_run(ids[0]).result_payload["scores"] == payload["scores"]
    ack = {"run_id": ids[0], "lease_id": lease["lease_id"]}
    assert client.post(BASE + "/ack-finished", headers=headers, json=ack).status_code == 200
    assert client.post(BASE + "/ack-finished", headers=headers, json=ack).status_code == 200
    stats = container.training_lobby.get_live_view(lobby, "duel-0").participant_stats
    assert all(item.matches_total == 1 and item.draws == 1 for item in stats)


def test_expired_lease_is_fenced_and_reassigned(client, container, teacher_headers):
    queue = Queue()
    container.scheduler = container.execution._scheduler_gateway = queue
    lobby, teams, _ = fixture_lobby(client, teacher_headers, count=2)
    ids = container.training_lobby.create_duel(lobby, "duel-0", teams[1])
    nodes = [add_node(client) for _ in range(2)]
    for _, key, token, _ in nodes:
        assert enroll(client, key, token).status_code == 200
    lease1 = client.post(BASE + "/pull-next", headers=nodes[0][3], json={}).json()
    h1 = {**nodes[0][3], "X-Lease-Id": lease1["lease_id"]}
    assert client.post(BASE + f"/runs/{ids[0]}/started", headers=h1).status_code == 200
    queue.leases.clear()
    assert client.get(BASE + f"/runs/{ids[0]}/package", headers=h1).status_code == 422
    queue.pending.append(ids[0])
    lease2 = client.post(BASE + "/pull-next", headers=nodes[1][3], json={})
    assert lease2.status_code == 200, lease2.text
    assert lease2.json()["lease_generation"] > lease1["lease_generation"]
    assert (
        client.post(
            BASE + f"/runs/{ids[0]}/started",
            headers={**nodes[1][3], "X-Lease-Id": lease2.json()["lease_id"]},
        ).status_code
        == 200
    )
    assert client.get(BASE + f"/runs/{ids[0]}/package", headers=h1).status_code == 403


def test_distribution_is_a_real_build_context(client):
    result, _, _, _ = add_node(client)
    context_url = next(item for item in shlex.split(result["command"]) if item.endswith(".tar.gz"))
    from urllib.parse import urlparse

    response = client.get(urlparse(context_url).path)
    assert response.status_code == 200
    with tarfile.open(fileobj=BytesIO(response.content), mode="r:gz") as archive:
        names = set(archive.getnames())
        assert "Dockerfile" in names
        assert "services/worker/src/worker_service/remote.py" in names
        assert not any(".env" in name or "tests/" in name for name in names)
        assert "COPY games" not in archive.extractfile("Dockerfile").read().decode()
