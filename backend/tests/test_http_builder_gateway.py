from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from administration.domain.model import SyncStatus
from administration.infrastructure.http_builder_gateway import HttpBuilderGateway
from shared.kernel import ExternalServiceError


@dataclass(frozen=True, slots=True)
class _ExpectedCall:
    method: str
    url: str
    json: dict[str, Any]
    status_code: int = 200
    payload: dict[str, Any] | None = None


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class _ScriptedClient:
    def __init__(self, calls: list[_ExpectedCall], timeout: float) -> None:
        self._calls = calls
        self._timeout = timeout

    def __enter__(self) -> "_ScriptedClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:
        assert self._calls, f"Unexpected POST {url}"
        expected = self._calls.pop(0)
        assert expected.method == "POST"
        assert expected.url == url
        assert expected.json == json
        return _FakeResponse(status_code=expected.status_code, payload=expected.payload)


def test_http_builder_gateway_returns_finished_result(monkeypatch: Any) -> None:
    calls = [
        _ExpectedCall(
            method="POST",
            url="http://builder/internal/builds/start",
            json={"game_source_id": "gsrc_1", "repo_url": "https://github.com/example/repo"},
            payload={
                "build_id": "build_0123456789abcdef0123456789abcdef",
                "status": "finished",
                "image_digest": "sha256:" + ("a" * 64),
            },
        ),
    ]
    monkeypatch.setattr(
        "administration.infrastructure.http_builder_gateway.httpx.Client",
        lambda timeout: _ScriptedClient(calls, timeout),
    )

    gateway = HttpBuilderGateway("http://builder", timeout_seconds=1.0)
    result = gateway.start_build(game_source_id="gsrc_1", repo_url="https://github.com/example/repo")

    assert result.status is SyncStatus.FINISHED
    assert result.build_id == "build_0123456789abcdef0123456789abcdef"
    assert result.image_digest == "sha256:" + ("a" * 64)
    assert calls == []


def test_http_builder_gateway_requires_build_id(monkeypatch: Any) -> None:
    calls = [
        _ExpectedCall(
            method="POST",
            url="http://builder/internal/builds/start",
            json={"game_source_id": "gsrc_1", "repo_url": "https://github.com/example/repo"},
            payload={"status": "finished", "image_digest": "sha256:" + ("a" * 64)},
        ),
    ]
    monkeypatch.setattr(
        "administration.infrastructure.http_builder_gateway.httpx.Client",
        lambda timeout: _ScriptedClient(calls, timeout),
    )

    gateway = HttpBuilderGateway("http://builder", timeout_seconds=1.0)
    try:
        gateway.start_build(game_source_id="gsrc_1", repo_url="https://github.com/example/repo")
        assert False, "Expected ExternalServiceError"
    except ExternalServiceError as exc:
        assert exc.message == "builder-service завершил sync без build_id"


def test_http_builder_gateway_requires_digest_for_finished(monkeypatch: Any) -> None:
    calls = [
        _ExpectedCall(
            method="POST",
            url="http://builder/internal/builds/start",
            json={"game_source_id": "gsrc_1", "repo_url": "https://github.com/example/repo"},
            payload={
                "build_id": "build_0123456789abcdef0123456789abcdef",
                "status": "finished",
                "image_digest": None,
            },
        ),
    ]
    monkeypatch.setattr(
        "administration.infrastructure.http_builder_gateway.httpx.Client",
        lambda timeout: _ScriptedClient(calls, timeout),
    )

    gateway = HttpBuilderGateway("http://builder", timeout_seconds=1.0)
    try:
        gateway.start_build(game_source_id="gsrc_1", repo_url="https://github.com/example/repo")
        assert False, "Expected ExternalServiceError"
    except ExternalServiceError as exc:
        assert exc.message == "builder-service завершил build без image_digest"


def test_http_builder_gateway_returns_failed_result(monkeypatch: Any) -> None:
    calls = [
        _ExpectedCall(
            method="POST",
            url="http://builder/internal/builds/start",
            json={"game_source_id": "gsrc_1", "repo_url": "https://github.com/example/repo"},
            payload={
                "build_id": "build_0123456789abcdef0123456789abcdef",
                "status": "failed",
                "error_message": "build failed",
            },
        ),
    ]
    monkeypatch.setattr(
        "administration.infrastructure.http_builder_gateway.httpx.Client",
        lambda timeout: _ScriptedClient(calls, timeout),
    )

    gateway = HttpBuilderGateway("http://builder", timeout_seconds=1.0)
    result = gateway.start_build(game_source_id="gsrc_1", repo_url="https://github.com/example/repo")

    assert result.status is SyncStatus.FAILED
    assert result.build_id == "build_0123456789abcdef0123456789abcdef"
    assert result.error_message == "build failed"


def test_http_builder_gateway_rejects_unexpected_status(monkeypatch: Any) -> None:
    calls = [
        _ExpectedCall(
            method="POST",
            url="http://builder/internal/builds/start",
            json={"game_source_id": "gsrc_1", "repo_url": "https://github.com/example/repo"},
            payload={
                "build_id": "build_0123456789abcdef0123456789abcdef",
                "status": "started",
            },
        ),
    ]
    monkeypatch.setattr(
        "administration.infrastructure.http_builder_gateway.httpx.Client",
        lambda timeout: _ScriptedClient(calls, timeout),
    )

    gateway = HttpBuilderGateway("http://builder", timeout_seconds=1.0)
    try:
        gateway.start_build(game_source_id="gsrc_1", repo_url="https://github.com/example/repo")
        assert False, "Expected ExternalServiceError"
    except ExternalServiceError as exc:
        assert "неожиданный статус" in exc.message


def test_http_builder_gateway_wraps_http_errors(monkeypatch: Any) -> None:
    class _FailingClient:
        def __init__(self, timeout: float) -> None:
            self._timeout = timeout

        def __enter__(self) -> "_FailingClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:  # noqa: ARG002
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(
        "administration.infrastructure.http_builder_gateway.httpx.Client",
        _FailingClient,
    )

    gateway = HttpBuilderGateway("http://builder", timeout_seconds=1.0)
    try:
        gateway.start_build(game_source_id="gsrc_1", repo_url="https://github.com/example/repo")
        assert False, "Expected ExternalServiceError"
    except ExternalServiceError as exc:
        assert exc.message == "Не удалось связаться с builder-service"
