from __future__ import annotations

import json
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from worker_service.main import (
    _build_package_archive,
    _engine_timeout_seconds,
    _execute_manifest_game,
    _parse_engine_payload,
    settings,
)


def test_build_package_archive_contains_game_files(tmp_path: Path) -> None:
    package_dir = tmp_path / "game"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "engine.py").write_text("print('ok')\n", encoding="utf-8")
    (package_dir / "data.txt").write_text("42\n", encoding="utf-8")
    (package_dir / ".secret").write_text("should-not-be-packed\n", encoding="utf-8")

    archive_bytes = _build_package_archive(package_dir)
    assert archive_bytes

    with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:gz") as archive:
        names = set(archive.getnames())
    assert "engine.py" in names
    assert "data.txt" in names
    assert ".secret" not in names


def test_execute_manifest_game_uses_docker_runner_with_limits(monkeypatch: Any, tmp_path: Path) -> None:
    games_root = tmp_path / "games"
    package_dir = games_root / "sample_game"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "engine.py").write_text("print('unused-local')\n", encoding="utf-8")

    settings.games_root = str(games_root)
    settings.execution_mode = "docker"
    settings.docker_binary = "docker"
    settings.docker_image = "python:3.12-slim"
    settings.docker_network_mode = "none"
    settings.docker_log_driver = "json-file"
    settings.docker_log_max_size = "10m"
    settings.docker_log_max_file = "3"
    settings.docker_cpu_limit = "1.5"
    settings.docker_memory_limit = "384m"
    settings.docker_pids_limit = 256
    settings.docker_tmpfs_size = "96m"
    settings.execution_timeout_seconds = 3.0
    settings.engine_timeout_cap_seconds = 60.0

    captured: dict[str, Any] = {}

    class _Completed:
        returncode = 0
        stdout = b'{"status":"finished","metrics":{"duration_ms": 1}}\n'
        stderr = b""

    def fake_run(command: list[str], **kwargs: Any) -> _Completed:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _Completed()

    monkeypatch.setattr("worker_service.main.subprocess.run", fake_run)

    payload = _execute_manifest_game(
        {
            "game_package_dir": "sample_game",
            "engine_entrypoint": "engine.py",
            "run_kind": "single_task",
            "snapshot_id": "snap-1",
        }
    )
    assert payload["status"] == "finished"

    command = captured["command"]
    assert command[0] == "docker"
    assert "--rm" in command
    assert "-i" in command
    assert "--read-only" in command
    assert "--log-driver" in command
    assert settings.docker_log_driver in command
    assert "--log-opt" in command
    assert f"max-size={settings.docker_log_max_size}" in command
    assert f"max-file={settings.docker_log_max_file}" in command
    assert "--network" in command
    assert settings.docker_network_mode in command
    assert "--cpus" in command
    assert settings.docker_cpu_limit in command
    assert "--memory" in command
    assert settings.docker_memory_limit in command
    assert "--pids-limit" in command
    assert str(settings.docker_pids_limit) in command

    kwargs = captured["kwargs"]
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    assert kwargs["timeout"] == settings.execution_timeout_seconds
    assert isinstance(kwargs["input"], bytes)
    assert len(kwargs["input"]) > 0


def test_execute_manifest_game_reports_missing_docker_binary(monkeypatch: Any, tmp_path: Path) -> None:
    games_root = tmp_path / "games"
    package_dir = games_root / "sample_game"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "engine.py").write_text("print('unused-local')\n", encoding="utf-8")

    settings.games_root = str(games_root)
    settings.execution_mode = "docker"
    settings.docker_binary = "docker-missing"

    def fake_run(*_: Any, **__: Any) -> Any:
        raise FileNotFoundError("docker-missing")

    monkeypatch.setattr("worker_service.main.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="Docker binary not found"):
        _execute_manifest_game(
            {
                "game_package_dir": "sample_game",
                "engine_entrypoint": "engine.py",
            }
        )


def test_parse_engine_payload_enforces_result_turn_limit() -> None:
    old_limit = settings.result_max_turns
    settings.result_max_turns = 500
    try:
        payload = {
            "status": "finished",
            "metrics": {"turns": 700},
            "frames": [
                {"tick": 0, "phase": "running", "frame": {"value": 0}},
                {"tick": 500, "phase": "running", "frame": {"value": 500}},
                {"tick": 501, "phase": "running", "frame": {"value": 501}},
                {"tick": 700, "phase": "finished", "frame": {"value": 700}},
            ],
            "events": [
                {"type": "kept", "tick": 500},
                {"type": "dropped", "tick": 501},
            ],
        }

        parsed = _parse_engine_payload(json.dumps(payload))

        assert [frame["tick"] for frame in parsed["frames"]] == [0, 500, 500]
        assert parsed["frames"][-1]["phase"] == "finished"
        assert parsed["metrics"]["turn_limit_enforced"] is True
        assert parsed["metrics"]["result_max_turns"] == 500
        assert parsed["metrics"]["dropped_frames"] == 2
        assert [event["type"] for event in parsed["events"]] == ["kept", "turn_limit_enforced"]
        assert parsed["events"][-1]["dropped_events"] == 1
    finally:
        settings.result_max_turns = old_limit


def test_engine_timeout_is_capped_to_one_minute() -> None:
    old_timeout = settings.execution_timeout_seconds
    old_cap = settings.engine_timeout_cap_seconds
    try:
        settings.execution_timeout_seconds = 120.0
        settings.engine_timeout_cap_seconds = 60.0
        assert _engine_timeout_seconds() == 60.0

        settings.execution_timeout_seconds = 20.0
        assert _engine_timeout_seconds() == 20.0
    finally:
        settings.execution_timeout_seconds = old_timeout
        settings.engine_timeout_cap_seconds = old_cap
