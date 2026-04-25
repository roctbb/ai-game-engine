from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from training_lobby.domain.model import LobbyAccess, LobbyKind, LobbyStatus


class CreateLobbyRequest(BaseModel):
    game_id: str
    title: str = Field(min_length=2, max_length=120)
    kind: Literal["training"] = "training"
    access: LobbyAccess
    access_code: str | None = None
    max_teams: int = Field(default=32, ge=1, le=512)


class JoinLobbyRequest(BaseModel):
    access_code: str | None = None


class SetReadyRequest(BaseModel):
    ready: bool


class PlayLobbyRequest(BaseModel):
    access_code: str | None = None


class SwitchGameVersionRequest(BaseModel):
    version_id: str


class MatchmakingTickRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=120)


class SetLobbyStatusRequest(BaseModel):
    status: LobbyStatus


class StartLobbyCompetitionRequest(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    format: Literal["single_elimination"] = "single_elimination"
    tie_break_policy: Literal["manual", "shared_advancement"] = "manual"
    code_policy: Literal["locked_on_registration", "locked_on_start", "allowed_between_matches"] = "locked_on_start"
    advancement_top_k: int = Field(default=1, ge=1, le=64)
    match_size: int = Field(default=2, ge=2, le=64)


class LobbyTeamStateResponse(BaseModel):
    team_id: str
    ready: bool
    blocker_reason: str | None


class LobbyParticipantStatsResponse(BaseModel):
    team_id: str
    captain_user_id: str
    display_name: str
    matches_total: int
    wins: int
    average_score: float | None


class LobbyResponse(BaseModel):
    lobby_id: str
    game_id: str
    game_version_id: str
    title: str
    kind: LobbyKind
    access: LobbyAccess
    status: LobbyStatus
    max_teams: int
    teams: list[LobbyTeamStateResponse]
    last_scheduled_run_ids: list[str]
    my_team_id: str | None = None
    my_status: str | None = None
    current_run_id: str | None = None
    playing_team_ids: list[str] = Field(default_factory=list)
    queued_team_ids: list[str] = Field(default_factory=list)
    preparing_team_ids: list[str] = Field(default_factory=list)
    current_run_ids: list[str] = Field(default_factory=list)
    archived_run_ids: list[str] = Field(default_factory=list)
    participant_stats: list[LobbyParticipantStatsResponse] = Field(default_factory=list)


class LobbyCurrentRunResponse(BaseModel):
    lobby_id: str
    team_id: str | None = None
    run_id: str | None = None
    status: str


class LobbyCompetitionResponse(BaseModel):
    competition_id: str
    title: str
    status: str
    winner_team_ids: list[str] = Field(default_factory=list)


class LobbyCompetitionArchiveResponse(BaseModel):
    lobby_id: str
    items: list[LobbyCompetitionResponse] = Field(default_factory=list)
