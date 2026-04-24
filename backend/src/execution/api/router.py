from __future__ import annotations

import json
import time
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, StreamingResponse

from app.auth import require_roles
from app.dependencies import ServiceContainer, get_container, get_games_root
from execution.api.schemas import (
    AcceptRunRequest,
    BuildResponse,
    CreateRunRequest,
    FailBuildRequest,
    FailRunRequest,
    FinishBuildRequest,
    FinishRunRequest,
    RegisterWorkerRequest,
    RunExecutionContextResponse,
    SingleTaskAttemptLogsResponse,
    RunWatchContextResponse,
    RunResponse,
    StartSingleTaskRunRequest,
    StartBuildRequest,
    StartRunRequest,
    StopSingleTaskRunRequest,
    UpdateWorkerStatusRequest,
    WorkerHeartbeatRequest,
    WorkerResponse,
)
from execution.domain.model import BuildJob, Run, RunKind, RunStatus, WorkerNode
from game_catalog.infrastructure.manifest_loader import GameManifest, find_game_manifest_path, load_game_manifest
from identity.domain.model import UserRole
from shared.api.sse import sse_envelope, sse_event
from shared.kernel import InvariantViolationError, NotFoundError

router = APIRouter(tags=["execution"])
_TERMINAL_RUN_STATUSES = {
    RunStatus.FINISHED,
    RunStatus.FAILED,
    RunStatus.TIMEOUT,
    RunStatus.CANCELED,
}


def _run_response(run: Run) -> RunResponse:
    return RunResponse(
        run_id=run.run_id,
        team_id=run.team_id,
        game_id=run.game_id,
        requested_by=run.requested_by,
        run_kind=run.run_kind,
        lobby_id=run.lobby_id,
        target_version_id=run.target_version_id,
        status=run.status,
        snapshot_id=run.snapshot_id,
        snapshot_version_id=run.snapshot_version_id,
        worker_id=run.worker_id,
        revisions_by_slot=run.revisions_by_slot,
        result_payload=run.result_payload,
        error_message=run.error_message,
        created_at=run.created_at,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _worker_response(worker: WorkerNode) -> WorkerResponse:
    return WorkerResponse(
        worker_id=worker.worker_id,
        hostname=worker.hostname,
        capacity_total=worker.capacity_total,
        capacity_available=worker.capacity_available,
        status=worker.status,
        labels=worker.labels,
    )


def _build_response(build: BuildJob) -> BuildResponse:
    return BuildResponse(
        build_id=build.build_id,
        game_source_id=build.game_source_id,
        repo_url=build.repo_url,
        status=build.status,
        image_digest=build.image_digest,
        error_message=build.error_message,
    )


def _resolve_manifest_for_slug(game_slug: str) -> tuple[Path, GameManifest]:
    games_root = get_games_root()
    manifest_path = find_game_manifest_path(games_root=games_root, game_id=game_slug)
    manifest = load_game_manifest(manifest_path)
    return manifest_path, manifest


def _resolve_renderer_asset_path(
    game_slug: str,
    asset_path: str,
) -> Path:
    manifest_path, manifest = _resolve_manifest_for_slug(game_slug=game_slug)
    if not manifest.renderer_entrypoint:
        raise NotFoundError(f"Renderer не поддерживается для игры {game_slug}")

    requested = PurePosixPath(asset_path)
    if requested.is_absolute() or ".." in requested.parts:
        raise NotFoundError("Renderer asset не найден")

    package_root = manifest_path.parent.resolve()
    renderer_root = (package_root / Path(manifest.renderer_entrypoint).parent).resolve()
    candidate = (package_root / Path(asset_path)).resolve()
    if not candidate.is_file():
        raise NotFoundError("Renderer asset не найден")
    if renderer_root != candidate and renderer_root not in candidate.parents:
        raise NotFoundError("Renderer asset не найден")
    return candidate


@router.post("/runs", response_model=RunResponse)
def create_run(
    request: CreateRunRequest,
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.create_run(
        data=container.execution_create_run_input(
            team_id=request.team_id,
            game_id=request.game_id,
            requested_by=request.requested_by,
            run_kind=request.run_kind,
            lobby_id=request.lobby_id,
            version_id=request.version_id,
        )
    )
    return _run_response(run)


@router.post("/single-tasks/{game_id}/run", response_model=RunResponse)
def start_single_task_run(
    game_id: str,
    request: StartSingleTaskRunRequest,
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.create_run(
        data=container.execution_create_run_input(
            team_id=request.team_id,
            game_id=game_id,
            requested_by=request.requested_by,
            run_kind=RunKind.SINGLE_TASK,
            lobby_id=None,
            version_id=None,
        )
    )
    queued = container.execution.queue_run(run_id=run.run_id)
    return _run_response(queued)


@router.post("/single-tasks/{game_id}/stop", response_model=RunResponse)
def stop_single_task_run(
    game_id: str,
    request: StopSingleTaskRunRequest,
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.get_run(run_id=request.run_id)
    if run.run_kind is not RunKind.SINGLE_TASK:
        raise InvariantViolationError("Остановка single_task доступна только для single_task попытки")
    if run.game_id != game_id:
        raise InvariantViolationError("run_id не принадлежит указанной single_task игре")
    return _run_response(
        container.execution.cancel_run(
            run_id=request.run_id,
            message="manual_stop_single_task",
        )
    )


@router.get("/single-tasks/{game_id}/attempts", response_model=list[RunResponse])
def list_single_task_attempts(
    game_id: str,
    requested_by: str | None = None,
    status: RunStatus | None = None,
    limit: int = 20,
    offset: int = 0,
    container: ServiceContainer = Depends(get_container),
) -> list[RunResponse]:
    bounded_limit = max(1, min(limit, 200))
    bounded_offset = max(0, offset)
    runs = container.execution.list_runs(game_id=game_id, run_kind=RunKind.SINGLE_TASK)
    runs.sort(key=lambda run: run.created_at, reverse=True)
    if requested_by is not None and requested_by.strip():
        requested = requested_by.strip()
        runs = [run for run in runs if run.requested_by == requested]
    if status is not None:
        runs = [run for run in runs if run.status is status]
    return [_run_response(run) for run in runs[bounded_offset : bounded_offset + bounded_limit]]


@router.get("/single-task-attempts/{attempt_id}", response_model=RunResponse)
def get_single_task_attempt(
    attempt_id: str,
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.get_run(run_id=attempt_id)
    if run.run_kind is not RunKind.SINGLE_TASK:
        raise InvariantViolationError("attempt_id не относится к single_task попытке")
    return _run_response(run)


@router.get("/single-task-attempts/{attempt_id}/logs", response_model=SingleTaskAttemptLogsResponse)
def get_single_task_attempt_logs(
    attempt_id: str,
    container: ServiceContainer = Depends(get_container),
) -> SingleTaskAttemptLogsResponse:
    run = container.execution.get_run(run_id=attempt_id)
    if run.run_kind is not RunKind.SINGLE_TASK:
        raise InvariantViolationError("attempt_id не относится к single_task попытке")
    result_payload = run.result_payload if isinstance(run.result_payload, dict) else {}
    metrics = result_payload.get("metrics")
    compile_error = ""
    if isinstance(metrics, dict):
        candidate = metrics.get("compile_error")
        if isinstance(candidate, str):
            compile_error = candidate.strip()
    lines = [f"compile_error: {compile_error}"] if compile_error else []
    return SingleTaskAttemptLogsResponse(attempt_id=attempt_id, lines=lines)


@router.get("/runs", response_model=list[RunResponse])
def list_runs(
    team_id: str | None = None,
    game_id: str | None = None,
    lobby_id: str | None = None,
    run_kind: RunKind | None = None,
    status: RunStatus | None = None,
    container: ServiceContainer = Depends(get_container),
) -> list[RunResponse]:
    runs = container.execution.list_runs(
        team_id=team_id,
        game_id=game_id,
        lobby_id=lobby_id,
        run_kind=run_kind,
        status=status,
    )
    return [_run_response(run) for run in runs]


@router.post("/runs/{run_id}/queue", response_model=RunResponse)
def queue_run(run_id: str, container: ServiceContainer = Depends(get_container)) -> RunResponse:
    return _run_response(container.execution.queue_run(run_id=run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
def cancel_run(run_id: str, container: ServiceContainer = Depends(get_container)) -> RunResponse:
    return _run_response(
        container.execution.cancel_run(
            run_id=run_id,
            message="manual_cancel",
        )
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str, container: ServiceContainer = Depends(get_container)) -> RunResponse:
    return _run_response(container.execution.get_run(run_id=run_id))


@router.get("/runs/{run_id}/watch-context", response_model=RunWatchContextResponse)
def get_run_watch_context(
    run_id: str,
    container: ServiceContainer = Depends(get_container),
) -> RunWatchContextResponse:
    run = container.execution.get_run(run_id=run_id)
    game = container.game_catalog.get_game(run.game_id)
    _, manifest = _resolve_manifest_for_slug(game_slug=game.slug)

    renderer_entrypoint = manifest.renderer_entrypoint
    renderer_url = None
    if renderer_entrypoint:
        renderer_url = f"/api/v1/renderers/{game.slug}/{renderer_entrypoint}"

    return RunWatchContextResponse(
        run_id=run.run_id,
        game_id=run.game_id,
        game_slug=game.slug,
        run_kind=run.run_kind,
        status=run.status,
        renderer_entrypoint=renderer_entrypoint,
        renderer_url=renderer_url,
        renderer_protocol="v1",
    )


@router.get("/runs/{run_id}/stream")
def stream_run(
    run_id: str,
    poll_interval_ms: int = 1000,
    max_events: int = 0,
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    interval = max(50, min(poll_interval_ms, 10_000)) / 1000
    max_events_bounded = max(0, min(max_events, 10_000))

    def _events():
        emitted = 0
        last_payload_signature = ""
        while True:
            run = container.execution.get_run(run_id=run_id)
            payload = _run_response(run).model_dump(mode="json")
            signature = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if signature != last_payload_signature:
                last_payload_signature = signature
                yield sse_event(
                    "agp.update",
                    sse_envelope(
                        channel="run",
                        entity_id=run.run_id,
                        kind="snapshot",
                        payload=payload,
                        status=run.status.value,
                    ),
                )
                emitted += 1
                if max_events_bounded > 0 and emitted >= max_events_bounded:
                    break
                if run.status in _TERMINAL_RUN_STATUSES:
                    yield sse_event(
                        "agp.terminal",
                        sse_envelope(
                            channel="run",
                            entity_id=run.run_id,
                            kind="terminal",
                            payload={"run_id": run.run_id},
                            status=run.status.value,
                        ),
                    )
                    break
            else:
                yield sse_event(
                    "agp.keepalive",
                    sse_envelope(channel="run", entity_id=run_id, kind="keepalive"),
                )
            time.sleep(interval)

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/renderers/{game_slug}/{asset_path:path}")
def get_renderer_asset(game_slug: str, asset_path: str) -> FileResponse:
    return FileResponse(_resolve_renderer_asset_path(game_slug=game_slug, asset_path=asset_path))


@router.get("/internal/runs/{run_id}/execution-context", response_model=RunExecutionContextResponse)
def get_run_execution_context(
    run_id: str,
    container: ServiceContainer = Depends(get_container),
) -> RunExecutionContextResponse:
    run = container.execution.get_run(run_id=run_id)
    if run.snapshot_id is None or run.snapshot_version_id is None:
        raise InvariantViolationError("Execution context доступен только для queued/running запуска")

    game = container.game_catalog.get_game(run.game_id)
    snapshot = container.team_workspace.get_snapshot(run.snapshot_id)
    games_root = get_games_root()
    manifest_path = find_game_manifest_path(games_root=games_root, game_id=game.slug)
    manifest = load_game_manifest(manifest_path)

    return RunExecutionContextResponse(
        run_id=run.run_id,
        team_id=run.team_id,
        run_kind=run.run_kind,
        game_id=run.game_id,
        game_slug=game.slug,
        game_package_dir=manifest_path.parent.name,
        code_api_mode=manifest.code_api_mode,
        engine_entrypoint=manifest.engine_entrypoint,
        renderer_entrypoint=manifest.renderer_entrypoint,
        snapshot_id=snapshot.snapshot_id,
        snapshot_version_id=snapshot.version_id,
        codes_by_slot=snapshot.codes_by_slot,
        revisions_by_slot=snapshot.revisions_by_slot,
    )


@router.post("/internal/workers/register", response_model=WorkerResponse)
def register_worker(
    request: RegisterWorkerRequest,
    container: ServiceContainer = Depends(get_container),
) -> WorkerResponse:
    worker = container.execution.register_worker(
        data=container.execution_register_worker_input(
            worker_id=request.worker_id,
            hostname=request.hostname,
            capacity_total=request.capacity_total,
            labels=request.labels,
        )
    )
    return _worker_response(worker)


@router.post("/internal/workers/{worker_id}/heartbeat", response_model=WorkerResponse)
def heartbeat_worker(
    worker_id: str,
    request: WorkerHeartbeatRequest,
    container: ServiceContainer = Depends(get_container),
) -> WorkerResponse:
    worker = container.execution.worker_heartbeat(
        worker_id=worker_id,
        capacity_available=request.capacity_available,
    )
    return _worker_response(worker)


@router.patch("/internal/workers/{worker_id}/status", response_model=WorkerResponse)
def update_worker_status(
    worker_id: str,
    request: UpdateWorkerStatusRequest,
    container: ServiceContainer = Depends(get_container),
) -> WorkerResponse:
    worker = container.execution.update_worker_status(
        data=container.execution_update_worker_status_input(
            worker_id=worker_id,
            status=request.status,
        )
    )
    return _worker_response(worker)


@router.get("/internal/workers", response_model=list[WorkerResponse])
def list_workers(container: ServiceContainer = Depends(get_container)) -> list[WorkerResponse]:
    return [_worker_response(worker) for worker in container.execution.list_workers()]


@router.get("/workers", response_model=list[WorkerResponse])
def list_workers_public(
    _: object = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> list[WorkerResponse]:
    return [_worker_response(worker) for worker in container.execution.list_workers()]


@router.get("/workers/{worker_id}", response_model=WorkerResponse)
def get_worker_public(
    worker_id: str,
    _: object = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> WorkerResponse:
    return _worker_response(container.execution.get_worker(worker_id=worker_id))


@router.patch("/workers/{worker_id}/status", response_model=WorkerResponse)
def update_worker_status_public(
    worker_id: str,
    request: UpdateWorkerStatusRequest,
    _: object = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> WorkerResponse:
    worker = container.execution.update_worker_status(
        data=container.execution_update_worker_status_input(
            worker_id=worker_id,
            status=request.status,
        )
    )
    return _worker_response(worker)


@router.post("/internal/runs/{run_id}/started", response_model=RunResponse)
def mark_run_started(
    run_id: str,
    request: StartRunRequest,
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.start_run(run_id=run_id, worker_id=request.worker_id)
    return _run_response(run)


@router.post("/internal/runs/{run_id}/accepted", response_model=RunResponse)
def mark_run_accepted(
    run_id: str,
    request: AcceptRunRequest,
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.accept_run(run_id=run_id, worker_id=request.worker_id)
    return _run_response(run)


@router.post("/internal/runs/{run_id}/finished", response_model=RunResponse)
def mark_run_finished(
    run_id: str,
    request: FinishRunRequest,
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.finish_run(run_id=run_id, payload=request.payload)
    return _run_response(run)


@router.post("/internal/runs/{run_id}/failed", response_model=RunResponse)
def mark_run_failed(
    run_id: str,
    request: FailRunRequest,
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.fail_run(run_id=run_id, message=request.message)
    return _run_response(run)


@router.post("/internal/builds/start", response_model=BuildResponse)
def start_build(
    request: StartBuildRequest,
    container: ServiceContainer = Depends(get_container),
) -> BuildResponse:
    build = container.execution.start_build(
        game_source_id=request.game_source_id,
        repo_url=request.repo_url,
    )
    return _build_response(build)


@router.post("/internal/builds/{build_id}/finished", response_model=BuildResponse)
def finish_build(
    build_id: str,
    request: FinishBuildRequest,
    container: ServiceContainer = Depends(get_container),
) -> BuildResponse:
    build = container.execution.finish_build(build_id=build_id, image_digest=request.image_digest)
    return _build_response(build)


@router.post("/internal/builds/{build_id}/failed", response_model=BuildResponse)
def fail_build(
    build_id: str,
    request: FailBuildRequest,
    container: ServiceContainer = Depends(get_container),
) -> BuildResponse:
    build = container.execution.fail_build(build_id=build_id, error_message=request.error_message)
    return _build_response(build)
