from __future__ import annotations

from pydantic import BaseModel, Field

from competition.domain.model import (
    CompetitionFormat,
    CompetitionMatchStatus,
    CompetitionRoundStatus,
    CompetitionStatus,
    TieBreakPolicy,
)


class CreateCompetitionRequest(BaseModel):
    game_id: str
    title: str = Field(min_length=2, max_length=160)
    format: CompetitionFormat
    tie_break_policy: TieBreakPolicy
    advancement_top_k: int = Field(ge=1, le=64)
    match_size: int = Field(ge=2, le=64)


class PatchCompetitionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    tie_break_policy: TieBreakPolicy | None = None
    advancement_top_k: int | None = Field(default=None, ge=1, le=64)
    match_size: int | None = Field(default=None, ge=2, le=64)


class RegisterTeamRequest(BaseModel):
    team_id: str


class RequestedByRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=120)


class SetEntrantReadyRequest(BaseModel):
    team_id: str
    reason: str | None = Field(default=None, max_length=400)


class BanEntrantRequest(BaseModel):
    team_id: str
    banned: bool = True
    reason: str | None = Field(default=None, max_length=400)


class AdvanceCompetitionRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=120)


class ResolveMatchTieRequest(BaseModel):
    round_index: int = Field(ge=1, le=128)
    match_id: str = Field(min_length=1, max_length=120)
    advanced_team_ids: list[str] = Field(min_length=1, max_length=64)


class CompetitionEntrantResponse(BaseModel):
    team_id: str
    ready: bool
    banned: bool
    blocker_reason: str | None


class CompetitionMatchResponse(BaseModel):
    match_id: str
    round_index: int
    team_ids: list[str]
    status: CompetitionMatchStatus
    run_ids_by_team: dict[str, str]
    scores_by_team: dict[str, float]
    placements_by_team: dict[str, int]
    advanced_team_ids: list[str]
    tie_break_reason: str | None


class CompetitionRoundResponse(BaseModel):
    round_index: int
    status: CompetitionRoundStatus
    matches: list[CompetitionMatchResponse]


class CompetitionResponse(BaseModel):
    competition_id: str
    game_id: str
    game_version_id: str
    title: str
    format: CompetitionFormat
    tie_break_policy: TieBreakPolicy
    advancement_top_k: int
    match_size: int
    status: CompetitionStatus
    entrants: list[CompetitionEntrantResponse]
    rounds: list[CompetitionRoundResponse]
    current_round_index: int | None
    winner_team_ids: list[str]
    pending_reason: str | None
    last_scheduled_run_ids: list[str]


class CompetitionRunItemResponse(BaseModel):
    run_id: str
    team_id: str
    status: str
    error_message: str | None
