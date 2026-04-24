from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_session
from app.dependencies import ServiceContainer, get_container
from execution.domain.model import RunKind
from identity.domain.model import AppSession
from spectator_replay.api.schemas import ReplayResponse
from spectator_replay.application.service import ListReplaysQuery
from spectator_replay.domain.model import ReplayRecord

router = APIRouter(prefix="/replays", tags=["spectator_replay"])


def _to_response(item: ReplayRecord) -> ReplayResponse:
    return ReplayResponse(
        replay_id=item.replay_id,
        run_id=item.run_id,
        game_id=item.game_id,
        run_kind=item.run_kind,
        status=item.status,
        visibility=item.visibility,
        frames=list(item.frames),
        events=list(item.events),
        summary=dict(item.summary),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/runs/{run_id}", response_model=ReplayResponse)
def get_replay_by_run_id(
    run_id: str,
    container: ServiceContainer = Depends(get_container),
) -> ReplayResponse:
    return _to_response(container.spectator_replay.get_by_run_id(run_id))


@router.get("", response_model=list[ReplayResponse])
def list_replays(
    game_id: str | None = None,
    run_kind: RunKind | None = None,
    limit: int = 50,
    _session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[ReplayResponse]:
    items = container.spectator_replay.list_replays(
        ListReplaysQuery(game_id=game_id, run_kind=run_kind, limit=limit)
    )
    return [_to_response(item) for item in items]
