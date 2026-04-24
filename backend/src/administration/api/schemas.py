from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl

from administration.domain.model import GameSourceStatus, GameSourceType, SyncStatus


class CreateGameSourceRequest(BaseModel):
    repo_url: HttpUrl
    default_branch: str = Field(default="main", min_length=1, max_length=120)
    created_by: str = Field(min_length=1, max_length=120)


class TriggerSyncRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=120)


class UpdateGameSourceStatusRequest(BaseModel):
    status: GameSourceStatus


class GameSourceResponse(BaseModel):
    source_id: str
    source_type: GameSourceType
    repo_url: str
    default_branch: str
    status: GameSourceStatus
    last_sync_status: SyncStatus
    last_synced_commit_sha: str | None
    created_by: str
    created_at: object
    updated_at: object


class GameSourceSyncResponse(BaseModel):
    sync_id: str
    source_id: str
    requested_by: str
    status: SyncStatus
    build_id: str | None
    image_digest: str | None
    error_message: str | None
    commit_sha: str | None
    started_at: object
    finished_at: object | None


class TriggerSyncResponse(BaseModel):
    source: GameSourceResponse
    sync: GameSourceSyncResponse
