from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient

from scheduler_service.main import app


@dataclass
class FakeQueue:
    enqueue_result: bool = True
    pull_result: str | None = None
    ack_result: bool = True
    stats_payload: dict[str, object] = field(
        default_factory=lambda: {"queue_depth": 0, "known_count": 0, "worker_leases": {}}
    )
    enqueue_calls: list[tuple[str, dict[str, str] | None]] = field(default_factory=list)
    pull_calls: list[tuple[str, int, dict[str, str] | None]] = field(default_factory=list)
    ack_calls: list[tuple[str, str]] = field(default_factory=list)

    def enqueue(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> bool:
        self.enqueue_calls.append((run_id, required_worker_labels))
        return self.enqueue_result

    def pull_next(
        self,
        worker_id: str,
        leased_at_epoch: int,
        worker_labels: dict[str, str] | None = None,
    ) -> str | None:
        self.pull_calls.append((worker_id, leased_at_epoch, worker_labels))
        return self.pull_result

    def ack_finished(self, worker_id: str, run_id: str) -> bool:
        self.ack_calls.append((worker_id, run_id))
        return self.ack_result

    def stats(self) -> dict[str, object]:
        return self.stats_payload


def test_healthcheck() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_schedule_run_queued(monkeypatch: Any) -> None:
    fake_queue = FakeQueue(enqueue_result=True)
    monkeypatch.setattr("scheduler_service.main.queue", fake_queue)
    client = TestClient(app)

    response = client.post("/internal/runs/run-1/schedule")

    assert response.status_code == 200
    assert response.json() == {"run_id": "run-1", "status": "queued"}
    assert fake_queue.enqueue_calls == [("run-1", None)]


def test_schedule_run_already_queued(monkeypatch: Any) -> None:
    fake_queue = FakeQueue(enqueue_result=False)
    monkeypatch.setattr("scheduler_service.main.queue", fake_queue)
    client = TestClient(app)

    response = client.post("/internal/runs/run-1/schedule")

    assert response.status_code == 200
    assert response.json() == {"run_id": "run-1", "status": "already_queued"}
    assert fake_queue.enqueue_calls == [("run-1", None)]


def test_schedule_run_with_required_worker_labels(monkeypatch: Any) -> None:
    fake_queue = FakeQueue(enqueue_result=True)
    monkeypatch.setattr("scheduler_service.main.queue", fake_queue)
    client = TestClient(app)

    response = client.post(
        "/internal/runs/run-2/schedule",
        json={"required_worker_labels": {"pool": "gpu", "region": "eu-mow-1"}},
    )

    assert response.status_code == 200
    assert response.json() == {"run_id": "run-2", "status": "queued"}
    assert fake_queue.enqueue_calls == [("run-2", {"pool": "gpu", "region": "eu-mow-1"})]


def test_pull_next_assigned(monkeypatch: Any) -> None:
    fake_queue = FakeQueue(pull_result="run-7")
    monkeypatch.setattr("scheduler_service.main.queue", fake_queue)
    client = TestClient(app)

    response = client.post(
        "/internal/workers/pull-next",
        json={"worker_id": "w-1", "worker_labels": {"pool": "gpu"}},
    )

    assert response.status_code == 200
    assert response.json()["worker_id"] == "w-1"
    assert response.json()["run_id"] == "run-7"
    assert response.json()["status"] == "assigned"
    assert len(fake_queue.pull_calls) == 1
    assert fake_queue.pull_calls[0][0] == "w-1"
    assert isinstance(fake_queue.pull_calls[0][1], int)
    assert fake_queue.pull_calls[0][2] == {"pool": "gpu"}


def test_pull_next_empty(monkeypatch: Any) -> None:
    fake_queue = FakeQueue(pull_result=None)
    monkeypatch.setattr("scheduler_service.main.queue", fake_queue)
    client = TestClient(app)

    response = client.post("/internal/workers/pull-next", json={"worker_id": "w-2"})

    assert response.status_code == 200
    assert response.json() == {"worker_id": "w-2", "run_id": None, "status": "empty"}


def test_ack_finished(monkeypatch: Any) -> None:
    fake_queue = FakeQueue(ack_result=True)
    monkeypatch.setattr("scheduler_service.main.queue", fake_queue)
    client = TestClient(app)

    response = client.post(
        "/internal/runs/ack-finished",
        json={"worker_id": "w-1", "run_id": "run-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "acknowledged"}
    assert fake_queue.ack_calls == [("w-1", "run-1")]


def test_ack_finished_stale(monkeypatch: Any) -> None:
    fake_queue = FakeQueue(ack_result=False)
    monkeypatch.setattr("scheduler_service.main.queue", fake_queue)
    client = TestClient(app)

    response = client.post(
        "/internal/runs/ack-finished",
        json={"worker_id": "w-1", "run_id": "run-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "stale_lease_ignored"}
    assert fake_queue.ack_calls == [("w-1", "run-1")]


def test_queue_stats(monkeypatch: Any) -> None:
    stats_payload = {
        "queue_depth": 3,
        "known_count": 4,
        "worker_leases": {"w-1": [{"worker_id": "w-1", "run_id": "run-1", "leased_at": 10}]},
    }
    fake_queue = FakeQueue(stats_payload=stats_payload)
    monkeypatch.setattr("scheduler_service.main.queue", fake_queue)
    client = TestClient(app)

    response = client.get("/internal/queue/stats")

    assert response.status_code == 200
    assert response.json() == stats_payload
