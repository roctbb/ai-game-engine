from __future__ import annotations

from pydantic import BaseModel, Field

from training_lobby.domain.model import LobbyAccess, LobbyKind, LobbyStatus


class CreateLobbyRequest(BaseModel):
    game_id: str
    title: str = Field(min_length=2, max_length=120)
    kind: LobbyKind
    access: LobbyAccess
    access_code: str | None = None
    max_teams: int = Field(default=32, ge=1, le=512)


class JoinLobbyRequest(BaseModel):
    access_code: str | None = None


class SetReadyRequest(BaseModel):
    ready: bool


class SwitchGameVersionRequest(BaseModel):
    version_id: str


class MatchmakingTickRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=120)


class SetLobbyStatusRequest(BaseModel):
    status: LobbyStatus


class LobbyTeamStateResponse(BaseModel):
    team_id: str
    ready: bool
    blocker_reason: str | None


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
