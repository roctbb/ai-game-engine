from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from typing import Any
from types import ModuleType

import httpx
from fastapi.testclient import TestClient

import worker_service.main as worker_main
from worker_service.main import app, settings


@dataclass(frozen=True, slots=True)
class ExpectedCall:
    method: str
    url: str
    json: dict[str, Any] | None
    status_code: int = 200
    payload: dict[str, Any] | None = None


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, Any] | None = None,
        method: str = "GET",
        url: str = "http://fake",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.request = httpx.Request(method, url)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message=f"HTTP {self.status_code}",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self) -> dict[str, Any]:
        return self._payload


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expected_tic_tac_toe_payload(context: dict[str, Any]) -> dict[str, Any]:
    engine_module = _load_module(
        Path(__file__).resolve().parents[3] / "games" / "tic_tac_toe" / "engine.py",
        "worker_test_tic_tac_toe_engine",
    )
    return engine_module.run(context)


def _expected_maze_escape_payload(context: dict[str, Any]) -> dict[str, Any]:
    engine_module = _load_module(
        Path(__file__).resolve().parents[3] / "games" / "maze_escape" / "engine.py",
        "worker_test_maze_engine",
    )
    return engine_module.run(context)


class ScriptedHttpxClient:
    def __init__(
        self,
        calls: list[ExpectedCall],
        timeout: float,
        heartbeat_status: str = "online",
    ) -> None:
        self._calls = calls
        self._timeout = timeout
        self._heartbeat_status = heartbeat_status

    def __enter__(self) -> ScriptedHttpxClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        return self._consume("POST", url, json)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FakeResponse:
        return self._consume("GET", url, None)

    def _consume(self, method: str, url: str, json: dict[str, Any] | None) -> FakeResponse:
        heartbeat_url = f"{settings.backend_api_url}/internal/workers/{settings.worker_id}/heartbeat"
        if method == "POST" and url == heartbeat_url:
            return FakeResponse(
                status_code=200,
                payload={"status": self._heartbeat_status},
                method=method,
                url=url,
            )

        assert self._calls, f"Unexpected {method} {url}"
        expected = self._calls.pop(0)
        assert expected.method == method
        assert expected.url == url
        assert expected.json == json
        return FakeResponse(
            status_code=expected.status_code,
            payload=expected.payload,
            method=method,
            url=url,
        )


def _set_test_settings() -> None:
    worker_main._worker_registration_expires_at = 0.0
    worker_main._worker_heartbeat_expires_at = 0.0
    settings.backend_api_url = "http://backend"
    settings.scheduler_url = "http://scheduler"
    settings.internal_api_token = "dev-internal-token"
    settings.worker_id = "worker-test-1"
    settings.hostname = "worker-host"
    settings.max_slots = 2
    settings.worker_labels = {}
    settings.games_root = str(Path(__file__).resolve().parents[3] / "games")
    settings.execution_mode = "local_process"
    settings.execution_timeout_seconds = 2.0
    settings.request_timeout_seconds = 1.0
    settings.request_max_attempts = 3
    settings.retry_base_delay_ms = 1
    settings.retry_max_delay_ms = 2
    settings.worker_registration_ttl_seconds = 30.0
    settings.worker_heartbeat_interval_seconds = 5.0


def test_pull_and_execute_idle(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "empty", "run_id": None},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 200
    assert response.json() == {"worker_id": "worker-test-1", "status": "idle"}
    assert scripted_calls == []


def test_pull_and_execute_paused_for_disabled_worker(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
            payload={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "capacity_available": 2,
                "status": "disabled",
                "labels": {},
            },
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout, heartbeat_status="disabled"),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 200
    assert response.json() == {
        "worker_id": "worker-test-1",
        "status": "paused",
        "worker_status": "disabled",
    }
    assert scripted_calls == []


def test_pull_and_execute_paused_for_draining_worker(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
            payload={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "capacity_available": 2,
                "status": "draining",
                "labels": {},
            },
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout, heartbeat_status="draining"),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 200
    assert response.json() == {
        "worker_id": "worker-test-1",
        "status": "paused",
        "worker_status": "draining",
    }
    assert scripted_calls == []


def test_pull_and_execute_registers_worker_labels(monkeypatch: Any) -> None:
    _set_test_settings()
    settings.worker_labels = {"region": "eu-mow-1", "pool": "remote"}
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {"region": "eu-mow-1", "pool": "remote"},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "empty", "run_id": None},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 200
    assert response.json() == {"worker_id": "worker-test-1", "status": "idle"}
    assert scripted_calls == []


def test_pull_and_execute_reports_failed_when_execution_context_missing(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-123"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-123/execution-context",
            json=None,
            status_code=404,
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-123/failed",
            json={"message": "Execution context is not available for run run-123"},
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-123"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 500
    assert "Worker execution failed for run run-123" in response.json()["detail"]
    assert scripted_calls == []


def test_pull_and_execute_runs_manifest_game(monkeypatch: Any) -> None:
    _set_test_settings()
    execution_context = {
        "run_id": "run-manifest",
        "run_kind": "single_task",
        "game_id": "game-maze",
        "game_slug": "maze_escape_v1",
        "game_package_dir": "maze_escape",
        "code_api_mode": "script_based",
        "engine_entrypoint": "engine.py",
        "renderer_entrypoint": "renderer/index.html",
        "snapshot_id": "snap-1",
        "snapshot_version_id": "gver-1",
        "codes_by_slot": {
            "agent": (
                "def make_move(state):\n"
                "    x = state['position']['x']\n"
                "    y = state['position']['y']\n"
                "    if y < 6 and x in {0, 6}:\n"
                "        return 'down'\n"
                "    if x < 6:\n"
                "        return 'right'\n"
                "    return 'down'\n"
            )
        },
        "revisions_by_slot": {"agent": 1},
    }
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-manifest"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-manifest/execution-context",
            json=None,
            payload=execution_context,
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-manifest/accepted",
            json={"worker_id": "worker-test-1"},
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-manifest/started",
            json={"worker_id": "worker-test-1"},
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-manifest/finished",
            json={
                "payload": _expected_maze_escape_payload(execution_context)
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-manifest"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 200
    assert response.json() == {
        "worker_id": "worker-test-1",
        "status": "completed",
        "run_id": "run-manifest",
    }
    assert scripted_calls == []


def test_pull_and_execute_runs_turn_based_manifest_game(monkeypatch: Any) -> None:
    _set_test_settings()
    execution_context = {
        "run_id": "run-turn-based",
        "team_id": "team-turn-based",
        "run_kind": "training_match",
        "game_id": "game-turn",
        "game_slug": "ttt_connect5_v1",
        "game_package_dir": "tic_tac_toe",
        "code_api_mode": "turn_based",
        "engine_entrypoint": "engine.py",
        "renderer_entrypoint": "renderer/index.html",
        "snapshot_id": "snap-turn",
        "snapshot_version_id": "gver-turn",
        "codes_by_slot": {
            "bot": (
                "def make_choice(field, role):\n"
                "    for x in range(5):\n"
                "        for y in range(5):\n"
                "            if field[x][y] == 0:\n"
                "                return x, y\n"
            )
        },
        "revisions_by_slot": {"bot": 3},
    }
    expected_payload = _expected_tic_tac_toe_payload(execution_context)

    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-turn-based"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-turn-based/execution-context",
            json=None,
            payload=execution_context,
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-turn-based/accepted",
            json={"worker_id": "worker-test-1"},
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-turn-based/started",
            json={"worker_id": "worker-test-1"},
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-turn-based/finished",
            json={"payload": expected_payload},
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-turn-based"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 200
    assert response.json() == {
        "worker_id": "worker-test-1",
        "status": "completed",
        "run_id": "run-turn-based",
    }
    assert scripted_calls == []


def test_pull_and_execute_reports_failed_for_unsupported_code_api_mode(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-turn"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-turn/execution-context",
            json=None,
            payload={
                "run_id": "run-turn",
                "run_kind": "training_match",
                "game_id": "game-turn",
                "game_slug": "ttt_connect5_v1",
                "game_package_dir": "tic_tac_toe",
                "code_api_mode": "legacy_sdk",
                "engine_entrypoint": "engine.py",
                "renderer_entrypoint": "renderer/index.html",
                "snapshot_id": "snap-turn",
                "snapshot_version_id": "gver-turn",
                "codes_by_slot": {"bot": "def make_choice(*args): return 0, 0\n"},
                "revisions_by_slot": {"bot": 1},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-turn/failed",
            json={"message": "Unsupported code_api_mode=legacy_sdk"},
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-turn"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 500
    assert "Worker execution failed for run run-turn" in response.json()["detail"]
    assert scripted_calls == []


def test_pull_and_execute_reports_failed_for_missing_run_kind(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-mismatch"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-mismatch/execution-context",
            json=None,
            payload={
                "run_id": "run-mismatch",
                "game_id": "game-turn",
                "game_slug": "ttt_connect5_v1",
                "game_package_dir": "tic_tac_toe",
                "code_api_mode": "turn_based",
                "engine_entrypoint": "engine.py",
                "renderer_entrypoint": "renderer/index.html",
                "snapshot_id": "snap-turn",
                "snapshot_version_id": "gver-turn",
                "codes_by_slot": {"bot": "def make_choice(*args): return 0, 0\n"},
                "revisions_by_slot": {"bot": 1},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-mismatch/failed",
            json={"message": "Execution context is missing run_kind"},
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-mismatch"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 500
    assert "Worker execution failed for run run-mismatch" in response.json()["detail"]
    assert scripted_calls == []


def test_pull_and_execute_reports_failed_for_unsupported_run_kind(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-unknown-kind"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-unknown-kind/execution-context",
            json=None,
            payload={
                "run_id": "run-unknown-kind",
                "run_kind": "sandbox_probe",
                "game_id": "game-turn",
                "game_slug": "ttt_connect5_v1",
                "game_package_dir": "tic_tac_toe",
                "code_api_mode": "turn_based",
                "engine_entrypoint": "engine.py",
                "renderer_entrypoint": "renderer/index.html",
                "snapshot_id": "snap-turn",
                "snapshot_version_id": "gver-turn",
                "codes_by_slot": {"bot": "def make_choice(*args): return 0, 0\n"},
                "revisions_by_slot": {"bot": 1},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-unknown-kind/failed",
            json={"message": "Unsupported run_kind=sandbox_probe"},
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-unknown-kind"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 500
    assert "Worker execution failed for run run-unknown-kind" in response.json()["detail"]
    assert scripted_calls == []


def test_pull_and_execute_reports_failed_on_http_error(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-err"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-err/execution-context",
            json=None,
            payload={
                "run_id": "run-err",
                "run_kind": "single_task",
                "game_id": "game-err",
                "game_slug": "maze_escape_v1",
                "game_package_dir": "maze_escape",
                "code_api_mode": "script_based",
                "engine_entrypoint": "engine.py",
                "renderer_entrypoint": "renderer/index.html",
                "snapshot_id": "snap-err",
                "snapshot_version_id": "gver-err",
                "codes_by_slot": {"agent": "def make_move(state):\n    return 'right'\n"},
                "revisions_by_slot": {"agent": 1},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-err/accepted",
            json={"worker_id": "worker-test-1"},
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-err/started",
            json={"worker_id": "worker-test-1"},
            status_code=404,
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-err/failed",
            json={"message": "HTTP 404"},
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-err"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 502
    assert "Worker execution failed for run run-err" in response.json()["detail"]
    assert scripted_calls == []


def test_pull_and_execute_acks_stale_backend_run(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-stale"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-stale/execution-context",
            json=None,
            payload={
                "run_id": "run-stale",
                "run_kind": "single_task",
                "game_id": "game-stale",
                "game_slug": "maze_escape_v1",
                "game_package_dir": "maze_escape",
                "code_api_mode": "script_based",
                "engine_entrypoint": "engine.py",
                "renderer_entrypoint": "renderer/index.html",
                "snapshot_id": "snap-stale",
                "snapshot_version_id": "gver-stale",
                "codes_by_slot": {"agent": "def make_move(state):\n    return 'right'\n"},
                "revisions_by_slot": {"agent": 1},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-stale/accepted",
            json={"worker_id": "worker-test-1"},
            status_code=422,
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-stale/failed",
            json={"message": "HTTP 422"},
            status_code=422,
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-stale"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 502
    assert "Worker execution failed for run run-stale" in response.json()["detail"]
    assert scripted_calls == []


def test_pull_and_execute_reports_failed_on_engine_error(monkeypatch: Any, tmp_path: Path) -> None:
    _set_test_settings()
    game_dir = tmp_path / "broken_game"
    game_dir.mkdir()
    (game_dir / "engine.py").write_text(
        "import sys\nsys.stderr.write('boom')\nsys.exit(2)\n",
        encoding="utf-8",
    )
    settings.games_root = str(tmp_path)
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "assigned", "run_id": "run-broken"},
        ),
        ExpectedCall(
            method="GET",
            url="http://backend/internal/runs/run-broken/execution-context",
            json=None,
            payload={
                "run_id": "run-broken",
                "run_kind": "single_task",
                "game_id": "game-broken",
                "game_slug": "broken_game_v1",
                "game_package_dir": "broken_game",
                "code_api_mode": "script_based",
                "engine_entrypoint": "engine.py",
                "renderer_entrypoint": None,
                "snapshot_id": "snap-broken",
                "snapshot_version_id": "gver-broken",
                "codes_by_slot": {"agent": "print('broken')\n"},
                "revisions_by_slot": {"agent": 1},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-broken/accepted",
            json={"worker_id": "worker-test-1"},
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-broken/started",
            json={"worker_id": "worker-test-1"},
        ),
        ExpectedCall(
            method="POST",
            url="http://backend/internal/runs/run-broken/failed",
            json={"message": "Game engine exited with 2: boom"},
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/runs/ack-finished",
            json={"worker_id": "worker-test-1", "run_id": "run-broken"},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 500
    assert "Worker execution failed for run run-broken" in response.json()["detail"]
    assert scripted_calls == []


def test_pull_and_execute_retries_retryable_errors(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            status_code=503,
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            payload={"status": "empty", "run_id": None},
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )
    monkeypatch.setattr("worker_service.main.time.sleep", lambda _delay: None)

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 200
    assert response.json() == {"worker_id": "worker-test-1", "status": "idle"}
    assert scripted_calls == []


def test_pull_and_execute_does_not_retry_non_retryable_error(monkeypatch: Any) -> None:
    _set_test_settings()
    scripted_calls = [
        ExpectedCall(
            method="POST",
            url="http://backend/internal/workers/register",
            json={
                "worker_id": "worker-test-1",
                "hostname": "worker-host",
                "capacity_total": 2,
                "labels": {},
            },
        ),
        ExpectedCall(
            method="POST",
            url="http://scheduler/internal/workers/pull-next",
            json={"worker_id": "worker-test-1", "worker_labels": settings.worker_labels},
            status_code=404,
        ),
    ]

    monkeypatch.setattr(
        "worker_service.main.httpx.Client",
        lambda timeout: ScriptedHttpxClient(scripted_calls, timeout),
    )
    monkeypatch.setattr("worker_service.main.time.sleep", lambda _delay: None)

    client = TestClient(app)
    response = client.post("/internal/worker/pull-and-execute")
    assert response.status_code == 502
    assert response.json()["detail"] == "Worker failed to pull run from scheduler"
    assert scripted_calls == []
