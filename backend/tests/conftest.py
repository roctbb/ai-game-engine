import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import _build_container


@pytest.fixture()
def container():
    # Пересобираем in-memory контейнер для изоляции тестов.
    app.dependency_overrides.clear()
    from app.dependencies import get_container

    built_container = _build_container()
    app.dependency_overrides[get_container] = lambda: built_container
    return built_container


@pytest.fixture()
def client(container):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def teacher_headers(client):
    response = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": "teacher-test", "role": "teacher"},
    )
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    return {"X-Session-Id": session_id}
