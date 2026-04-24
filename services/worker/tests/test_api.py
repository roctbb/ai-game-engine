from __future__ import annotations

from fastapi.testclient import TestClient

from worker_service.main import app


def test_healthcheck() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_heartbeat_endpoint() -> None:
    client = TestClient(app)
    response = client.post(
        "/internal/workers/heartbeat",
        json={
            "worker_id": "worker-1",
            "hostname": "worker-host",
            "available_slots": 1,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"worker_id": "worker-1", "status": "alive"}
