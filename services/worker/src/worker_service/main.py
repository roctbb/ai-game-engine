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
    global _auto_poll_stop_event, _auto_poll_task
    if not settings.auto_poll_enabled:
        return
    _auto_poll_stop_event = asyncio.Event()
    _auto_poll_task = asyncio.create_task(_auto_poll_loop(_auto_poll_stop_event))


@app.on_event("shutdown")
async def stop_auto_poll_loop() -> None:
    global _auto_poll_stop_event, _auto_poll_task
    if _auto_poll_stop_event is not None:
        _auto_poll_stop_event.set()
    if _auto_poll_task is not None:
        _auto_poll_task.cancel()
        with suppress(asyncio.CancelledError):
            await _auto_poll_task
    _auto_poll_stop_event = None
    _auto_poll_task = None


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
    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
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
            _best_effort_send_worker_heartbeat(
                client=client,
                capacity_available=settings.max_slots,
            )
            return {
                "worker_id": settings.worker_id,
                "status": "idle",
            }

        _best_effort_send_worker_heartbeat(
            client=client,
            capacity_available=max(settings.max_slots - 1, 0),
        )
        try:
            run_info_response = _request_with_retry(
                client=client,
                method="GET",
                url=f"{settings.backend_api_url}/runs/{run_id}",
            )
            run_info = run_info_response.json()
            run_kind_raw = run_info.get("run_kind")
            if not isinstance(run_kind_raw, str):
                raise RuntimeError("Run payload is missing run_kind")
            execution_context = _get_execution_context(client=client, run_id=run_id)
            resolved_context = _require_execution_context(
                run_id=run_id,
                run_kind=run_kind_raw,
                execution_context=execution_context,
            )

            _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.backend_api_url}/internal/runs/{run_id}/accepted",
                json_payload={"worker_id": settings.worker_id},
            )

            _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.backend_api_url}/internal/runs/{run_id}/started",
                json_payload={"worker_id": settings.worker_id},
            )

            payload = _execute_manifest_game(resolved_context)

            _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.backend_api_url}/internal/runs/{run_id}/finished",
                json_payload={"payload": payload},
            )

            _request_with_retry(
                client=client,
                method="POST",
                url=f"{settings.scheduler_url}/internal/runs/ack-finished",
                json_payload={
                    "worker_id": settings.worker_id,
                    "run_id": run_id,
                },
            )
        except httpx.HTTPError as exc:
            _best_effort_report_failed(client=client, run_id=run_id, error=str(exc))
            raise HTTPException(status_code=502, detail=f"Worker execution failed for run {run_id}") from exc
        except Exception as exc:
            _best_effort_report_failed(client=client, run_id=run_id, error=str(exc))
            raise HTTPException(status_code=500, detail=f"Worker execution failed for run {run_id}") from exc
        finally:
            _best_effort_send_worker_heartbeat(
                client=client,
                capacity_available=settings.max_slots,
            )

        return {
            "worker_id": settings.worker_id,
            "status": "completed",
            "run_id": run_id,
        }


def _ensure_worker_registered(client: httpx.Client) -> str | None:
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
        timeout=settings.execution_timeout_seconds,
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
            timeout=settings.execution_timeout_seconds,
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


def _build_package_archive(package_dir: Path) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(package_dir)
            if relative.parts and relative.parts[0].startswith("."):
                continue
            archive.add(path, arcname=str(relative))
    return buffer.getvalue()


def _parse_engine_payload(stdout: str) -> dict[str, object]:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise RuntimeError("Game engine must print a JSON object")
        return parsed
    raise RuntimeError("Game engine did not print result payload")


def _best_effort_report_failed(client: httpx.Client, run_id: str, error: str) -> None:
    try:
        _request_with_retry(
            client=client,
            method="POST",
            url=f"{settings.backend_api_url}/internal/runs/{run_id}/failed",
            json_payload={"message": error[:3000]},
        )
    except httpx.HTTPError:
        return


def _best_effort_send_worker_heartbeat(client: httpx.Client, capacity_available: int) -> str | None:
    try:
        response = _request_with_retry(
            client=client,
            method="POST",
            url=f"{settings.backend_api_url}/internal/workers/{settings.worker_id}/heartbeat",
            json_payload={"capacity_available": capacity_available},
        )
        payload = response.json()
        status = payload.get("status")
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
            if method == "GET":
                response = client.get(url)
            elif method == "POST":
                response = client.post(url, json=json_payload)
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


def _is_retryable_http_error(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code >= 500 or status_code in {408, 425, 429}
    return True
