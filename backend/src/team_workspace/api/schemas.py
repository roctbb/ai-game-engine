from __future__ import annotations

from pydantic import BaseModel, Field


class CreateTeamRequest(BaseModel):
    game_id: str
    name: str = Field(min_length=2, max_length=120)
    captain_user_id: str = Field(min_length=1, max_length=120)


class UpdateSlotCodeRequest(BaseModel):
    actor_user_id: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=50000)


class TeamResponse(BaseModel):
    team_id: str
    game_id: str
    name: str
    captain_user_id: str


class SlotStateResponse(BaseModel):
    slot_key: str
    state: str
    required: bool
    code: str | None
    revision: int | None


class TeamWorkspaceResponse(BaseModel):
    team_id: str
    game_id: str
    captain_user_id: str
    version_id: str
    slot_states: list[SlotStateResponse]
