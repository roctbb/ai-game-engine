from fastapi.testclient import TestClient

from app.main import app


def test_healthcheck() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
