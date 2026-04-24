import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import _build_container
from shared.config.settings import settings


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
        login = test_client.post(
            "/api/v1/auth/dev-login",
            json={"nickname": "test-teacher", "role": "teacher"},
        )
        assert login.status_code == 200
        default_session_id = login.json()["session_id"]
        original_request = test_client.request

        def request_with_default_session(method, url, **kwargs):
            headers = dict(kwargs.pop("headers", {}) or {})
            skip_session = headers.pop("X-Test-No-Session", "") == "1"
            skip_internal_token = headers.pop("X-Test-No-Internal-Token", "") == "1"
            if not skip_session and "X-Session-Id" not in headers and "X-Dev-Session" not in headers:
                headers["X-Session-Id"] = default_session_id
            if (
                not skip_internal_token
                and "/api/v1/internal/" in str(url)
                and "X-Internal-Token" not in headers
            ):
                headers["X-Internal-Token"] = settings.internal_api_token
            kwargs["headers"] = headers
            return original_request(method, url, **kwargs)

        test_client.request = request_with_default_session
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
