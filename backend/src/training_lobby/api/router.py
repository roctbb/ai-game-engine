from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from app.auth import get_current_session, require_roles
from app.dependencies import ServiceContainer, get_container, get_games_root
from competition.application.service import CreateCompetitionInput
from competition.domain.model import Competition, CompetitionCodePolicy, CompetitionFormat, CompetitionStatus, TieBreakPolicy
from game_catalog.infrastructure.manifest_loader import find_game_manifest_path, load_game_manifest
from identity.domain.model import AppSession, UserRole
from shared.api.sse import sse_envelope, sse_event
from shared.kernel import ForbiddenError, InvariantViolationError, NotFoundError
from training_lobby.api.schemas import (
    CreateLobbyRequest,
    JoinLobbyRequest,
    LobbyCompetitionArchiveResponse,
    LobbyCompetitionResponse,
    LobbyCurrentRunResponse,
    LobbyParticipantStatsResponse,
    LobbyResponse,
    MatchmakingTickRequest,
    PatchLobbyRequest,
    PlayLobbyRequest,
    StartLobbyCompetitionRequest,
    SetReadyRequest,
    SetLobbyStatusRequest,
    SwitchGameVersionRequest,
)
from training_lobby.application.service import CreateLobbyInput, LobbyLiveView, LobbyMatchGroupView
from training_lobby.domain.model import Lobby, LobbyAccess, LobbyKind, LobbyStatus

router = APIRouter(prefix="/lobbies", tags=["training_lobby"])
_TERMINAL_LOBBY_STATUSES = {LobbyStatus.CLOSED}
_LOBBY_LOCKING_COMPETITION_STATUSES = {
    CompetitionStatus.RUNNING,
    CompetitionStatus.PAUSED,
    CompetitionStatus.COMPLETED,
}
_DEMO_BOT_NAMES = (
    "Бот Евгений",
    "Бот Анна",
    "Бот Максим",
    "Бот София",
    "Бот Артем",
    "Бот Мария",
    "Бот Илья",
    "Бот Алиса",
    "Бот Кирилл",
    "Бот Полина",
    "Бот Даниил",
    "Бот Варвара",
    "Бот Никита",
    "Бот Ксения",
    "Бот Роман",
    "Бот Вера",
)


def _ensure_can_control_team(container: ServiceContainer, session: AppSession, team_id: str) -> None:
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        return
    team = container.team_workspace.get_team(team_id)
    if team.captain_user_id != session.nickname:
        raise ForbiddenError("Участник может управлять только своей командой")


def _to_response(live_view: LobbyLiveView, *, redact_private: bool = False) -> LobbyResponse:
    typed = live_view.lobby
    return LobbyResponse(
        lobby_id=typed.lobby_id,
        game_id=typed.game_id,
        game_version_id=typed.game_version_id,
        title=typed.title,
        kind=typed.kind,
        access=typed.access,
        status=typed.status,
        max_teams=typed.max_teams,
        auto_delete_training_runs_days=typed.auto_delete_training_runs_days,
        teams=[
            {
                "team_id": team_state.team_id,
                "ready": team_state.ready,
                "blocker_reason": team_state.blocker_reason,
            }
            for team_state in ([] if redact_private else typed.teams.values())
        ],
        last_scheduled_run_ids=[] if redact_private else list(typed.last_scheduled_run_ids),
        my_team_id=live_view.my_team_id,
        my_status=live_view.my_status,
        current_run_id=None if redact_private else live_view.current_run_id,
        playing_team_ids=[] if redact_private else list(live_view.playing_team_ids),
        queued_team_ids=[] if redact_private else list(live_view.queued_team_ids),
        preparing_team_ids=[] if redact_private else list(live_view.preparing_team_ids),
        current_run_ids=[] if redact_private else list(live_view.current_run_ids),
        archived_run_ids=[] if redact_private else list(live_view.archived_run_ids),
        participant_stats=[
            LobbyParticipantStatsResponse(
                team_id=item.team_id,
                captain_user_id=item.captain_user_id,
                display_name=item.display_name,
                matches_total=item.matches_total,
                wins=item.wins,
                average_score=item.average_score,
            )
            for item in ([] if redact_private else live_view.participant_stats)
        ],
        cycle_phase=live_view.cycle_phase,
        cycle_phase_label=live_view.cycle_phase_label,
        cycle_message=live_view.cycle_message,
        cycle_started_at=live_view.cycle_started_at,
        replay_started_at=live_view.replay_started_at,
        replay_until=live_view.replay_until,
        result_until=live_view.result_until,
        cycle_frame_ms=live_view.cycle_frame_ms,
        cycle_replay_frame_index=live_view.cycle_replay_frame_index,
        cycle_replay_frame_count=live_view.cycle_replay_frame_count,
        cycle_winner_team_ids=[] if redact_private else list(live_view.cycle_winner_team_ids),
        current_match_groups=[] if redact_private else [_match_group_response(item) for item in live_view.current_match_groups],
        archived_match_groups=[] if redact_private else [_match_group_response(item) for item in live_view.archived_match_groups],
    )


def _match_group_response(item: LobbyMatchGroupView) -> dict[str, object]:
    return {
        "group_id": item.group_id,
        "batch_id": item.batch_id,
        "run_ids": list(item.run_ids),
        "team_ids": list(item.team_ids),
        "status": item.status,
        "started_at": item.started_at,
        "finished_at": item.finished_at,
        "replay_frame_count": item.replay_frame_count,
        "replay_frame_index": item.replay_frame_index,
        "winner_team_ids": list(item.winner_team_ids),
        "scores_by_team": dict(item.scores_by_team),
    }


def _to_summary_response(
    lobby: Lobby,
    *,
    container: ServiceContainer,
    session: AppSession,
    redact_private: bool = False,
) -> LobbyResponse:
    my_team_id = container.training_lobby.find_user_team_in_lobby(
        lobby_id=lobby.lobby_id,
        user_id=session.nickname,
    )
    my_status = "not_in_lobby"
    if my_team_id is not None:
        team_state = lobby.teams.get(my_team_id)
        my_status = "queued" if team_state is not None and team_state.ready else "preparing"

    return LobbyResponse(
        lobby_id=lobby.lobby_id,
        game_id=lobby.game_id,
        game_version_id=lobby.game_version_id,
        title=lobby.title,
        kind=lobby.kind,
        access=lobby.access,
        status=lobby.status,
        max_teams=lobby.max_teams,
        auto_delete_training_runs_days=None if redact_private else lobby.auto_delete_training_runs_days,
        teams=[
            {
                "team_id": team_state.team_id,
                "ready": team_state.ready,
                "blocker_reason": team_state.blocker_reason,
            }
            for team_state in ([] if redact_private else lobby.teams.values())
        ],
        last_scheduled_run_ids=[] if redact_private else list(lobby.last_scheduled_run_ids),
        my_team_id=my_team_id,
        my_status=my_status,
        current_run_id=None,
        playing_team_ids=[],
        queued_team_ids=[],
        preparing_team_ids=[],
        current_run_ids=[],
        archived_run_ids=[],
        participant_stats=[],
    )


def _is_lobby_competition(lobby_id: str, competition: Competition) -> bool:
    return competition.lobby_id == lobby_id


def _has_lobby_locking_competition(container: ServiceContainer, lobby_id: str) -> bool:
    return any(
        _is_lobby_competition(lobby_id=lobby_id, competition=item)
        and item.status in _LOBBY_LOCKING_COMPETITION_STATUSES
        for item in container.competition.list_competitions()
    )


def _reopen_lobby_after_finished_competition_if_needed(container: ServiceContainer, lobby_id: str) -> bool:
    lobby = container.training_lobby.get_lobby(lobby_id)
    if lobby.status is not LobbyStatus.PAUSED:
        return False
    competitions = [
        item
        for item in container.competition.list_competitions()
        if _is_lobby_competition(lobby_id=lobby_id, competition=item)
    ]
    if not competitions:
        return False
    if any(item.status in _LOBBY_LOCKING_COMPETITION_STATUSES for item in competitions):
        return False
    if not any(item.status is CompetitionStatus.FINISHED for item in competitions):
        return False
    try:
        container.training_lobby.set_status(lobby_id=lobby_id, status=LobbyStatus.OPEN)
        return True
    except InvariantViolationError:
        return False


def _kick_training_matchmaking_if_possible(container: ServiceContainer, lobby_id: str) -> None:
    lobby = container.training_lobby.get_lobby(lobby_id)
    if lobby.kind is not LobbyKind.TRAINING:
        return
    if lobby.status not in {LobbyStatus.OPEN, LobbyStatus.RUNNING}:
        return
    if _has_lobby_locking_competition(container=container, lobby_id=lobby_id):
        return
    try:
        container.training_lobby.run_matchmaking_cycle(lobby_id=lobby_id, requested_by="system")
    except InvariantViolationError:
        return


def _next_demo_bot_name(container: ServiceContainer, lobby: Lobby) -> str:
    existing_names: set[str] = set()
    for team_id in lobby.teams:
        try:
            team = container.team_workspace.get_team(team_id)
        except NotFoundError:
            continue
        if team.name:
            existing_names.add(team.name)

    for name in _DEMO_BOT_NAMES:
        if name not in existing_names:
            return name
    for round_index in range(2, 10_000):
        for name in _DEMO_BOT_NAMES:
            candidate = f"{name} {round_index}"
            if candidate not in existing_names:
                return candidate
    return f"Бот {uuid4().hex[:8]}"


def _demo_bot_code_by_slot(container: ServiceContainer, lobby: Lobby) -> dict[str, str]:
    game = container.game_catalog.get_game(lobby.game_id)
    version = container.game_catalog.get_version(game_id=lobby.game_id, version_id=lobby.game_version_id)
    try:
        manifest_path = find_game_manifest_path(games_root=get_games_root(), game_id=game.slug)
        manifest = load_game_manifest(manifest_path)
    except InvariantViolationError as exc:
        raise InvariantViolationError("Для игры не найден manifest с примерами") from exc

    package_root = Path(manifest_path).parent
    codes: dict[str, str] = {}
    for slot_key in version.required_slot_keys:
        demo_strategy = next((item for item in manifest.demo_strategies if item.slot_key == slot_key), None)
        if demo_strategy is not None:
            demo_path = package_root / demo_strategy.path
            if demo_path.is_file():
                codes[slot_key] = demo_path.read_text(encoding="utf-8")
                continue
        template_path = package_root / "templates" / f"{slot_key}.py"
        if template_path.is_file():
            codes[slot_key] = template_path.read_text(encoding="utf-8")
            continue
        raise InvariantViolationError(f"Для роли {slot_key} нет примера или шаблона")
    return codes


def _cleanup_old_training_runs_if_possible(container: ServiceContainer, lobby_id: str) -> None:
    try:
        container.training_lobby.cleanup_old_training_runs(lobby_id=lobby_id)
    except InvariantViolationError:
        return


def _has_lobby_detail_access(
    *,
    container: ServiceContainer,
    session: AppSession,
    lobby_id: str,
) -> bool:
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        return True
    lobby = container.training_lobby.get_lobby(lobby_id)
    if lobby.access is not LobbyAccess.CODE:
        return True
    return (
        container.training_lobby.find_user_team_in_lobby(
            lobby_id=lobby_id,
            user_id=session.nickname,
        )
        is not None
    )


def _ensure_lobby_detail_access(
    *,
    container: ServiceContainer,
    session: AppSession,
    lobby_id: str,
) -> None:
    if not _has_lobby_detail_access(container=container, session=session, lobby_id=lobby_id):
        raise ForbiddenError("Для просмотра лобби нужен код входа или участие в лобби")


@router.get("", response_model=list[LobbyResponse])
def list_lobbies(
    game_id: str | None = None,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[LobbyResponse]:
    lobbies = container.training_lobby.list_lobbies()
    if game_id is not None and game_id.strip():
        lobbies = [item for item in lobbies if item.game_id == game_id.strip()]
    response: list[LobbyResponse] = []
    for item in lobbies:
        response.append(
            _to_summary_response(
                item,
                container=container,
                session=session,
                redact_private=not _has_lobby_detail_access(
                    container=container,
                    session=session,
                    lobby_id=item.lobby_id,
                ),
            )
        )
    return response


@router.get("/stream")
def stream_lobbies(
    request: Request,
    poll_interval_ms: int = 1000,
    max_events: int = 0,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    interval = max(50, min(poll_interval_ms, 10_000)) / 1000
    max_events_bounded = max(0, min(max_events, 10_000))

    async def _events():
        emitted = 0
        last_signature = ""
        while True:
            if await request.is_disconnected():
                break
            lobbies_payload = [
                _to_summary_response(
                    item,
                    container=container,
                    session=session,
                    redact_private=not _has_lobby_detail_access(
                        container=container,
                        session=session,
                        lobby_id=item.lobby_id,
                    ),
                )
                .model_dump(mode="json")
                for item in container.training_lobby.list_lobbies()
            ]
            signature = json.dumps(lobbies_payload, ensure_ascii=False, sort_keys=True)
            if signature != last_signature:
                last_signature = signature
                yield sse_event(
                    "agp.update",
                    sse_envelope(
                        channel="lobbies",
                        entity_id="collection",
                        kind="snapshot",
                        payload={"items": lobbies_payload},
                    ),
                )
                emitted += 1
                if max_events_bounded > 0 and emitted >= max_events_bounded:
                    break
            else:
                yield sse_event(
                    "agp.keepalive",
                    sse_envelope(channel="lobbies", entity_id="collection", kind="keepalive"),
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


@router.post("", response_model=LobbyResponse)
def create_lobby(
    request: CreateLobbyRequest,
    session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.create_lobby(
        CreateLobbyInput(
            game_id=request.game_id,
            title=request.title,
            kind=LobbyKind(request.kind),
            access=request.access,
            access_code=request.access_code,
            max_teams=request.max_teams,
            auto_delete_training_runs_days=request.auto_delete_training_runs_days,
        )
    )
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.post("/matchmaking/tick", response_model=list[LobbyResponse])
def run_due_matchmaking_ticks(
    session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> list[LobbyResponse]:
    lobbies = container.training_lobby.run_due_matchmaking_cycles(requested_by="system")
    return [
        _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))
        for lobby in lobbies
    ]


@router.get("/{lobby_id}", response_model=LobbyResponse)
def get_lobby(
    lobby_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    _ensure_lobby_detail_access(container=container, session=session, lobby_id=lobby_id)
    _reopen_lobby_after_finished_competition_if_needed(container=container, lobby_id=lobby_id)
    _cleanup_old_training_runs_if_possible(container=container, lobby_id=lobby_id)
    container.training_lobby.mark_viewer_online(lobby_id=lobby_id, user_id=session.nickname)
    _kick_training_matchmaking_if_possible(container=container, lobby_id=lobby_id)
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby_id, user_id=session.nickname))


@router.patch("/{lobby_id}", response_model=LobbyResponse)
def patch_lobby(
    lobby_id: str,
    request: PatchLobbyRequest,
    session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    retention = request.auto_delete_training_runs_days if "auto_delete_training_runs_days" in request.model_fields_set else ...
    kwargs = {
        "title": request.title,
        "access": request.access,
        "access_code": request.access_code,
        "max_teams": request.max_teams,
    }
    if retention is not ...:
        kwargs["auto_delete_training_runs_days"] = retention
    lobby = container.training_lobby.update_lobby_settings(lobby_id=lobby_id, **kwargs)
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.delete("/{lobby_id}", status_code=204)
def delete_lobby(
    lobby_id: str,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> Response:
    if _has_lobby_locking_competition(container=container, lobby_id=lobby_id):
        raise InvariantViolationError("Нельзя удалить лобби, пока идет или ожидает завершения соревнование")
    container.training_lobby.delete_lobby(lobby_id=lobby_id)
    return Response(status_code=204)


@router.get("/{lobby_id}/stream")
def stream_lobby(
    request: Request,
    lobby_id: str,
    poll_interval_ms: int = 1000,
    max_events: int = 0,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    _ensure_lobby_detail_access(container=container, session=session, lobby_id=lobby_id)
    _reopen_lobby_after_finished_competition_if_needed(container=container, lobby_id=lobby_id)
    _cleanup_old_training_runs_if_possible(container=container, lobby_id=lobby_id)
    container.training_lobby.mark_viewer_online(lobby_id=lobby_id, user_id=session.nickname)
    _kick_training_matchmaking_if_possible(container=container, lobby_id=lobby_id)
    interval = max(50, min(poll_interval_ms, 10_000)) / 1000
    max_events_bounded = max(0, min(max_events, 10_000))

    async def _events():
        emitted = 0
        last_signature = ""
        while True:
            if await request.is_disconnected():
                break
            _ensure_lobby_detail_access(container=container, session=session, lobby_id=lobby_id)
            _cleanup_old_training_runs_if_possible(container=container, lobby_id=lobby_id)
            container.training_lobby.mark_viewer_online(lobby_id=lobby_id, user_id=session.nickname)
            _kick_training_matchmaking_if_possible(container=container, lobby_id=lobby_id)
            lobby_payload = _to_response(
                container.training_lobby.get_live_view(lobby_id=lobby_id, user_id=session.nickname)
            ).model_dump(mode="json")
            signature = json.dumps(lobby_payload, ensure_ascii=False, sort_keys=True)
            if signature != last_signature:
                last_signature = signature
                status = str(lobby_payload.get("status", ""))
                yield sse_event(
                    "agp.update",
                    sse_envelope(
                        channel="lobby",
                        entity_id=lobby_id,
                        kind="snapshot",
                        payload=lobby_payload,
                        status=status,
                    ),
                )
                emitted += 1
                if max_events_bounded > 0 and emitted >= max_events_bounded:
                    break
                if status in {item.value for item in _TERMINAL_LOBBY_STATUSES}:
                    yield sse_event(
                        "agp.terminal",
                        sse_envelope(
                            channel="lobby",
                            entity_id=lobby_id,
                            kind="terminal",
                            payload={"lobby_id": lobby_id},
                            status=status,
                        ),
                    )
                    break
            else:
                yield sse_event(
                    "agp.keepalive",
                    sse_envelope(channel="lobby", entity_id=lobby_id, kind="keepalive"),
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


@router.post("/{lobby_id}/join", response_model=LobbyResponse)
def join_lobby_as_user(
    lobby_id: str,
    request: JoinLobbyRequest,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby, _team_id = container.training_lobby.ensure_user_joined(
        lobby_id=lobby_id,
        user_id=session.nickname,
        access_code=request.access_code,
        bypass_access_code=session.role in {UserRole.TEACHER, UserRole.ADMIN},
    )
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.post("/{lobby_id}/play", response_model=LobbyResponse)
def play_lobby_as_user(
    lobby_id: str,
    request: PlayLobbyRequest,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby, team_id = container.training_lobby.ensure_user_joined(
        lobby_id=lobby_id,
        user_id=session.nickname,
        access_code=request.access_code,
    )
    lobby = container.training_lobby.set_ready(lobby_id=lobby_id, team_id=team_id, ready=True)
    container.training_lobby.mark_viewer_online(lobby_id=lobby_id, user_id=session.nickname)
    if lobby.kind.value == "training" and lobby.status in {LobbyStatus.OPEN, LobbyStatus.RUNNING}:
        try:
            lobby = container.training_lobby.run_matchmaking_cycle(
                lobby_id=lobby_id,
                requested_by=session.nickname,
            )
        except InvariantViolationError:
            pass
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.post("/{lobby_id}/stop", response_model=LobbyResponse)
def stop_lobby_as_user(
    lobby_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.stop_for_user(lobby_id=lobby_id, user_id=session.nickname)
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.get("/{lobby_id}/current-run", response_model=LobbyCurrentRunResponse)
def get_lobby_current_run(
    lobby_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyCurrentRunResponse:
    _ensure_lobby_detail_access(container=container, session=session, lobby_id=lobby_id)
    live_view = container.training_lobby.get_live_view(lobby_id=lobby_id, user_id=session.nickname)
    return LobbyCurrentRunResponse(
        lobby_id=lobby_id,
        team_id=live_view.my_team_id,
        run_id=live_view.current_run_id,
        status=live_view.my_status,
    )


@router.post("/{lobby_id}/competitions/start", response_model=LobbyCompetitionResponse)
def start_lobby_competition(
    lobby_id: str,
    request: StartLobbyCompetitionRequest,
    session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyCompetitionResponse:
    lobby = container.training_lobby.get_lobby(lobby_id=lobby_id)
    if lobby.kind.value != "training":
        raise InvariantViolationError("Соревнование можно запускать только в training-лобби")
    active_competition = next(
        (
            item
            for item in container.competition.list_competitions()
            if _is_lobby_competition(lobby_id=lobby_id, competition=item)
            and item.status is not CompetitionStatus.FINISHED
        ),
        None,
    )
    if active_competition is not None:
        raise InvariantViolationError("В лобби уже есть активное соревнование")
    ready_team_ids = [
        team_id
        for team_id in sorted(lobby.teams.keys())
        if container.team_workspace.evaluate_compatibility(
            team_id=team_id,
            game_id=lobby.game_id,
            version_id=lobby.game_version_id,
        ).compatible
    ]
    if len(ready_team_ids) < 2:
        raise InvariantViolationError("Для старта соревнования нужны минимум 2 игрока с заполненным кодом")

    lobby = container.training_lobby.stop_current_training_games_for_competition(lobby_id=lobby_id)
    competition = container.competition.create_competition(
        CreateCompetitionInput(
            game_id=lobby.game_id,
            lobby_id=lobby_id,
            title=request.title,
            format=CompetitionFormat(request.format),
            tie_break_policy=TieBreakPolicy(request.tie_break_policy),
            code_policy=CompetitionCodePolicy(request.code_policy),
            advancement_top_k=request.advancement_top_k,
            match_size=request.match_size,
        )
    )
    for team_id in sorted(lobby.teams.keys()):
        container.competition.register_team(competition_id=competition.competition_id, team_id=team_id)
    competition = container.competition.start_competition(
        competition_id=competition.competition_id,
        requested_by=session.nickname,
    )
    try:
        container.training_lobby.set_status(lobby_id=lobby_id, status=LobbyStatus.PAUSED)
    except InvariantViolationError:
        pass
    return LobbyCompetitionResponse(
        competition_id=competition.competition_id,
        title=competition.title,
        status=competition.status.value,
        winner_team_ids=list(competition.winner_team_ids),
    )


@router.post("/{lobby_id}/competitions/{competition_id}/finish", response_model=LobbyCompetitionResponse)
def finish_lobby_competition(
    lobby_id: str,
    competition_id: str,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyCompetitionResponse:
    competition = container.competition.get_competition(competition_id=competition_id)
    if not _is_lobby_competition(lobby_id=lobby_id, competition=competition):
        raise InvariantViolationError("Соревнование не принадлежит этому лобби")
    competition = container.competition.finish_competition(competition_id=competition_id)
    try:
        container.training_lobby.set_status(lobby_id=lobby_id, status=LobbyStatus.OPEN)
    except InvariantViolationError:
        pass
    return LobbyCompetitionResponse(
        competition_id=competition.competition_id,
        title=competition.title,
        status=competition.status.value,
        winner_team_ids=list(competition.winner_team_ids),
    )


@router.get("/{lobby_id}/competitions/archive", response_model=LobbyCompetitionArchiveResponse)
def list_lobby_competition_archive(
    lobby_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyCompetitionArchiveResponse:
    _ensure_lobby_detail_access(container=container, session=session, lobby_id=lobby_id)
    competitions = [
        item
        for item in container.competition.list_competitions()
        if _is_lobby_competition(lobby_id=lobby_id, competition=item)
        and item.status is CompetitionStatus.FINISHED
    ]
    competitions.sort(key=lambda item: item.updated_at, reverse=True)
    return LobbyCompetitionArchiveResponse(
        lobby_id=lobby_id,
        items=[
            LobbyCompetitionResponse(
                competition_id=item.competition_id,
                title=item.title,
                status=item.status.value,
                winner_team_ids=list(item.winner_team_ids),
            )
            for item in competitions
        ],
    )


@router.post("/{lobby_id}/teams/{team_id}/join", response_model=LobbyResponse)
def join_lobby(
    lobby_id: str,
    team_id: str,
    request: JoinLobbyRequest,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    _ensure_can_control_team(container=container, session=session, team_id=team_id)
    lobby = container.training_lobby.join_team(
        lobby_id=lobby_id,
        team_id=team_id,
        access_code=request.access_code,
    )
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.post("/{lobby_id}/teams/{team_id}/leave", response_model=LobbyResponse)
def leave_lobby(
    lobby_id: str,
    team_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    _ensure_can_control_team(container=container, session=session, team_id=team_id)
    if _has_lobby_locking_competition(container=container, lobby_id=lobby_id):
        raise InvariantViolationError("Во время соревнования выход из лобби запрещен")
    lobby = container.training_lobby.leave_team(lobby_id=lobby_id, team_id=team_id)
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.post("/{lobby_id}/admin-bots", response_model=LobbyResponse)
def add_admin_demo_bot(
    lobby_id: str,
    session: AppSession = Depends(require_roles(UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.get_lobby(lobby_id=lobby_id)
    if _has_lobby_locking_competition(container=container, lobby_id=lobby_id):
        raise InvariantViolationError("Во время соревнования нельзя добавлять ботов")
    if lobby.status not in {LobbyStatus.DRAFT, LobbyStatus.OPEN, LobbyStatus.RUNNING}:
        raise InvariantViolationError("В текущем статусе нельзя добавлять ботов")
    if len(lobby.teams) >= lobby.max_teams:
        raise InvariantViolationError("Лобби заполнено")

    slot_codes = _demo_bot_code_by_slot(container=container, lobby=lobby)
    bot_name = _next_demo_bot_name(container=container, lobby=lobby)
    captain_user_id = f"bot:{lobby.lobby_id}:{uuid4().hex}"
    team = container.team_workspace.create_team(
        game_id=lobby.game_id,
        name=bot_name,
        captain_user_id=captain_user_id,
    )
    for slot_key, code in slot_codes.items():
        container.team_workspace.update_slot_code(
            team_id=team.team_id,
            actor_user_id=captain_user_id,
            slot_key=slot_key,
            code=code,
        )
    lobby = container.training_lobby.join_team(
        lobby_id=lobby.lobby_id,
        team_id=team.team_id,
        access_code=None,
        bypass_access_code=True,
    )
    lobby = container.training_lobby.set_ready(lobby_id=lobby.lobby_id, team_id=team.team_id, ready=True)
    if lobby.kind is LobbyKind.TRAINING and lobby.status in {LobbyStatus.OPEN, LobbyStatus.RUNNING}:
        _kick_training_matchmaking_if_possible(container=container, lobby_id=lobby.lobby_id)
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.post("/{lobby_id}/teams/{team_id}/ready", response_model=LobbyResponse)
def set_ready(
    lobby_id: str,
    team_id: str,
    request: SetReadyRequest,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    _ensure_can_control_team(container=container, session=session, team_id=team_id)
    lobby = container.training_lobby.set_ready(
        lobby_id=lobby_id,
        team_id=team_id,
        ready=request.ready,
    )
    if request.ready and lobby.kind.value == "training" and lobby.status in {LobbyStatus.OPEN, LobbyStatus.RUNNING}:
        try:
            lobby = container.training_lobby.run_matchmaking_cycle(
                lobby_id=lobby_id,
                requested_by=session.nickname,
            )
        except InvariantViolationError:
            pass
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.post("/{lobby_id}/status", response_model=LobbyResponse)
def set_lobby_status(
    lobby_id: str,
    request: SetLobbyStatusRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.set_status(lobby_id=lobby_id, status=request.status)
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=_session.nickname))


@router.post("/{lobby_id}/switch-version", response_model=LobbyResponse)
def switch_game_version(
    lobby_id: str,
    request: SwitchGameVersionRequest,
    session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.switch_game_version(lobby_id=lobby_id, version_id=request.version_id)
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))


@router.post("/{lobby_id}/matchmaking/tick", response_model=LobbyResponse)
def run_matchmaking_tick(
    lobby_id: str,
    request: MatchmakingTickRequest,
    session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.run_matchmaking_cycle(
        lobby_id=lobby_id,
        requested_by=request.requested_by,
    )
    return _to_response(container.training_lobby.get_live_view(lobby_id=lobby.lobby_id, user_id=session.nickname))
