from __future__ import annotations

import asyncio
from contextlib import suppress
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

from worker_service.settings import settings

app = FastAPI(title=settings.app_name)
logger = logging.getLogger(__name__)
_auto_poll_task: asyncio.Task[None] | None = None
_auto_poll_stop_event: asyncio.Event | None = None
_worker_registration_expires_at: float = 0.0
_worker_heartbeat_expires_at: float = 0.0
_persistent_client: httpx.Client | None = None
_package_archive_cache: dict[str, bytes] = {}

SUPPORTED_RUN_KINDS: set[str] = {"single_task", "training_match", "competition_match"}
SUPPORTED_CODE_API_MODES: set[str] = {"script_based", "turn_based"}


class HeartbeatPayload(BaseModel):
    worker_id: str
    hostname: str
    available_slots: int


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def start_auto_poll_loop() -> None:
    global _auto_poll_stop_event, _auto_poll_task, _persistent_client
    _persistent_client = httpx.Client(timeout=settings.request_timeout_seconds)
    if not settings.auto_poll_enabled:
        return
    _auto_poll_stop_event = asyncio.Event()
    _auto_poll_task = asyncio.create_task(_auto_poll_loop(_auto_poll_stop_event))


@app.on_event("shutdown")
async def stop_auto_poll_loop() -> None:
    global _auto_poll_stop_event, _auto_poll_task, _persistent_client
    if _auto_poll_stop_event is not None:
        _auto_poll_stop_event.set()
    if _auto_poll_task is not None:
        _auto_poll_task.cancel()
        with suppress(asyncio.CancelledError):
            await _auto_poll_task
    _auto_poll_stop_event = None
    _auto_poll_task = None
    if _persistent_client is not None:
        _persistent_client.close()
        _persistent_client = None


@app.post("/internal/workers/heartbeat")
def heartbeat(payload: HeartbeatPayload) -> dict[str, str]:
    # В следующей итерации этот endpoint будет пробрасывать heartbeat в control plane.
    return {"worker_id": payload.worker_id, "status": "alive"}


@app.post("/internal/worker/pull-and-execute")
def pull_and_execute() -> dict[str, object]:
    return _pull_and_execute_once()


async def _auto_poll_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            result = await asyncio.to_thread(_pull_and_execute_once)
            sleep_for = settings.auto_poll_interval_seconds
            if result.get("status") == "paused":
                sleep_for = max(settings.auto_poll_error_backoff_seconds, sleep_for)
        except Exception:
            logger.exception("Worker auto-poll iteration failed")
            sleep_for = settings.auto_poll_error_backoff_seconds

        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=max(sleep_for, 0.1))


def _pull_and_execute_once() -> dict[str, object]:
    # MVP: worker запрашивает следующую задачу у scheduler и проходит lifecycle accepted->started->finished.
    client = _persistent_client
    owns_client = False
    if client is None:
        client = httpx.Client(timeout=settings.request_timeout_seconds)
        owns_client = True
    try:
        try:
            registered_status = _ensure_worker_registered(client=client)
            heartbeat_status = _best_effort_send_worker_heartbeat(
                client=client,
                capacity_available=settings.max_slots,
            )
            effective_status = heartbeat_status or registered_status
            if not _is_worker_pull_allowed(effective_status):
                return {
                    "worker_id": settings.worker_id,
                    "status": "paused",
                    "worker_status": effective_status or "unknown",
                }
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail="Worker failed to register in control plane",
            ) from exc

        try:
            pull = _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.scheduler_url}/internal/workers/pull-next",
                json_payload={
                    "worker_id": settings.worker_id,
                    "worker_labels": settings.worker_labels,
                },
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail="Worker failed to pull run from scheduler",
            ) from exc
        data = pull.json()

        run_id = data.get("run_id")
        if not run_id:
            return {
                "worker_id": settings.worker_id,
                "status": "idle",
            }
        lease_id = data.get("lease_id")
        if not isinstance(lease_id, str) or not lease_id:
            raise RuntimeError(f"Scheduler did not return lease_id for run {run_id}")

        _best_effort_send_worker_heartbeat(
            client=client,
            capacity_available=max(settings.max_slots - 1, 0),
            force=True,
        )
        try:
            execution_context = _get_execution_context(client=client, run_id=run_id)
            if execution_context is None:
                raise RuntimeError(f"Execution context is not available for run {run_id}")
            run_kind_raw = execution_context.get("run_kind") if execution_context is not None else None
            if not isinstance(run_kind_raw, str):
                raise RuntimeError("Execution context is missing run_kind")
            resolved_context = _require_execution_context(
                run_id=run_id,
                run_kind=run_kind_raw,
                execution_context=execution_context,
            )

            _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.backend_api_url}/internal/runs/{run_id}/accepted",
                json_payload={"worker_id": settings.worker_id, "lease_id": lease_id},
            )

            _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.backend_api_url}/internal/runs/{run_id}/started",
                json_payload={"worker_id": settings.worker_id, "lease_id": lease_id},
            )

            payload = _execute_manifest_game(resolved_context)

            _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.backend_api_url}/internal/runs/{run_id}/finished",
                json_payload={"payload": payload, "lease_id": lease_id},
            )

            _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.scheduler_url}/internal/runs/ack-finished",
                json_payload={
                    "worker_id": settings.worker_id,
                    "run_id": run_id,
                    "lease_id": lease_id,
                },
            )
        except httpx.HTTPError as exc:
            reported_terminal = _best_effort_report_failed(
                client=client,
                run_id=run_id,
                lease_id=lease_id,
                error=str(exc),
            )
            if reported_terminal or _is_stale_backend_run_error(exc):
                _best_effort_ack_scheduler(client=client, run_id=run_id, lease_id=lease_id)
            raise HTTPException(status_code=502, detail=f"Worker execution failed for run {run_id}") from exc
        except Exception as exc:
            if _best_effort_report_failed(client=client, run_id=run_id, lease_id=lease_id, error=str(exc)):
                _best_effort_ack_scheduler(client=client, run_id=run_id, lease_id=lease_id)
            raise HTTPException(status_code=500, detail=f"Worker execution failed for run {run_id}") from exc
        finally:
            _best_effort_send_worker_heartbeat(
                client=client,
                capacity_available=settings.max_slots,
                force=True,
            )

        return {
            "worker_id": settings.worker_id,
            "status": "completed",
            "run_id": run_id,
        }
    finally:
        if owns_client:
            close = getattr(client, "close", None)
            if callable(close):
                close()


def _ensure_worker_registered(client: httpx.Client) -> str | None:
    global _worker_registration_expires_at
    now = time.monotonic()
    if now < _worker_registration_expires_at:
        return None

    response = _request_with_retry(
        client=client,
        method="POST",
        url=f"{settings.backend_api_url}/internal/workers/register",
        json_payload={
            "worker_id": settings.worker_id,
            "hostname": settings.hostname,
            "capacity_total": settings.max_slots,
            "labels": settings.worker_labels,
        },
    )
    payload = response.json()
    status = payload.get("status")
    _worker_registration_expires_at = now + max(settings.worker_registration_ttl_seconds, 1.0)
    return status if isinstance(status, str) else None


def _require_execution_context(
    *,
    run_id: str,
    run_kind: str,
    execution_context: dict[str, object] | None,
) -> dict[str, object]:
    if execution_context is None:
        raise RuntimeError(f"Execution context is not available for run {run_id}")
    if run_kind not in SUPPORTED_RUN_KINDS:
        raise RuntimeError(f"Unsupported run_kind={run_kind}")

    context_run_kind = execution_context.get("run_kind")
    if context_run_kind != run_kind:
        raise RuntimeError(
            f"Execution context run_kind mismatch for run {run_id}: "
            f"context={context_run_kind}, run={run_kind}"
        )
    code_api_mode = execution_context.get("code_api_mode")
    if code_api_mode not in SUPPORTED_CODE_API_MODES:
        raise RuntimeError(f"Unsupported code_api_mode={code_api_mode}")
    return execution_context


def _get_execution_context(client: httpx.Client, run_id: str) -> dict[str, object] | None:
    try:
        response = _request_with_retry(
            client=client,
            method="GET",
            url=f"{settings.backend_api_url}/internal/runs/{run_id}/execution-context",
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    return response.json()


def _execute_manifest_game(context: dict[str, object]) -> dict[str, object]:
    package_dir_raw = context.get("game_package_dir")
    entrypoint_raw = context.get("engine_entrypoint")
    if not isinstance(package_dir_raw, str) or not isinstance(entrypoint_raw, str):
        raise RuntimeError("Execution context is missing game package or engine entrypoint")

    games_root = Path(settings.games_root).resolve()
    package_dir = (games_root / package_dir_raw).resolve()
    engine_path = (package_dir / entrypoint_raw).resolve()
    if games_root not in engine_path.parents or not engine_path.is_file():
        raise RuntimeError(f"Engine entrypoint is not available: {entrypoint_raw}")

    if settings.execution_mode == "docker":
        return _execute_manifest_game_in_docker(
            package_dir=package_dir,
            entrypoint=entrypoint_raw,
            context=context,
        )
    if settings.execution_mode == "local_process":
        return _execute_manifest_game_locally(
            package_dir=package_dir,
            engine_path=engine_path,
            context=context,
        )

    raise RuntimeError(f"Unsupported execution mode: {settings.execution_mode}")


def _execute_manifest_game_locally(
    package_dir: Path,
    engine_path: Path,
    context: dict[str, object],
) -> dict[str, object]:
    env = os.environ.copy()
    env["AGP_RUN_CONTEXT"] = json.dumps(context, ensure_ascii=False)
    completed = subprocess.run(
        [sys.executable, str(engine_path)],
        cwd=str(package_dir),
        env=env,
        text=True,
        capture_output=True,
        timeout=_engine_timeout_seconds(),
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"Game engine exited with {completed.returncode}: {stderr}")

    return _parse_engine_payload(completed.stdout)


def _execute_manifest_game_in_docker(
    package_dir: Path,
    entrypoint: str,
    context: dict[str, object],
) -> dict[str, object]:
    package_archive = _build_package_archive(package_dir)
    context_json = json.dumps(context, ensure_ascii=False)

    command = [
        settings.docker_binary,
        "run",
        "--rm",
        "-i",
        "--log-driver",
        settings.docker_log_driver,
        "--log-opt",
        f"max-size={settings.docker_log_max_size}",
        "--log-opt",
        f"max-file={settings.docker_log_max_file}",
        "--network",
        settings.docker_network_mode,
        "--cpus",
        settings.docker_cpu_limit,
        "--memory",
        settings.docker_memory_limit,
        "--pids-limit",
        str(settings.docker_pids_limit),
        "--read-only",
        "--tmpfs",
        f"/tmp:size={settings.docker_tmpfs_size}",
        "--tmpfs",
        f"/workspace:size={settings.docker_tmpfs_size}",
        "-e",
        f"AGP_RUN_CONTEXT={context_json}",
        settings.docker_image,
        "/bin/sh",
        "-c",
        (
            "set -eu; "
            "mkdir -p /workspace/game; "
            "tar -xzf - -C /workspace/game; "
            "cd /workspace/game; "
            'python "$1"'
        ),
        "sh",
        entrypoint,
    ]
    try:
        completed = subprocess.run(
            command,
            input=package_archive,
            capture_output=True,
            timeout=_engine_timeout_seconds(),
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Docker binary not found: {settings.docker_binary}") from exc

    stdout_text = completed.stdout.decode("utf-8", errors="replace")
    stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0:
        raise RuntimeError(
            "Game engine in docker failed "
            f"(exit_code={completed.returncode}, image={settings.docker_image}): {stderr_text}"
        )
    return _parse_engine_payload(stdout_text)


def _engine_timeout_seconds() -> float:
    configured_timeout = float(settings.execution_timeout_seconds)
    hard_cap = float(settings.engine_timeout_cap_seconds)
    return max(0.1, min(configured_timeout, hard_cap))


def _build_package_archive(package_dir: Path) -> bytes:
    cache_key = str(package_dir)
    cached = _package_archive_cache.get(cache_key)
    if cached is not None:
        return cached
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(package_dir)
            if relative.parts and relative.parts[0].startswith("."):
                continue
            archive.add(path, arcname=str(relative))
    result = buffer.getvalue()
    _package_archive_cache[cache_key] = result
    return result


def _parse_engine_payload(stdout: str) -> dict[str, object]:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise RuntimeError("Game engine must print a JSON object")
        return _enforce_result_turn_limit(parsed)
    raise RuntimeError("Game engine did not print result payload")


def _enforce_result_turn_limit(payload: dict[str, object]) -> dict[str, object]:
    max_turns = max(int(settings.result_max_turns), 0)
    frames = payload.get("frames")
    if not isinstance(frames, list):
        return payload

    kept_frames: list[object] = []
    dropped_frames = 0
    final_frame: object | None = None
    for frame in frames:
        if isinstance(frame, dict) and frame.get("phase") == "finished":
            final_frame = frame

        tick = _frame_tick(frame)
        if tick is None or tick <= max_turns:
            kept_frames.append(frame)
        else:
            dropped_frames += 1

    if final_frame is not None and final_frame not in kept_frames:
        if isinstance(final_frame, dict):
            capped_final = dict(final_frame)
            capped_final["tick"] = max_turns
            kept_frames.append(capped_final)
        else:
            kept_frames.append(final_frame)

    if dropped_frames <= 0:
        return payload

    payload = dict(payload)
    payload["frames"] = kept_frames
    payload["metrics"] = _metrics_with_turn_limit(
        payload.get("metrics"),
        max_turns=max_turns,
        dropped_frames=dropped_frames,
    )
    payload["events"] = _events_with_turn_limit(
        payload.get("events"),
        max_turns=max_turns,
        dropped_frames=dropped_frames,
    )
    return payload


def _frame_tick(frame: object) -> int | None:
    if not isinstance(frame, dict):
        return None

    tick = frame.get("tick")
    if isinstance(tick, bool):
        return None
    if isinstance(tick, int):
        return tick
    if isinstance(tick, float) and tick.is_integer():
        return int(tick)
    return None


def _metrics_with_turn_limit(raw_metrics: object, *, max_turns: int, dropped_frames: int) -> dict[str, object]:
    metrics = dict(raw_metrics) if isinstance(raw_metrics, dict) else {}
    metrics["turn_limit_enforced"] = True
    metrics["max_turns"] = min(int(metrics.get("max_turns", max_turns)), max_turns)
    metrics["result_max_turns"] = max_turns
    metrics["dropped_frames"] = dropped_frames
    return metrics


def _events_with_turn_limit(raw_events: object, *, max_turns: int, dropped_frames: int) -> list[object]:
    raw_items = raw_events if isinstance(raw_events, list) else []
    events: list[object] = []
    dropped_events = 0
    for event in raw_items:
        tick = _frame_tick(event)
        if tick is None or tick <= max_turns:
            events.append(event)
        else:
            dropped_events += 1

    events.append(
        {
            "type": "turn_limit_enforced",
            "tick": max_turns,
            "message": f"Игра принудительно ограничена {max_turns} ходами.",
            "dropped_frames": dropped_frames,
            "dropped_events": dropped_events,
        }
    )
    return events


def _best_effort_report_failed(client: httpx.Client, run_id: str, lease_id: str, error: str) -> bool:
    try:
        _request_with_retry(
            client=client,
            method="POST",
            url=f"{settings.backend_api_url}/internal/runs/{run_id}/failed",
            json_payload={"message": error[:3000], "lease_id": lease_id},
        )
        return True
    except httpx.HTTPError:
        return False


def _best_effort_ack_scheduler(client: httpx.Client, run_id: str, lease_id: str) -> bool:
    try:
        _request_with_retry(
            client=client,
            method="POST",
            url=f"{settings.scheduler_url}/internal/runs/ack-finished",
            json_payload={
                "worker_id": settings.worker_id,
                "run_id": run_id,
                "lease_id": lease_id,
            },
        )
        return True
    except httpx.HTTPError:
        return False


def _best_effort_send_worker_heartbeat(
    client: httpx.Client,
    capacity_available: int,
    *,
    force: bool = False,
) -> str | None:
    global _worker_heartbeat_expires_at
    now = time.monotonic()
    if not force and now < _worker_heartbeat_expires_at:
        return None
    try:
        response = _request_with_retry(
            client=client,
            method="POST",
            url=f"{settings.backend_api_url}/internal/workers/{settings.worker_id}/heartbeat",
            json_payload={"capacity_available": capacity_available},
        )
        payload = response.json()
        status = payload.get("status")
        _worker_heartbeat_expires_at = now + max(settings.worker_heartbeat_interval_seconds, 0.1)
        return status if isinstance(status, str) else None
    except httpx.HTTPError:
        return None


def _is_worker_pull_allowed(worker_status: str | None) -> bool:
    return worker_status in {None, "online"}


def _request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    json_payload: dict[str, object] | None = None,
) -> httpx.Response:
    attempts = max(settings.request_max_attempts, 1)
    base_delay_seconds = max(settings.retry_base_delay_ms, 0) / 1000.0
    max_delay_seconds = max(settings.retry_max_delay_ms, 0) / 1000.0

    for attempt in range(attempts):
        try:
            headers = _headers_for_request(url)
            if method == "GET":
                response = client.get(url, headers=headers)
            elif method == "POST":
                response = client.post(url, json=json_payload, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            is_last_attempt = attempt == attempts - 1
            if is_last_attempt or not _is_retryable_http_error(exc):
                raise

            delay = min(base_delay_seconds * (2**attempt), max_delay_seconds)
            if delay > 0:
                time.sleep(delay)

    raise RuntimeError("Unreachable retry state")


def _headers_for_request(url: str) -> dict[str, str] | None:
    if url.startswith(f"{settings.backend_api_url.rstrip('/')}/internal/"):
        return {"X-Internal-Token": settings.internal_api_token}
    return None


def _is_retryable_http_error(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code >= 500 or status_code in {408, 425, 429}
    return True


def _is_stale_backend_run_error(exc: httpx.HTTPError) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    request_url = str(exc.request.url)
    if not request_url.startswith(f"{settings.backend_api_url.rstrip('/')}/internal/runs/"):
        return False
    return exc.response.status_code in {404, 409, 422}
