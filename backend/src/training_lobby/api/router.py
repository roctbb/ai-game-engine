from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth import get_current_session, require_roles
from app.dependencies import ServiceContainer, get_container
from identity.domain.model import AppSession, UserRole
from shared.api.sse import sse_envelope, sse_event
from training_lobby.api.schemas import (
    CreateLobbyRequest,
    JoinLobbyRequest,
    LobbyResponse,
    MatchmakingTickRequest,
    SetReadyRequest,
    SetLobbyStatusRequest,
    SwitchGameVersionRequest,
)
from training_lobby.application.service import CreateLobbyInput
from training_lobby.domain.model import LobbyStatus

router = APIRouter(prefix="/lobbies", tags=["training_lobby"])
_TERMINAL_LOBBY_STATUSES = {LobbyStatus.CLOSED}


def _to_response(lobby: object) -> LobbyResponse:
    from training_lobby.domain.model import Lobby

    typed = lobby if isinstance(lobby, Lobby) else None
    assert typed is not None
    return LobbyResponse(
        lobby_id=typed.lobby_id,
        game_id=typed.game_id,
        game_version_id=typed.game_version_id,
        title=typed.title,
        kind=typed.kind,
        access=typed.access,
        status=typed.status,
        max_teams=typed.max_teams,
        teams=[
            {
                "team_id": team_state.team_id,
                "ready": team_state.ready,
                "blocker_reason": team_state.blocker_reason,
            }
            for team_state in typed.teams.values()
        ],
        last_scheduled_run_ids=list(typed.last_scheduled_run_ids),
    )


@router.get("", response_model=list[LobbyResponse])
def list_lobbies(container: ServiceContainer = Depends(get_container)) -> list[LobbyResponse]:
    return [_to_response(item) for item in container.training_lobby.list_lobbies()]


@router.get("/stream")
def stream_lobbies(
    poll_interval_ms: int = 1000,
    max_events: int = 0,
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    interval = max(50, min(poll_interval_ms, 10_000)) / 1000
    max_events_bounded = max(0, min(max_events, 10_000))

    def _events():
        emitted = 0
        last_signature = ""
        while True:
            lobbies_payload = [
                _to_response(item).model_dump(mode="json")
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


@router.post("", response_model=LobbyResponse)
def create_lobby(
    request: CreateLobbyRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.create_lobby(
        CreateLobbyInput(
            game_id=request.game_id,
            title=request.title,
            kind=request.kind,
            access=request.access,
            access_code=request.access_code,
            max_teams=request.max_teams,
        )
    )
    return _to_response(lobby)


@router.get("/{lobby_id}", response_model=LobbyResponse)
def get_lobby(lobby_id: str, container: ServiceContainer = Depends(get_container)) -> LobbyResponse:
    return _to_response(container.training_lobby.get_lobby(lobby_id))


@router.get("/{lobby_id}/stream")
def stream_lobby(
    lobby_id: str,
    poll_interval_ms: int = 1000,
    max_events: int = 0,
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    interval = max(50, min(poll_interval_ms, 10_000)) / 1000
    max_events_bounded = max(0, min(max_events, 10_000))

    def _events():
        emitted = 0
        last_signature = ""
        while True:
            lobby_payload = _to_response(container.training_lobby.get_lobby(lobby_id)).model_dump(mode="json")
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


@router.post("/{lobby_id}/teams/{team_id}/join", response_model=LobbyResponse)
def join_lobby(
    lobby_id: str,
    team_id: str,
    request: JoinLobbyRequest,
    _session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.join_team(
        lobby_id=lobby_id,
        team_id=team_id,
        access_code=request.access_code,
    )
    return _to_response(lobby)


@router.post("/{lobby_id}/teams/{team_id}/leave", response_model=LobbyResponse)
def leave_lobby(
    lobby_id: str,
    team_id: str,
    _session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    return _to_response(container.training_lobby.leave_team(lobby_id=lobby_id, team_id=team_id))


@router.post("/{lobby_id}/teams/{team_id}/ready", response_model=LobbyResponse)
def set_ready(
    lobby_id: str,
    team_id: str,
    request: SetReadyRequest,
    _session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    return _to_response(
        container.training_lobby.set_ready(
            lobby_id=lobby_id,
            team_id=team_id,
            ready=request.ready,
        )
    )


@router.post("/{lobby_id}/status", response_model=LobbyResponse)
def set_lobby_status(
    lobby_id: str,
    request: SetLobbyStatusRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    return _to_response(container.training_lobby.set_status(lobby_id=lobby_id, status=request.status))


@router.post("/{lobby_id}/switch-version", response_model=LobbyResponse)
def switch_game_version(
    lobby_id: str,
    request: SwitchGameVersionRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.switch_game_version(lobby_id=lobby_id, version_id=request.version_id)
    return _to_response(lobby)


@router.post("/{lobby_id}/matchmaking/tick", response_model=LobbyResponse)
def run_matchmaking_tick(
    lobby_id: str,
    request: MatchmakingTickRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> LobbyResponse:
    lobby = container.training_lobby.run_matchmaking_cycle(
        lobby_id=lobby_id,
        requested_by=request.requested_by,
    )
    return _to_response(lobby)
