from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from execution.domain.model import BuildStatus, RunKind, RunStatus, WorkerStatus


class CreateRunRequest(BaseModel):
    team_id: str
    game_id: str
    requested_by: str = Field(min_length=1, max_length=120)
    run_kind: RunKind = RunKind.SINGLE_TASK
    lobby_id: str | None = None
    version_id: str | None = None


class StartSingleTaskRunRequest(BaseModel):
    team_id: str
    requested_by: str = Field(min_length=1, max_length=120)


class StopSingleTaskRunRequest(BaseModel):
    run_id: str


class SingleTaskAttemptLogsResponse(BaseModel):
    attempt_id: str
    lines: list[str] = []


class RunResponse(BaseModel):
    run_id: str
    team_id: str
    game_id: str
    requested_by: str
    run_kind: RunKind
    lobby_id: str | None
    target_version_id: str | None
    status: RunStatus
    snapshot_id: str | None
    snapshot_version_id: str | None
    worker_id: str | None
    revisions_by_slot: dict[str, int]
    result_payload: dict[str, object] | None
    error_message: str | None
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


class RunExecutionContextResponse(BaseModel):
    run_id: str
    team_id: str
    run_kind: RunKind
    game_id: str
    game_slug: str
    game_package_dir: str
    code_api_mode: str
    engine_entrypoint: str
    renderer_entrypoint: str | None
    snapshot_id: str
    snapshot_version_id: str
    codes_by_slot: dict[str, str]
    revisions_by_slot: dict[str, int]
    participants: list[dict[str, object]] = Field(default_factory=list)


class RunWatchContextResponse(BaseModel):
    run_id: str
    game_id: str
    game_slug: str
    run_kind: RunKind
    status: RunStatus
    renderer_entrypoint: str | None
    renderer_url: str | None
    renderer_protocol: str


class RegisterWorkerRequest(BaseModel):
    worker_id: str
    hostname: str
    capacity_total: int = Field(ge=1, le=1024)
    labels: dict[str, str] = {}


class WorkerHeartbeatRequest(BaseModel):
    capacity_available: int = Field(ge=0, le=1024)


class UpdateWorkerStatusRequest(BaseModel):
    status: WorkerStatus


class WorkerResponse(BaseModel):
    worker_id: str
    hostname: str
    capacity_total: int
    capacity_available: int
    status: WorkerStatus
    labels: dict[str, str]


class FinishRunRequest(BaseModel):
    payload: dict[str, object]


class FailRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class StartRunRequest(BaseModel):
    worker_id: str


class AcceptRunRequest(BaseModel):
    worker_id: str


class StartBuildRequest(BaseModel):
    game_source_id: str
    repo_url: str


class FinishBuildRequest(BaseModel):
    image_digest: str = Field(min_length=10)


class FailBuildRequest(BaseModel):
    error_message: str = Field(min_length=1, max_length=4000)


class BuildResponse(BaseModel):
    build_id: str
    game_source_id: str
    repo_url: str
    status: BuildStatus
    image_digest: str | None
    error_message: str | None
