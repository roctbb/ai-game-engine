from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import require_roles
from administration.api.schemas import (
    CreateGameSourceRequest,
    GameSourceResponse,
    GameSourceSyncResponse,
    TriggerSyncRequest,
    TriggerSyncResponse,
    UpdateGameSourceStatusRequest,
)
from administration.application.service import CreateGameSourceInput, TriggerSyncInput, UpdateSourceStatusInput
from app.dependencies import ServiceContainer, get_container
from identity.domain.model import UserRole

router = APIRouter(
    prefix="/game-sources",
    tags=["administration"],
    dependencies=[Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN))],
)


def _source_response(source: object) -> GameSourceResponse:
    from administration.domain.model import GameSource

    typed = source if isinstance(source, GameSource) else None
    assert typed is not None
    return GameSourceResponse(
        source_id=typed.source_id,
        source_type=typed.source_type,
        repo_url=typed.repo_url,
        default_branch=typed.default_branch,
        status=typed.status,
        last_sync_status=typed.last_sync_status,
        last_synced_commit_sha=typed.last_synced_commit_sha,
        created_by=typed.created_by,
        created_at=typed.created_at,
        updated_at=typed.updated_at,
    )


def _sync_response(sync: object) -> GameSourceSyncResponse:
    from administration.domain.model import GameSourceSync

    typed = sync if isinstance(sync, GameSourceSync) else None
    assert typed is not None
    return GameSourceSyncResponse(
        sync_id=typed.sync_id,
        source_id=typed.source_id,
        requested_by=typed.requested_by,
        status=typed.status,
        build_id=typed.build_id,
        image_digest=typed.image_digest,
        error_message=typed.error_message,
        commit_sha=typed.commit_sha,
        started_at=typed.started_at,
        finished_at=typed.finished_at,
    )


@router.get("", response_model=list[GameSourceResponse])
def list_game_sources(container: ServiceContainer = Depends(get_container)) -> list[GameSourceResponse]:
    return [_source_response(item) for item in container.administration.list_sources()]


@router.post("", response_model=GameSourceResponse)
def create_game_source(
    request: CreateGameSourceRequest,
    container: ServiceContainer = Depends(get_container),
) -> GameSourceResponse:
    source = container.administration.create_git_source(
        CreateGameSourceInput(
            repo_url=str(request.repo_url),
            default_branch=request.default_branch,
            created_by=request.created_by,
        )
    )
    return _source_response(source)


@router.patch("/{source_id}/status", response_model=GameSourceResponse)
def update_game_source_status(
    source_id: str,
    request: UpdateGameSourceStatusRequest,
    container: ServiceContainer = Depends(get_container),
) -> GameSourceResponse:
    source = container.administration.update_source_status(
        UpdateSourceStatusInput(source_id=source_id, status=request.status.value)
    )
    return _source_response(source)


@router.post("/{source_id}/sync", response_model=TriggerSyncResponse)
def trigger_game_source_sync(
    source_id: str,
    request: TriggerSyncRequest,
    container: ServiceContainer = Depends(get_container),
) -> TriggerSyncResponse:
    source, sync = container.administration.sync_source(
        TriggerSyncInput(
            source_id=source_id,
            requested_by=request.requested_by,
        )
    )
    return TriggerSyncResponse(
        source=_source_response(source),
        sync=_sync_response(sync),
    )


@router.get("/{source_id}/sync-history", response_model=list[GameSourceSyncResponse])
def list_sync_history(
    source_id: str,
    container: ServiceContainer = Depends(get_container),
) -> list[GameSourceSyncResponse]:
    return [_sync_response(item) for item in container.administration.list_sync_history(source_id=source_id)]
