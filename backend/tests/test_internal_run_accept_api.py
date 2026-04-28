def _create_queued_single_task_run(client, requested_by: str) -> dict:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": f"Accept Team {requested_by}",
            "captain_user_id": requested_by,
        },
    ).json()
    put_code = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={
            "actor_user_id": requested_by,
            "code": "def make_move(state):\n    return 'right'\n",
        },
    )
    assert put_code.status_code == 200, put_code.json()

    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": requested_by,
            "run_kind": "single_task",
        },
    ).json()
    queued = client.post(f"/api/v1/runs/{run['run_id']}/queue")
    assert queued.status_code == 200, queued.json()
    return queued.json()


def _register_worker(client, worker_id: str) -> None:
    response = client.post(
        "/api/v1/internal/workers/register",
        json={
            "worker_id": worker_id,
            "hostname": f"{worker_id}.local",
            "capacity_total": 1,
            "labels": {},
        },
    )
    assert response.status_code == 200, response.json()


def test_internal_run_accepted_assigns_worker_without_start(client) -> None:
    queued = _create_queued_single_task_run(client, requested_by="captain-accept-1")
    _register_worker(client, "worker-accept-1")

    accepted = client.post(
        f"/api/v1/internal/runs/{queued['run_id']}/accepted",
        json={"worker_id": "worker-accept-1", "lease_id": "lease-accept-1"},
    )

    assert accepted.status_code == 200, accepted.json()
    payload = accepted.json()
    assert payload["status"] == "queued"
    assert payload["worker_id"] == "worker-accept-1"


def test_internal_lifecycle_requires_internal_token(client) -> None:
    queued = _create_queued_single_task_run(client, requested_by="captain-accept-token")
    _register_worker(client, "worker-accept-token")

    response = client.post(
        f"/api/v1/internal/runs/{queued['run_id']}/accepted",
        json={"worker_id": "worker-accept-token", "lease_id": "lease-token"},
        headers={"X-Test-No-Internal-Token": "1"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_internal_run_accepted_reassigns_queued_run_to_new_lease(client) -> None:
    queued = _create_queued_single_task_run(client, requested_by="captain-accept-2")
    _register_worker(client, "worker-accept-2a")
    _register_worker(client, "worker-accept-2b")

    first = client.post(
        f"/api/v1/internal/runs/{queued['run_id']}/accepted",
        json={"worker_id": "worker-accept-2a", "lease_id": "lease-2a"},
    )
    assert first.status_code == 200, first.json()

    second = client.post(
        f"/api/v1/internal/runs/{queued['run_id']}/accepted",
        json={"worker_id": "worker-accept-2b", "lease_id": "lease-2b"},
    )
    assert second.status_code == 200
    assert second.json()["worker_id"] == "worker-accept-2b"

    stale_start = client.post(
        f"/api/v1/internal/runs/{queued['run_id']}/started",
        json={"worker_id": "worker-accept-2a", "lease_id": "lease-2a"},
    )
    assert stale_start.status_code == 422
    assert stale_start.json()["error"]["code"] == "invariant_violation"


def test_internal_run_started_is_idempotent_for_same_worker(client) -> None:
    queued = _create_queued_single_task_run(client, requested_by="captain-accept-3")
    _register_worker(client, "worker-accept-3")

    accepted = client.post(
        f"/api/v1/internal/runs/{queued['run_id']}/accepted",
        json={"worker_id": "worker-accept-3", "lease_id": "lease-3"},
    )
    assert accepted.status_code == 200, accepted.json()

    started_once = client.post(
        f"/api/v1/internal/runs/{queued['run_id']}/started",
        json={"worker_id": "worker-accept-3", "lease_id": "lease-3"},
    )
    assert started_once.status_code == 200, started_once.json()
    assert started_once.json()["status"] == "running"

    started_twice = client.post(
        f"/api/v1/internal/runs/{queued['run_id']}/started",
        json={"worker_id": "worker-accept-3", "lease_id": "lease-3"},
    )
    assert started_twice.status_code == 200, started_twice.json()
    assert started_twice.json()["status"] == "running"


def test_internal_run_accepted_rejects_non_queued_run(client) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": "Accept Team non-queued",
            "captain_user_id": "captain-accept-4",
        },
    ).json()
    _register_worker(client, "worker-accept-4")

    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-accept-4",
            "run_kind": "single_task",
        },
    ).json()

    response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/accepted",
        json={"worker_id": "worker-accept-4", "lease_id": "lease-4"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invariant_violation"
