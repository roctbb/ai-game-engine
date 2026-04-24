from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import ServiceContainer, get_container
from team_workspace.api.schemas import (
    CreateTeamRequest,
    TeamResponse,
    TeamWorkspaceResponse,
    UpdateSlotCodeRequest,
)

router = APIRouter(prefix="/teams", tags=["team_workspace"])


@router.get("", response_model=list[TeamResponse])
def list_teams(
    game_id: str,
    container: ServiceContainer = Depends(get_container),
) -> list[TeamResponse]:
    teams = container.team_workspace.list_teams_by_game(game_id=game_id)
    return [
        TeamResponse(
            team_id=team.team_id,
            game_id=team.game_id,
            name=team.name,
            captain_user_id=team.captain_user_id,
        )
        for team in teams
    ]


@router.post("", response_model=TeamResponse)
def create_team(
    request: CreateTeamRequest,
    container: ServiceContainer = Depends(get_container),
) -> TeamResponse:
    team = container.team_workspace.create_team(
        game_id=request.game_id,
        name=request.name,
        captain_user_id=request.captain_user_id,
    )
    return TeamResponse(
        team_id=team.team_id,
        game_id=team.game_id,
        name=team.name,
        captain_user_id=team.captain_user_id,
    )


@router.put("/{team_id}/slots/{slot_key}", response_model=TeamResponse)
def update_slot_code(
    team_id: str,
    slot_key: str,
    request: UpdateSlotCodeRequest,
    container: ServiceContainer = Depends(get_container),
) -> TeamResponse:
    team = container.team_workspace.update_slot_code(
        team_id=team_id,
        actor_user_id=request.actor_user_id,
        slot_key=slot_key,
        code=request.code,
    )
    return TeamResponse(
        team_id=team.team_id,
        game_id=team.game_id,
        name=team.name,
        captain_user_id=team.captain_user_id,
    )


@router.get("/{team_id}/workspace", response_model=TeamWorkspaceResponse)
def get_workspace(
    team_id: str,
    version_id: str | None = None,
    container: ServiceContainer = Depends(get_container),
) -> TeamWorkspaceResponse:
    workspace = container.team_workspace.get_workspace_view(team_id=team_id, version_id=version_id)
    return TeamWorkspaceResponse(
        team_id=workspace.team_id,
        game_id=workspace.game_id,
        version_id=workspace.version_id,
        slot_states=[
            {
                "slot_key": state.slot_key,
                "state": state.state,
                "required": state.required,
                "code": state.code,
                "revision": state.revision,
            }
            for state in workspace.slot_states
        ],
    )
