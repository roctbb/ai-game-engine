from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.auth import get_current_session, require_internal_token, require_roles
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
from execution.api.access import ensure_can_view_run
from execution.domain.model import BuildJob, Run, RunKind, RunStatus, WorkerNode
from execution.domain.result_payload import compact_result_payload as compact_run_result_payload
from game_catalog.infrastructure.manifest_loader import GameManifest, find_game_manifest_path, load_game_manifest
from identity.domain.model import AppSession, UserRole
from shared.api.sse import sse_envelope, sse_event, sse_payload_hash
from shared.kernel import ForbiddenError, InvariantViolationError, NotFoundError

router = APIRouter(tags=["execution"])
_TERMINAL_RUN_STATUSES = {
    RunStatus.FINISHED,
    RunStatus.FAILED,
    RunStatus.TIMEOUT,
    RunStatus.CANCELED,
}

def _run_response(run: Run, *, compact_result_payload: bool = False) -> RunResponse:
    return RunResponse(
        run_id=run.run_id,
        team_id=run.team_id,
        game_id=run.game_id,
        requested_by=run.requested_by,
        run_kind=run.run_kind,
        lobby_id=run.lobby_id,
        target_version_id=run.target_version_id,
        match_execution_id=run.match_execution_id,
        match_primary_run_id=run.match_primary_run_id,
        status=run.status,
        snapshot_id=run.snapshot_id,
        snapshot_version_id=run.snapshot_version_id,
        worker_id=run.worker_id,
        revisions_by_slot=run.revisions_by_slot,
        result_payload=compact_run_result_payload(run.result_payload) if compact_result_payload else run.result_payload,
        error_message=run.error_message,
        created_at=run.created_at,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _attach_replay_summary_payload_if_available(
    *,
    container: ServiceContainer,
    run: Run,
) -> Run:
    if run.result_payload is not None or run.status not in _TERMINAL_RUN_STATUSES:
        return run
    try:
        replay = container.spectator_replay.get_by_run_id(
            run.run_id,
            include_content=False,
        )
    except NotFoundError:
        return run
    return replace(run, result_payload=dict(replay.summary))


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


def _ensure_can_use_team(container: ServiceContainer, session: AppSession, team_id: str) -> None:
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        return
    team = container.team_workspace.get_team(team_id)
    if team.captain_user_id != session.nickname:
        raise ForbiddenError("Запускать код этой команды может только капитан, преподаватель или админ")


def _ensure_can_manage_run(container: ServiceContainer, session: AppSession, run: Run) -> None:
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        return
    if run.requested_by != session.nickname:
        raise ForbiddenError("Управлять этим запуском может только его автор, преподаватель или админ")


def _reconcile_training_lobby_for_terminal_run(container: ServiceContainer, run: Run) -> None:
    if run.run_kind is not RunKind.TRAINING_MATCH or run.lobby_id is None:
        return
    try:
        lobby = container.training_lobby.reconcile_training_lobby_status(lobby_id=run.lobby_id)
        if lobby.status.value in {"open", "running"}:
            container.training_lobby.run_matchmaking_cycle(
                lobby_id=run.lobby_id,
                requested_by="system",
            )
    except NotFoundError:
        return
    except InvariantViolationError:
        return


def _advance_competition_for_terminal_run(container: ServiceContainer, run: Run) -> None:
    if run.run_kind is not RunKind.COMPETITION_MATCH or run.lobby_id is None:
        return
    try:
        container.competition.advance_competition(
            competition_id=run.lobby_id,
            requested_by="system",
        )
    except NotFoundError:
        return
    except InvariantViolationError:
        return


@router.post("/runs", response_model=RunResponse)
def create_run(
    request: CreateRunRequest,
    session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    _ensure_can_use_team(container=container, session=session, team_id=request.team_id)
    requested_by = request.requested_by if session.role in {UserRole.TEACHER, UserRole.ADMIN} else session.nickname
    run = container.execution.create_run(
        data=container.execution_create_run_input(
            team_id=request.team_id,
            game_id=request.game_id,
            requested_by=requested_by,
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
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    _ensure_can_use_team(container=container, session=session, team_id=request.team_id)
    requested_by = request.requested_by if session.role in {UserRole.TEACHER, UserRole.ADMIN} else session.nickname
    run = container.execution.create_run(
        data=container.execution_create_run_input(
            team_id=request.team_id,
            game_id=game_id,
            requested_by=requested_by,
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
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.get_run(run_id=request.run_id)
    _ensure_can_manage_run(container=container, session=session, run=run)
    if run.run_kind is not RunKind.SINGLE_TASK:
        raise InvariantViolationError("Остановка single_task доступна только для single_task попытки")
    if run.game_id != game_id:
        raise InvariantViolationError("run_id не принадлежит указанной single_task игре")
    stopped = container.execution.cancel_run(
        run_id=request.run_id,
        message="manual_stop_single_task",
    )
    return _run_response(stopped)


@router.get("/single-tasks/{game_id}/attempts", response_model=list[RunResponse])
def list_single_task_attempts(
    game_id: str,
    requested_by: str | None = None,
    status: RunStatus | None = None,
    limit: int = 20,
    offset: int = 0,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[RunResponse]:
    bounded_limit = max(1, min(limit, 200))
    bounded_offset = max(0, offset)
    effective_requested_by: str | None = None
    if session.role not in {UserRole.TEACHER, UserRole.ADMIN}:
        effective_requested_by = session.nickname
    elif requested_by is not None and requested_by.strip():
        effective_requested_by = requested_by.strip()
    runs = container.execution.list_runs(
        game_id=game_id,
        run_kind=RunKind.SINGLE_TASK,
        status=status,
        requested_by=effective_requested_by,
        include_result_payload=False,
        limit=bounded_limit,
        offset=bounded_offset,
    )
    return [_run_response(run, compact_result_payload=True) for run in runs]


@router.get("/single-task-attempts/{attempt_id}", response_model=RunResponse)
def get_single_task_attempt(
    attempt_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.get_run(run_id=attempt_id)
    _ensure_can_manage_run(container=container, session=session, run=run)
    if run.run_kind is not RunKind.SINGLE_TASK:
        raise InvariantViolationError("attempt_id не относится к single_task попытке")
    return _run_response(run)


@router.get("/single-task-attempts/{attempt_id}/logs", response_model=SingleTaskAttemptLogsResponse)
def get_single_task_attempt_logs(
    attempt_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> SingleTaskAttemptLogsResponse:
    run = container.execution.get_run(run_id=attempt_id)
    _ensure_can_manage_run(container=container, session=session, run=run)
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
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[RunResponse]:
    runs = container.execution.list_runs(
        team_id=team_id,
        game_id=game_id,
        lobby_id=lobby_id,
        run_kind=run_kind,
        status=status,
        include_result_payload=False,
    )
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        return [_run_response(run, compact_result_payload=True) for run in runs]

    # Batch access check: preload teams and lobby memberships to avoid N+1
    user_id = session.nickname
    user_team_ids: set[str] = set()
    user_lobby_ids: set[str] = set()

    # Collect unique team_ids and lobby_ids from runs
    needed_team_ids = {run.team_id for run in runs}
    needed_lobby_ids = {run.lobby_id for run in runs if run.lobby_id}

    # Batch: check which teams the user captains
    for tid in needed_team_ids:
        try:
            team = container.team_workspace.get_team(tid)
            if team.captain_user_id == user_id:
                user_team_ids.add(tid)
        except NotFoundError:
            pass

    # Batch: check which lobbies the user is a member of
    for lid in needed_lobby_ids:
        try:
            if container.training_lobby.find_user_team_in_lobby(lobby_id=lid, user_id=user_id):
                user_lobby_ids.add(lid)
        except NotFoundError:
            pass

    # Batch: check competition entrants for competition_match runs
    competition_lobby_ids = {
        run.lobby_id for run in runs
        if run.run_kind is RunKind.COMPETITION_MATCH and run.lobby_id
    }
    user_competition_ids: set[str] = set()
    for comp_id in competition_lobby_ids:
        try:
            competition = container.competition.get_competition(comp_id)
            user_teams = container.team_workspace.list_teams_by_game_and_captain(
                game_id=competition.game_id if hasattr(competition, 'game_id') else runs[0].game_id,
                captain_user_id=user_id,
            )
            if any(t.team_id in competition.entrants for t in user_teams):
                user_competition_ids.add(comp_id)
            elif competition.lobby_id and competition.lobby_id in user_lobby_ids:
                user_competition_ids.add(comp_id)
        except NotFoundError:
            pass

    visible_runs: list[Run] = []
    for run in runs:
        if run.requested_by == user_id:
            visible_runs.append(run)
            continue
        if run.team_id in user_team_ids:
            visible_runs.append(run)
            continue
        if run.run_kind is RunKind.TRAINING_MATCH and run.lobby_id and run.lobby_id in user_lobby_ids:
            visible_runs.append(run)
            continue
        if run.run_kind is RunKind.COMPETITION_MATCH and run.lobby_id and run.lobby_id in user_competition_ids:
            visible_runs.append(run)
            continue

    return [_run_response(run, compact_result_payload=True) for run in visible_runs]


@router.post("/runs/{run_id}/queue", response_model=RunResponse)
def queue_run(
    run_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.get_run(run_id=run_id)
    _ensure_can_manage_run(container=container, session=session, run=run)
    return _run_response(container.execution.queue_run(run_id=run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
def cancel_run(
    run_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.get_run(run_id=run_id)
    _ensure_can_manage_run(container=container, session=session, run=run)
    canceled = container.execution.cancel_run(
        run_id=run_id,
        message="manual_cancel",
    )
    container.training_lobby.cancel_shadow_match_runs(primary_run=canceled, message="manual_cancel")
    _reconcile_training_lobby_for_terminal_run(container=container, run=canceled)
    return _run_response(canceled)


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    compact_payload: bool = False,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.get_run(
        run_id=run_id,
        include_result_payload=not compact_payload,
    )
    ensure_can_view_run(container=container, session=session, run=run)
    if compact_payload:
        run = _attach_replay_summary_payload_if_available(container=container, run=run)
    return _run_response(run, compact_result_payload=compact_payload)


@router.get("/runs/{run_id}/watch-context", response_model=RunWatchContextResponse)
def get_run_watch_context(
    run_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> RunWatchContextResponse:
    run = container.execution.get_run(run_id=run_id)
    ensure_can_view_run(container=container, session=session, run=run)
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
        game_title=game.title,
        run_kind=run.run_kind,
        status=run.status,
        renderer_entrypoint=renderer_entrypoint,
        renderer_url=renderer_url,
        renderer_protocol="v1",
        participants=_watch_context_participants(container=container, current_run=run),
    )


def _watch_context_participants(container: ServiceContainer, current_run: Run) -> list[dict[str, object]]:
    run_ids = _watch_context_run_ids(container=container, current_run=current_run)
    participants: list[dict[str, object]] = []
    seen_team_ids: set[str] = set()

    for participant_run_id in run_ids:
        try:
            participant_run = container.execution.get_run(participant_run_id)
        except NotFoundError:
            continue
        if participant_run.team_id in seen_team_ids:
            continue
        seen_team_ids.add(participant_run.team_id)
        participants.append(_participant_summary(container=container, run=participant_run, current_run_id=current_run.run_id))

    return participants


def _participant_summary(
    *,
    container: ServiceContainer,
    run: Run,
    current_run_id: str | None = None,
) -> dict[str, object]:
    try:
        team = container.team_workspace.get_team(run.team_id)
        display_name = team.name or team.captain_user_id or run.team_id
        captain_user_id = team.captain_user_id
    except NotFoundError:
        display_name = run.team_id
        captain_user_id = run.requested_by
    result: dict[str, object] = {
        "run_id": run.run_id,
        "team_id": run.team_id,
        "display_name": display_name,
        "captain_user_id": captain_user_id,
    }
    if current_run_id is not None:
        result["is_current"] = run.run_id == current_run_id
    return result


def _watch_context_run_ids(container: ServiceContainer, current_run: Run) -> list[str]:
    run_ids = [current_run.run_id]
    peer_ids: list[str] = []

    if current_run.run_kind is RunKind.COMPETITION_MATCH and current_run.lobby_id:
        peer_ids = _competition_watch_peer_run_ids(container=container, current_run=current_run)
    elif current_run.run_kind is RunKind.TRAINING_MATCH and current_run.lobby_id:
        peer_ids = _training_watch_peer_run_ids(container=container, current_run=current_run)

    for peer_id in peer_ids:
        if peer_id not in run_ids:
            run_ids.append(peer_id)
    return run_ids


def _competition_watch_peer_run_ids(container: ServiceContainer, current_run: Run) -> list[str]:
    if not current_run.lobby_id:
        return []
    try:
        competition = container.competition.get_competition(current_run.lobby_id)
    except NotFoundError:
        return []

    for round_item in competition.rounds:
        for match in round_item.matches:
            match_run_ids = [run_id for run_id in match.run_ids_by_team.values() if run_id]
            if current_run.run_id in match_run_ids:
                return [run_id for run_id in match_run_ids if run_id != current_run.run_id]
    return []


def _training_watch_peer_run_ids(container: ServiceContainer, current_run: Run) -> list[str]:
    if not current_run.lobby_id:
        return []
    try:
        lobby = container.training_lobby.get_lobby(current_run.lobby_id)
    except NotFoundError:
        return []

    for group in lobby.last_scheduled_match_groups:
        if current_run.run_id in group:
            return [run_id for run_id in group if run_id != current_run.run_id]

    stored_peer_ids = _stored_training_match_peer_run_ids(current_run)
    if stored_peer_ids:
        return stored_peer_ids

    peer_ids: list[str] = []
    if current_run.run_id in lobby.last_scheduled_run_ids:
        for run_id in lobby.last_scheduled_run_ids:
            if run_id != current_run.run_id:
                peer_ids.append(run_id)
    if peer_ids:
        return peer_ids

    lobby_runs = container.execution.list_runs(
        lobby_id=current_run.lobby_id,
        run_kind=RunKind.TRAINING_MATCH,
        include_result_payload=False,
    )
    game = container.game_catalog.get_game(current_run.game_id)
    max_players = game.match_player_bounds[1] if game.is_multiplayer else 2
    close_seconds = 2.0
    sorted_runs = sorted(
        (run for run in lobby_runs if run.game_id == current_run.game_id),
        key=lambda run: run.created_at.timestamp() if run.created_at else 0,
        reverse=True,
    )
    current_group: list[Run] = []
    groups: list[list[Run]] = []
    for candidate in sorted_runs:
        previous = current_group[-1] if current_group else None
        if previous is not None:
            if (
                len(current_group) >= max_players
                or candidate.created_at is None
                or previous.created_at is None
                or abs((previous.created_at - candidate.created_at).total_seconds()) > close_seconds
            ):
                groups.append(current_group)
                current_group = []
        current_group.append(candidate)
    if current_group:
        groups.append(current_group)

    for group in groups:
        if all(candidate.run_id != current_run.run_id for candidate in group):
            continue
        return [candidate.run_id for candidate in group if candidate.run_id != current_run.run_id]
    return []


def _stored_training_match_peer_run_ids(current_run: Run) -> list[str]:
    payload = current_run.result_payload if isinstance(current_run.result_payload, dict) else {}
    participants = payload.get("match_participants")
    if not isinstance(participants, list):
        return []
    peer_run_ids: list[str] = []
    for item in participants:
        if not isinstance(item, dict):
            continue
        run_id = item.get("run_id")
        if not isinstance(run_id, str) or not run_id or run_id == current_run.run_id:
            continue
        if run_id not in peer_run_ids:
            peer_run_ids.append(run_id)
    return peer_run_ids


@router.get("/runs/{run_id}/stream")
def stream_run(
    request: Request,
    run_id: str,
    poll_interval_ms: int = 1000,
    max_events: int = 0,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    initial_run = container.execution.get_run(run_id=run_id, include_result_payload=False)
    ensure_can_view_run(container=container, session=session, run=initial_run)
    interval = max(50, min(poll_interval_ms, 10_000)) / 1000
    max_events_bounded = max(0, min(max_events, 10_000))

    async def _events():
        emitted = 0
        last_payload_signature = ""

        def _build_payload() -> tuple[dict[str, object], str, str]:
            run = container.execution.get_run(run_id=run_id, include_result_payload=False)
            ensure_can_view_run(container=container, session=session, run=run)
            run = _attach_replay_summary_payload_if_available(container=container, run=run)
            return (
                _run_response(run, compact_result_payload=True).model_dump(mode="json"),
                run.status.value,
                run.run_id,
            )

        while True:
            if await request.is_disconnected():
                break
            payload, status, current_run_id = await run_in_threadpool(_build_payload)
            signature = sse_payload_hash(payload)
            if signature != last_payload_signature:
                last_payload_signature = signature
                yield sse_event(
                    "agp.update",
                    sse_envelope(
                        channel="run",
                        entity_id=current_run_id,
                        kind="snapshot",
                        payload=payload,
                        status=status,
                    ),
                )
                emitted += 1
                if max_events_bounded > 0 and emitted >= max_events_bounded:
                    break
                if status in {item.value for item in _TERMINAL_RUN_STATUSES}:
                    yield sse_event(
                        "agp.terminal",
                        sse_envelope(
                            channel="run",
                            entity_id=current_run_id,
                            kind="terminal",
                            payload={"run_id": current_run_id},
                            status=status,
                        ),
                    )
                    break
            else:
                yield sse_event(
                    "agp.keepalive",
                    sse_envelope(channel="run", entity_id=run_id, kind="keepalive"),
                )
            await asyncio.sleep(interval)

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
    _: object = Depends(require_internal_token),
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
        participants=_execution_context_participants(container=container, current_run_id=run.run_id),
    )


def _execution_context_participants(container: ServiceContainer, current_run_id: str) -> list[dict[str, object]]:
    run = container.execution.get_run(current_run_id)
    run_ids = [current_run_id]
    if run.lobby_id is not None and run.run_kind is RunKind.TRAINING_MATCH:
        lobby = container.training_lobby.get_lobby(run.lobby_id)
        scheduled_group: list[str] = []
        for group in lobby.last_scheduled_match_groups:
            if current_run_id not in group:
                continue
            scheduled_group = list(group)
            break
        if scheduled_group:
            run_ids = scheduled_group
        else:
            peer_ids: list[str] = []
            # Backward-compatible fallback for lobbies created before match groups existed.
            if current_run_id in lobby.last_scheduled_run_ids:
                for rid in list(lobby.last_scheduled_run_ids):
                    if rid == current_run_id:
                        continue
                    peer = container.execution.get_run(rid)
                    if peer.created_at and run.created_at and abs((peer.created_at - run.created_at).total_seconds()) < 2:
                        peer_ids.append(rid)
            if not peer_ids:
                lobby_runs = container.execution.list_runs(
                    lobby_id=run.lobby_id,
                    run_kind=RunKind.TRAINING_MATCH,
                    include_result_payload=False,
                )
                for peer in lobby_runs:
                    if peer.run_id == current_run_id:
                        continue
                    if peer.status not in {RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING}:
                        continue
                    if peer.created_at and run.created_at and abs((peer.created_at - run.created_at).total_seconds()) < 5:
                        peer_ids.append(peer.run_id)
            unsorted_run_ids = [current_run_id] + peer_ids
            fallback_at = run.created_at or run.queued_at or run.started_at or run.finished_at

            def run_order_key(run_id: str) -> tuple[str, str]:
                peer = container.execution.get_run(run_id)
                created_at = peer.created_at or fallback_at
                return (created_at.isoformat() if created_at is not None else "", run_id)

            run_ids = sorted(unsorted_run_ids, key=run_order_key)

    participants: list[dict[str, object]] = []
    seen: set[str] = set()
    for run_id in run_ids:
        participant_run = container.execution.get_run(run_id)
        if participant_run.snapshot_id is None:
            continue
        if participant_run.team_id in seen:
            continue
        seen.add(participant_run.team_id)
        team = container.team_workspace.get_team(participant_run.team_id)
        snapshot = container.team_workspace.get_snapshot(participant_run.snapshot_id)
        participants.append(
            {
                "run_id": participant_run.run_id,
                "team_id": participant_run.team_id,
                "display_name": team.name or team.captain_user_id,
                "captain_user_id": team.captain_user_id,
                "codes_by_slot": snapshot.codes_by_slot,
                "revisions_by_slot": snapshot.revisions_by_slot,
                "is_current": participant_run.run_id == current_run_id,
            }
        )
    return participants


@router.post("/internal/workers/register", response_model=WorkerResponse)
def register_worker(
    request: RegisterWorkerRequest,
    _: object = Depends(require_internal_token),
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
    _: object = Depends(require_internal_token),
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
    _: object = Depends(require_internal_token),
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
def list_workers(
    _: object = Depends(require_internal_token),
    container: ServiceContainer = Depends(get_container),
) -> list[WorkerResponse]:
    return [_worker_response(worker) for worker in container.execution.list_workers()]


@router.get("/workers", response_model=list[WorkerResponse])
def list_workers_public(
    _: object = Depends(require_roles(UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> list[WorkerResponse]:
    return [_worker_response(worker) for worker in container.execution.list_workers()]


@router.get("/workers/{worker_id}", response_model=WorkerResponse)
def get_worker_public(
    worker_id: str,
    _: object = Depends(require_roles(UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> WorkerResponse:
    return _worker_response(container.execution.get_worker(worker_id=worker_id))


@router.patch("/workers/{worker_id}/status", response_model=WorkerResponse)
def update_worker_status_public(
    worker_id: str,
    request: UpdateWorkerStatusRequest,
    _: object = Depends(require_roles(UserRole.ADMIN)),
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
    _: object = Depends(require_internal_token),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.start_run(run_id=run_id, worker_id=request.worker_id)
    return _run_response(run)


@router.post("/internal/runs/{run_id}/accepted", response_model=RunResponse)
def mark_run_accepted(
    run_id: str,
    request: AcceptRunRequest,
    _: object = Depends(require_internal_token),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.accept_run(run_id=run_id, worker_id=request.worker_id)
    return _run_response(run)


@router.post("/internal/runs/{run_id}/finished", response_model=RunResponse)
def mark_run_finished(
    run_id: str,
    request: FinishRunRequest,
    _: object = Depends(require_internal_token),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    payload = _payload_with_training_match_context(container=container, run_id=run_id, payload=request.payload)
    run = container.execution.finish_run(run_id=run_id, payload=payload)
    container.training_lobby.finish_shadow_match_runs(primary_run=run, payload=payload)
    _reconcile_training_lobby_for_terminal_run(container=container, run=run)
    if run.run_kind is RunKind.TRAINING_MATCH and run.lobby_id is not None:
        container.training_lobby.cleanup_training_match_archive(lobby_id=run.lobby_id)
    _advance_competition_for_terminal_run(container=container, run=run)
    return _run_response(run)


@router.post("/internal/runs/{run_id}/failed", response_model=RunResponse)
def mark_run_failed(
    run_id: str,
    request: FailRunRequest,
    _: object = Depends(require_internal_token),
    container: ServiceContainer = Depends(get_container),
) -> RunResponse:
    run = container.execution.fail_run(run_id=run_id, message=request.message)
    container.training_lobby.fail_shadow_match_runs(primary_run=run, message=request.message)
    _reconcile_training_lobby_for_terminal_run(container=container, run=run)
    if run.run_kind is RunKind.TRAINING_MATCH and run.lobby_id is not None:
        container.training_lobby.cleanup_training_match_archive(lobby_id=run.lobby_id)
    _advance_competition_for_terminal_run(container=container, run=run)
    return _run_response(run)


def _payload_with_training_match_context(
    *,
    container: ServiceContainer,
    run_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    run = container.execution.get_run(run_id=run_id)
    if run.run_kind is not RunKind.TRAINING_MATCH or run.lobby_id is None:
        return payload

    try:
        lobby = container.training_lobby.get_lobby(run.lobby_id)
    except NotFoundError:
        return payload
    match_run_ids: list[str] = []
    for group in lobby.last_scheduled_match_groups:
        if run_id in group:
            match_run_ids = list(group)
            break
    if len(match_run_ids) <= 1:
        return payload

    participants: list[dict[str, object]] = []
    seen_team_ids: set[str] = set()
    for participant_run_id in match_run_ids:
        try:
            participant_run = container.execution.get_run(participant_run_id)
        except NotFoundError:
            continue
        if participant_run.team_id in seen_team_ids:
            continue
        seen_team_ids.add(participant_run.team_id)
        participants.append(_participant_summary(container=container, run=participant_run))

    if len(participants) <= 1:
        return payload
    result = dict(payload)
    result["match_participants"] = participants
    return result


@router.post("/internal/builds/start", response_model=BuildResponse)
def start_build(
    request: StartBuildRequest,
    _: object = Depends(require_internal_token),
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
    _: object = Depends(require_internal_token),
    container: ServiceContainer = Depends(get_container),
) -> BuildResponse:
    build = container.execution.finish_build(build_id=build_id, image_digest=request.image_digest)
    return _build_response(build)


@router.post("/internal/builds/{build_id}/failed", response_model=BuildResponse)
def fail_build(
    build_id: str,
    request: FailBuildRequest,
    _: object = Depends(require_internal_token),
    container: ServiceContainer = Depends(get_container),
) -> BuildResponse:
    build = container.execution.fail_build(build_id=build_id, error_message=request.error_message)
    return _build_response(build)
