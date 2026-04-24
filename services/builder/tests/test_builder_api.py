from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from builder_service.main import app, settings


@dataclass(frozen=True, slots=True)
class ExpectedCall:
    method: str
    url: str
    json: dict[str, Any] | None
    status_code: int = 200
    payload: dict[str, Any] | None = None


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.request = httpx.Request("POST", "http://builder-test")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message=f"HTTP {self.status_code}",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self) -> dict[str, Any]:
        return self._payload


class ScriptedHttpxClient:
    def __init__(self, calls: list[ExpectedCall], timeout: float) -> None:
        self._calls = calls
        self._timeout = timeout

    def __enter__(self) -> "ScriptedHttpxClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        assert self._calls, f"Unexpected POST {url}"
        expected = self._calls.pop(0)
        assert expected.method == "POST"
        assert expected.url == url
        assert expected.json == json
        return FakeResponse(status_code=expected.status_code, payload=expected.payload)


def _set_test_settings() -> None:
    settings.backend_api_url = "http://backend"
    settings.internal_api_token = "dev-internal-token"
    settings.request_timeout_seconds = 1.0


def test_healthcheck() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_build_success(monkeypatch: Any) -> None:
    _set_test_settings()
    expected_digest = "sha256:e6eae60f081e33bda56de692e085a354df775d773588f2632ec8c8a78203ba29"
    build_id = "build_0123456789abcdef0123456789abcdef"
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/builds/start",
            json={
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
            },
            payload={
                "build_id": build_id,
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
                "status": "started",
                "image_digest": None,
                "error_message": None,
            },
        ),
        ExpectedCall(
            method="POST",
            url=f"http://backend/internal/builds/{build_id}/finished",
            json={"image_digest": expected_digest},
            payload={
                "build_id": build_id,
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
                "status": "finished",
                "image_digest": expected_digest,
                "error_message": None,
            },
        ),
    ]

    monkeypatch.setattr(
        "builder_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post(
        "/internal/builds/start",
        json={
            "game_source_id": "gsrc_123",
            "repo_url": "https://github.com/example/game-repo",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "finished"
    assert response.json()["image_digest"] == expected_digest
    assert scripted_calls == []


def test_start_build_reports_failed_on_backend_error(monkeypatch: Any) -> None:
    _set_test_settings()
    expected_digest = "sha256:e6eae60f081e33bda56de692e085a354df775d773588f2632ec8c8a78203ba29"
    build_id = "build_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/builds/start",
            json={
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
            },
            payload={
                "build_id": build_id,
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
                "status": "started",
                "image_digest": None,
                "error_message": None,
            },
        ),
        ExpectedCall(
            method="POST",
            url=f"http://backend/internal/builds/{build_id}/finished",
            json={"image_digest": expected_digest},
            status_code=500,
        ),
        ExpectedCall(
            method="POST",
            url=f"http://backend/internal/builds/{build_id}/failed",
            json={"error_message": "HTTP 500"},
            payload={
                "build_id": build_id,
                "status": "failed",
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
                "image_digest": None,
                "error_message": "HTTP 500",
            },
        ),
    ]

    monkeypatch.setattr(
        "builder_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post(
        "/internal/builds/start",
        json={
            "game_source_id": "gsrc_123",
            "repo_url": "https://github.com/example/game-repo",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Builder service failed to sync build status"
    assert scripted_calls == []


def test_start_build_fails_when_backend_returns_invalid_start_payload(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/builds/start",
            json={
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
            },
            payload={
                "build_id": "bad-id",
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
                "status": "started",
            },
        ),
    ]

    monkeypatch.setattr(
        "builder_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post(
        "/internal/builds/start",
        json={
            "game_source_id": "gsrc_123",
            "repo_url": "https://github.com/example/game-repo",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Builder service failed to sync build status"
    assert scripted_calls == []


def test_start_build_fails_when_backend_returns_invalid_finished_payload(monkeypatch: Any) -> None:
    _set_test_settings()
    expected_digest = "sha256:e6eae60f081e33bda56de692e085a354df775d773588f2632ec8c8a78203ba29"
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/builds/start",
            json={
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
            },
            payload={
                "build_id": "build_0123456789abcdef0123456789abcdef",
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
                "status": "started",
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/builds/build_0123456789abcdef0123456789abcdef/finished",
            json={"image_digest": expected_digest},
            payload={
                "build_id": "build_0123456789abcdef0123456789abcdef",
                "status": "finished",
                "image_digest": "sha256:" + ("b" * 64),
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/builds/build_0123456789abcdef0123456789abcdef/failed",
            json={"error_message": "Backend returned unexpected image_digest in finished response"},
            payload={
                "build_id": "build_0123456789abcdef0123456789abcdef",
                "status": "failed",
                "game_source_id": "gsrc_123",
                "repo_url": "https://github.com/example/game-repo",
                "image_digest": None,
                "error_message": "Backend returned unexpected image_digest in finished response",
            },
        ),
    ]

    monkeypatch.setattr(
        "builder_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post(
        "/internal/builds/start",
        json={
            "game_source_id": "gsrc_123",
            "repo_url": "https://github.com/example/game-repo",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Builder service failed to sync build status"
    assert scripted_calls == []


def test_start_build_rejects_invalid_repo_url() -> None:
    client = TestClient(app)
    response = client.post(
        "/internal/builds/start",
        json={
            "game_source_id": "gsrc_123",
            "repo_url": "not-a-url",
        },
    )

    assert response.status_code == 422
