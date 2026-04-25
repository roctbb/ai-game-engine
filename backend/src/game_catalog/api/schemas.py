from __future__ import annotations

from pydantic import BaseModel, Field

from game_catalog.domain.model import CatalogMetadataStatus, GameMode


class SlotDefinitionPayload(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    required: bool = True


class RegisterGameRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=255)
    mode: GameMode
    semver: str = Field(min_length=1, max_length=32)
    required_slots: list[SlotDefinitionPayload]
    required_worker_labels: dict[str, str] = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=2000)
    difficulty: str | None = Field(default=None, max_length=32)
    learning_section: str | None = Field(default=None, max_length=80)
    topics: list[str] = Field(default_factory=list, max_length=30)
    catalog_metadata_status: CatalogMetadataStatus | None = None


class AddVersionRequest(BaseModel):
    semver: str = Field(min_length=1, max_length=32)
    required_slots: list[SlotDefinitionPayload]
    required_worker_labels: dict[str, str] = Field(default_factory=dict)


class ActivateVersionRequest(BaseModel):
    version_id: str


class UpdateCatalogMetadataRequest(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    difficulty: str | None = Field(default=None, max_length=32)
    learning_section: str | None = Field(default=None, max_length=80)
    topics: list[str] = Field(default_factory=list, max_length=30)
    catalog_metadata_status: CatalogMetadataStatus | None = None


class PatchGameRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    difficulty: str | None = Field(default=None, max_length=32)
    learning_section: str | None = Field(default=None, max_length=80)
    topics: list[str] | None = Field(default=None, max_length=30)
    catalog_metadata_status: CatalogMetadataStatus | None = None


class GameVersionResponse(BaseModel):
    version_id: str
    semver: str
    required_slot_keys: list[str]
    required_worker_labels: dict[str, str] = Field(default_factory=dict)


class GameTopicsResponse(BaseModel):
    game_id: str
    topics: list[str] = Field(default_factory=list)


class GameSlotTemplateResponse(BaseModel):
    slot_key: str
    language: str
    code: str


class GameDemoStrategyResponse(BaseModel):
    strategy_id: str
    slot_key: str
    title: str
    language: str
    code: str
    description: str | None = None


class GameTemplatesResponse(BaseModel):
    game_id: str
    game_slug: str
    code_api_mode: str
    player_instruction: str | None = None
    templates: list[GameSlotTemplateResponse] = Field(default_factory=list)
    demo_strategies: list[GameDemoStrategyResponse] = Field(default_factory=list)


class GameDocumentationLinkResponse(BaseModel):
    title: str
    path: str
    content: str | None = None


class GameDocumentationResponse(BaseModel):
    game_id: str
    slug: str
    player_instruction: str | None = None
    links: list[GameDocumentationLinkResponse] = Field(default_factory=list)


class GameResponse(BaseModel):
    game_id: str
    slug: str
    title: str
    mode: GameMode
    description: str | None = None
    difficulty: str | None = None
    learning_section: str | None = None
    topics: list[str] = Field(default_factory=list)
    catalog_metadata_status: CatalogMetadataStatus
    active_version_id: str
    versions: list[GameVersionResponse]


class SingleTaskCatalogItemResponse(BaseModel):
    game_id: str
    slug: str
    title: str
    description: str | None = None
    difficulty: str | None = None
    learning_section: str | None = None
    topics: list[str] = Field(default_factory=list)
    catalog_metadata_status: CatalogMetadataStatus
    attempts_finished: int
    solved_users: int
    has_score_model: bool


class SingleTaskCatalogGroupResponse(BaseModel):
    learning_section: str
    items: list[SingleTaskCatalogItemResponse] = Field(default_factory=list)


class SingleTaskSolvedSummaryEntryResponse(BaseModel):
    place: int
    user_id: str
    solved_tasks_count: int
    solved_game_ids: list[str] = Field(default_factory=list)


class SingleTaskSolvedSummaryResponse(BaseModel):
    total_single_tasks: int
    entries: list[SingleTaskSolvedSummaryEntryResponse] = Field(default_factory=list)


class SingleTaskLeaderboardEntryResponse(BaseModel):
    place: int
    user_id: str
    solved: bool
    solved_attempts: int
    finished_attempts: int
    best_score: float | None = None
    best_run_id: str | None = None
    last_finished_at: str | None = None


class SingleTaskLeaderboardResponse(BaseModel):
    game_id: str
    leaderboard_kind: str
    entries: list[SingleTaskLeaderboardEntryResponse] = Field(default_factory=list)
