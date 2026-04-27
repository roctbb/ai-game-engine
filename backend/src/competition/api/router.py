from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.auth import get_current_session, require_roles
from app.dependencies import ServiceContainer, get_container
from identity.domain.model import AppSession, UserRole
from shared.api.sse import sse_envelope, sse_event
from shared.kernel import ForbiddenError, InvariantViolationError
from competition.api.schemas import (
    AdvanceCompetitionRequest,
    BanEntrantRequest,
    CompetitionMatchResponse,
    CompetitionResponse,
    CompetitionRoundResponse,
    CompetitionRunItemResponse,
    CreateCompetitionRequest,
    PatchCompetitionRequest,
    RegisterTeamRequest,
    ResolveMatchTieRequest,
    RequestedByRequest,
    SetEntrantReadyRequest,
)
from competition.application.service import CreateCompetitionInput, ResolveTieInput
from competition.domain.model import Competition, CompetitionCodePolicy, CompetitionFormat, CompetitionStatus, TieBreakPolicy

router = APIRouter(prefix="/competitions", tags=["competition"])
_TERMINAL_COMPETITION_STATUSES = {CompetitionStatus.FINISHED}


def _match_response(match) -> CompetitionMatchResponse:
    return CompetitionMatchResponse(
        match_id=match.match_id,
        round_index=match.round_index,
        team_ids=list(match.team_ids),
        status=match.status,
        run_ids_by_team=dict(match.run_ids_by_team),
        scores_by_team=dict(match.scores_by_team),
        placements_by_team=dict(match.placements_by_team),
        advanced_team_ids=list(match.advanced_team_ids),
        tie_break_reason=match.tie_break_reason,
    )


def _round_response(round_item) -> CompetitionRoundResponse:
    return CompetitionRoundResponse(
        round_index=round_item.round_index,
        status=round_item.status,
        matches=[_match_response(match) for match in round_item.matches],
    )


def _to_response(competition: Competition) -> CompetitionResponse:
    return CompetitionResponse(
        competition_id=competition.competition_id,
        game_id=competition.game_id,
        game_version_id=competition.game_version_id,
        lobby_id=competition.lobby_id,
        title=competition.title,
        format=competition.format,
        tie_break_policy=competition.tie_break_policy,
        code_policy=competition.code_policy,
        advancement_top_k=competition.advancement_top_k,
        min_match_size=competition.min_match_size,
        match_size=competition.match_size,
        status=competition.status,
        entrants=[
            {
                "team_id": entrant.team_id,
                "ready": entrant.ready,
                "banned": entrant.banned,
                "blocker_reason": entrant.blocker_reason,
            }
            for entrant in competition.entrants.values()
        ],
        rounds=[_round_response(round_item) for round_item in competition.rounds],
        current_round_index=competition.current_round_index,
        winner_team_ids=list(competition.winner_team_ids),
        pending_reason=competition.pending_reason,
        last_scheduled_run_ids=list(competition.last_scheduled_run_ids),
    )


def _can_view_competition(
    *,
    container: ServiceContainer,
    session: AppSession,
    competition: Competition,
) -> bool:
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        return True
    user_teams = container.team_workspace.list_teams_by_game_and_captain(
        game_id=competition.game_id,
        captain_user_id=session.nickname,
    )
    if any(team.team_id in competition.entrants for team in user_teams):
        return True
    if competition.lobby_id:
        return (
            container.training_lobby.find_user_team_in_lobby(
                lobby_id=competition.lobby_id,
                user_id=session.nickname,
            )
            is not None
        )
    return False


def _ensure_can_view_competition(
    *,
    container: ServiceContainer,
    session: AppSession,
    competition: Competition,
) -> None:
    if not _can_view_competition(container=container, session=session, competition=competition):
        raise ForbiddenError("Просматривать соревнование может только участник, преподаватель или админ")


def _reconcile_competition_if_ready(
    *,
    container: ServiceContainer,
    competition: Competition,
) -> Competition:
    if competition.status is not CompetitionStatus.RUNNING:
        return competition
    try:
        return container.competition.advance_competition(
            competition_id=competition.competition_id,
            requested_by="system",
        )
    except InvariantViolationError:
        return competition


@router.get("", response_model=list[CompetitionResponse])
def list_competitions(
    lobby_id: str | None = None,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[CompetitionResponse]:
    visible: list[CompetitionResponse] = []
    for item in container.competition.list_competitions(lobby_id=lobby_id):
        if not _can_view_competition(container=container, session=session, competition=item):
            continue
        visible.append(_to_response(_reconcile_competition_if_ready(container=container, competition=item)))
    return visible


@router.post("", response_model=CompetitionResponse)
def create_competition(
    request: CreateCompetitionRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    if request.lobby_id is not None:
        raise InvariantViolationError("Соревнование для лобби запускается через endpoint лобби")
    competition = container.competition.create_competition(
        CreateCompetitionInput(
            game_id=request.game_id,
            lobby_id=None,
            title=request.title,
            format=CompetitionFormat(request.format),
            tie_break_policy=TieBreakPolicy(request.tie_break_policy),
            code_policy=CompetitionCodePolicy(request.code_policy),
            advancement_top_k=request.advancement_top_k,
            match_size=request.match_size,
        )
    )
    return _to_response(competition)


@router.get("/{competition_id}", response_model=CompetitionResponse)
def get_competition(
    competition_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    competition = container.competition.get_competition(competition_id)
    _ensure_can_view_competition(container=container, session=session, competition=competition)
    competition = _reconcile_competition_if_ready(container=container, competition=competition)
    return _to_response(competition)


@router.patch("/{competition_id}", response_model=CompetitionResponse)
def patch_competition(
    competition_id: str,
    request: PatchCompetitionRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    competition = container.competition.update_competition(
        competition_id=competition_id,
        title=request.title,
        tie_break_policy=TieBreakPolicy(request.tie_break_policy) if request.tie_break_policy is not None else None,
        code_policy=CompetitionCodePolicy(request.code_policy) if request.code_policy is not None else None,
        advancement_top_k=request.advancement_top_k,
        match_size=request.match_size,
    )
    return _to_response(competition)


@router.get("/{competition_id}/stream")
def stream_competition(
    request: Request,
    competition_id: str,
    poll_interval_ms: int = 1000,
    max_events: int = 0,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    competition = container.competition.get_competition(competition_id)
    _ensure_can_view_competition(container=container, session=session, competition=competition)
    interval = max(50, min(poll_interval_ms, 10_000)) / 1000
    max_events_bounded = max(0, min(max_events, 10_000))

    async def _events():
        emitted = 0
        last_signature = ""

        def _build_payload() -> dict[str, object]:
            competition = container.competition.get_competition(competition_id)
            _ensure_can_view_competition(container=container, session=session, competition=competition)
            return _to_response(competition).model_dump(mode="json")

        while True:
            if await request.is_disconnected():
                break
            competition_payload = await run_in_threadpool(_build_payload)
            signature = json.dumps(competition_payload, ensure_ascii=False, sort_keys=True)
            if signature != last_signature:
                last_signature = signature
                status = str(competition_payload.get("status", ""))
                yield sse_event(
                    "agp.update",
                    sse_envelope(
                        channel="competition",
                        entity_id=competition_id,
                        kind="snapshot",
                        payload=competition_payload,
                        status=status,
                    ),
                )
                emitted += 1
                if max_events_bounded > 0 and emitted >= max_events_bounded:
                    break
                if status in {item.value for item in _TERMINAL_COMPETITION_STATUSES}:
                    yield sse_event(
                        "agp.terminal",
                        sse_envelope(
                            channel="competition",
                            entity_id=competition_id,
                            kind="terminal",
                            payload={"competition_id": competition_id},
                            status=status,
                        ),
                    )
                    break
            else:
                yield sse_event(
                    "agp.keepalive",
                    sse_envelope(channel="competition", entity_id=competition_id, kind="keepalive"),
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


@router.post("/{competition_id}/register", response_model=CompetitionResponse)
def register_team(
    competition_id: str,
    request: RegisterTeamRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(
        container.competition.register_team(
            competition_id=competition_id,
            team_id=request.team_id,
        )
    )


@router.post("/{competition_id}/unregister", response_model=CompetitionResponse)
def unregister_team(
    competition_id: str,
    request: RegisterTeamRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(
        container.competition.unregister_team(
            competition_id=competition_id,
            team_id=request.team_id,
        )
    )


@router.post("/{competition_id}/start", response_model=CompetitionResponse)
def start_competition(
    competition_id: str,
    request: RequestedByRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(
        container.competition.start_competition(
            competition_id=competition_id,
            requested_by=request.requested_by,
        )
    )


@router.post("/{competition_id}/pause", response_model=CompetitionResponse)
def pause_competition(
    competition_id: str,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(container.competition.pause_competition(competition_id))


@router.post("/{competition_id}/finish", response_model=CompetitionResponse)
def finish_competition(
    competition_id: str,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(container.competition.finish_competition(competition_id))


@router.post("/{competition_id}/advance", response_model=CompetitionResponse)
def advance_competition(
    competition_id: str,
    request: AdvanceCompetitionRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(
        container.competition.advance_competition(
            competition_id=competition_id,
            requested_by=request.requested_by,
        )
    )


@router.post("/{competition_id}/matches/resolve", response_model=CompetitionResponse)
def resolve_match_tie(
    competition_id: str,
    request: ResolveMatchTieRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(
        container.competition.resolve_match_tiebreak(
            competition_id=competition_id,
            data=ResolveTieInput(
                round_index=request.round_index,
                match_id=request.match_id,
                advanced_team_ids=request.advanced_team_ids,
            ),
        )
    )


@router.post("/{competition_id}/moderation/not-ready", response_model=CompetitionResponse)
def set_entrant_not_ready(
    competition_id: str,
    request: SetEntrantReadyRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(
        container.competition.set_not_ready(
            competition_id=competition_id,
            team_id=request.team_id,
            reason=request.reason,
        )
    )


@router.post("/{competition_id}/moderation/ban", response_model=CompetitionResponse)
def set_entrant_ban(
    competition_id: str,
    request: BanEntrantRequest,
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> CompetitionResponse:
    return _to_response(
        container.competition.set_ban(
            competition_id=competition_id,
            team_id=request.team_id,
            banned=request.banned,
            reason=request.reason,
        )
    )


@router.get("/{competition_id}/runs", response_model=list[CompetitionRunItemResponse])
def list_competition_runs(
    competition_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[CompetitionRunItemResponse]:
    competition = container.competition.get_competition(competition_id)
    _ensure_can_view_competition(container=container, session=session, competition=competition)
    return [
        CompetitionRunItemResponse(**item)
        for item in container.competition.list_competition_runs(competition_id=competition_id)
    ]


@router.get("/{competition_id}/bracket", response_model=list[CompetitionRoundResponse])
def get_competition_bracket(
    competition_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[CompetitionRoundResponse]:
    competition = container.competition.get_competition(competition_id)
    _ensure_can_view_competition(container=container, session=session, competition=competition)
    return [_round_response(round_item) for round_item in competition.rounds]


@router.get("/{competition_id}/rounds", response_model=list[CompetitionRoundResponse])
def get_competition_rounds(
    competition_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[CompetitionRoundResponse]:
    competition = container.competition.get_competition(competition_id)
    _ensure_can_view_competition(container=container, session=session, competition=competition)
    return [_round_response(round_item) for round_item in competition.rounds]


@router.get("/{competition_id}/matches", response_model=list[CompetitionMatchResponse])
def get_competition_matches(
    competition_id: str,
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[CompetitionMatchResponse]:
    competition = container.competition.get_competition(competition_id)
    _ensure_can_view_competition(container=container, session=session, competition=competition)
    matches: list[CompetitionMatchResponse] = []
    for round_item in competition.rounds:
        matches.extend(_match_response(match) for match in round_item.matches)
    return matches
