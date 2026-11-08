"""Real engines + Redis Lua + both HTTP APIs, with no external infrastructure."""

# ruff: noqa: E402 -- services are independent projects, bootstrapped below.
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import ConnectionError

ROOT = Path(__file__).resolve().parents[2]
for service in ("worker", "scheduler"):
    sys.path.insert(0, str(ROOT / "services" / service / "src"))

from competition.application.service import CreateCompetitionInput
from competition.domain.model import CompetitionCodePolicy, CompetitionFormat, TieBreakPolicy
from execution.application.service import CreateRunInput, RegisterWorkerInput
from execution.domain.model import RunKind, RunStatus, WorkerStatus
import scheduler_service.main as scheduler
from scheduler_service.queue import SchedulerQueue
import worker_service.main as worker
from worker_service import processes


@contextmanager
def private_redis():
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server required for distributed integration")
    with tempfile.TemporaryDirectory(prefix="agp-e2e-", dir="/tmp") as directory:
        process = subprocess.Popen(
            [
                binary,
                "--port",
                "0",
                "--unixsocket",
                directory + "/redis.sock",
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        client = Redis(unix_socket_path=directory + "/redis.sock")
        try:
            for _ in range(200):
                try:
                    if client.ping():
                        break
                except ConnectionError:
                    time.sleep(0.025)
            else:
                raise RuntimeError("Redis failed to start")
            yield client
        finally:
            client.close()
            process.terminate()
            process.wait(timeout=5)


@pytest.fixture()
def distributed(client, container, monkeypatch):
    with private_redis() as redis:
        queue = SchedulerQueue(redis)
        monkeypatch.setattr(scheduler, "queue", queue)
        monkeypatch.setattr(scheduler.settings, "lease_ttl_seconds", 2)
        monkeypatch.setattr(scheduler.settings, "lease_requeue_check_interval_seconds", 0)
        with TestClient(scheduler.app) as scheduler_api:

            class Gateway:
                def schedule_run(self, run_id, required_worker_labels=None):
                    response = scheduler_api.post(
                        f"/internal/runs/{run_id}/schedule",
                        json={"required_worker_labels": required_worker_labels or {}},
                    )
                    response.raise_for_status()

                def cancel_run(self, run_id):
                    scheduler_api.post(f"/internal/runs/{run_id}/cancel").raise_for_status()

            container.execution._scheduler_gateway = Gateway()

            def transport(request):
                api = scheduler_api if request.url.host == "scheduler" else client
                response = api.request(
                    request.method,
                    request.url.path,
                    headers=dict(request.headers),
                    content=request.content,
                )
                return httpx.Response(
                    response.status_code, headers=dict(response.headers), content=response.content
                )

            with httpx.Client(transport=httpx.MockTransport(transport)) as outbound:
                monkeypatch.setattr(worker, "_persistent_client", outbound)
                monkeypatch.setattr(worker, "_last_worker_status", None)
                monkeypatch.setattr(worker, "_worker_registration_expires_at", 0)
                monkeypatch.setattr(worker, "_worker_heartbeat_expires_at", 0)
                monkeypatch.setattr(worker, "_active_slots", 0)
                for key, value in {
                    "backend_api_url": "http://backend/api/v1",
                    "scheduler_url": "http://scheduler",
                    "games_root": str(ROOT / "games"),
                    "execution_mode": "local_process",
                    "max_slots": 1,
                    "execution_timeout_seconds": 10,
                    "worker_id": "e2e-worker",
                    "request_max_attempts": 1,
                }.items():
                    monkeypatch.setattr(worker.settings, key, value)
                yield container, queue


def ready_team(container, slug, owner, code):
    game = next(g for g in container.game_catalog.list_games() if g.slug == slug)
    team = container.team_workspace.create_team(game.game_id, owner, owner)
    for slot in game.active_version.required_slot_keys:
        container.team_workspace.update_slot_code(team.team_id, owner, slot, code)
    return game, team


@pytest.mark.parametrize("slug", ["planet_wars_v1", "ttt_connect5_v1", "tanks_ctf_v1"])
def test_tournament_executes_both_real_bots_once(distributed, slug):
    container, queue = distributed
    move = "[]" if slug == "planet_wars_v1" else "(0, 0)" if slug == "ttt_connect5_v1" else "None"
    function = "make_move" if slug == "planet_wars_v1" else "make_choice"
    game, first = ready_team(
        container, slug, "first", f"def {function}(*args):\n    print('FIRST')\n    return {move}"
    )
    _, second = ready_team(
        container, slug, "second", f"def {function}(*args):\n    print('SECOND')\n    return {move}"
    )
    competition = container.competition.create_competition(
        CreateCompetitionInput(
            game.game_id,
            "E2E",
            CompetitionFormat.SINGLE_ELIMINATION,
            TieBreakPolicy.MANUAL,
            CompetitionCodePolicy.LOCKED_ON_START,
            1,
            2,
        )
    )
    for team in (first, second):
        container.competition.register_team(competition.competition_id, team.team_id)
    container.competition.start_competition(competition.competition_id, "teacher")
    assert queue.stats()["queue_depth"] == 1
    result = worker._pull_and_execute_once()
    assert result["status"] == "completed"
    runs = container.execution.list_runs(lobby_id=competition.competition_id)
    assert len(runs) == 2
    assert all(run.status is RunStatus.FINISHED for run in runs)
    assert all(set(run.result_payload["scores"]) == {first.team_id, second.team_id} for run in runs)
    replay = container.spectator_replay.get_by_run_id(result["run_id"])
    assert replay.frames
    messages = [event.get("message") for event in replay.events]
    assert "FIRST" in messages and "SECOND" in messages
    assert queue.stats()["known_count"] == 0


def test_worker_recovers_dead_running_attempt(distributed):
    container, queue = distributed
    game, team = ready_team(
        container, "snake_v1", "recover", "def make_move(*args): return 'right'"
    )
    run = container.execution.create_run(
        CreateRunInput(team.team_id, game.game_id, "recover", RunKind.SINGLE_TASK)
    )
    container.execution.queue_run(run.run_id)
    old = queue.pull_next("dead", int(datetime.now(tz=UTC).timestamp()) - 3)
    container.execution.register_worker(RegisterWorkerInput("dead", "dead", 1, {}))
    container.execution.accept_run(run.run_id, "dead", old.lease_id, old.generation)
    container.execution.start_run(run.run_id, "dead", old.lease_id)
    assert worker._pull_and_execute_once()["status"] == "completed"
    completed = container.execution.get_run(run.run_id)
    assert completed.status is RunStatus.FINISHED
    assert completed.lease_generation > old.generation
    assert queue.stats()["known_count"] == 0


@pytest.mark.parametrize("mode", ["local_process", "docker"])
def test_stop_terminates_actual_infinite_bot_and_frees_slot(distributed, monkeypatch, mode):
    container, queue = distributed
    if mode == "docker":
        if shutil.which("docker") is None:
            pytest.skip("Docker unavailable")
        try:
            check = subprocess.run(
                ["docker", "image", "inspect", "python:3.12-slim"], capture_output=True, timeout=5
            )
        except subprocess.TimeoutExpired:
            pytest.skip("Docker daemon unavailable")
        if check.returncode:
            pytest.skip("python:3.12-slim image unavailable")
        monkeypatch.setattr(worker.settings, "execution_mode", "docker")
    game, team = ready_team(
        container, "snake_v1", "stop", "def make_move(*args):\n    while True: pass"
    )
    run = container.execution.create_run(
        CreateRunInput(team.team_id, game.game_id, "stop", RunKind.SINGLE_TASK)
    )
    container.execution.queue_run(run.run_id)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker._pull_and_execute_once)
        for _ in range(200):
            if run.run_id in processes._processes:
                break
            if future.done():
                pytest.fail(str(future.result()))
            time.sleep(0.025)
        else:
            pytest.fail("Engine did not start")
        assert worker._pull_and_execute_once()["status"] == "busy"
        container.execution.cancel_run(run.run_id, "manual_stop")
        assert future.result(timeout=5)["status"] == "canceled"
    assert run.run_id not in processes._processes
    assert worker._active_slots == 0
    assert queue.stats()["known_count"] == 0
    if mode == "docker":
        remaining = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label=ai-game-engine.run_id={run.run_id}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert remaining.stdout.strip() == ""


def test_disabled_status_survives_cached_poll_iterations(distributed, monkeypatch):
    container, _ = distributed
    assert worker._pull_and_execute_once()["status"] == "idle"
    node = container.execution.get_worker(worker.settings.worker_id)
    node.set_status(WorkerStatus.DISABLED)
    container.execution._worker_repository.save(node)
    monkeypatch.setattr(worker, "_worker_heartbeat_expires_at", 0)
    assert worker._pull_and_execute_once()["status"] == "paused"
    assert worker._pull_and_execute_once()["status"] == "paused"


def test_live_worker_renews_lease_during_long_engine(distributed, tmp_path):
    from execution.infrastructure.game_packages import GamePackageStore

    container, queue = distributed
    package = tmp_path / "games" / "snake"
    shutil.copytree(ROOT / "games" / "snake", package)
    (package / "engine.py").write_text(
        "import json, time\ntime.sleep(3)\nprint(json.dumps({'status': 'finished', 'metrics': {}}))\n"
    )
    container.execution.game_package_store = GamePackageStore(
        container.game_catalog, package.parent, tmp_path / "packages"
    )
    game, team = ready_team(container, "snake_v1", "long", "def make_move(*args): return 'right'")
    run = container.execution.create_run(
        CreateRunInput(team.team_id, game.game_id, "long", RunKind.SINGLE_TASK)
    )
    container.execution.queue_run(run.run_id)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker._pull_and_execute_once)
        for _ in range(200):
            if run.run_id in processes._processes:
                break
            time.sleep(0.025)
        time.sleep(2.2)
        assert queue.pull_next("other-worker", int(datetime.now(tz=UTC).timestamp())) is None
        assert future.result(timeout=5)["status"] == "completed"


def test_execution_deadline_has_timeout_status_and_clears_lease(distributed, monkeypatch):
    from fastapi import HTTPException

    container, queue = distributed
    monkeypatch.setattr(worker.settings, "execution_timeout_seconds", 0.1)
    game, team = ready_team(
        container, "snake_v1", "timeout", "def make_move(*args):\n    while True: pass"
    )
    run = container.execution.create_run(
        CreateRunInput(team.team_id, game.game_id, "timeout", RunKind.SINGLE_TASK)
    )
    container.execution.queue_run(run.run_id)
    with pytest.raises(HTTPException):
        worker._pull_and_execute_once()
    assert container.execution.get_run(run.run_id).status is RunStatus.TIMEOUT
    assert queue.stats()["known_count"] == 0
