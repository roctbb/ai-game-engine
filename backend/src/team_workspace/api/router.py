from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_session
from app.dependencies import ServiceContainer, get_container
from identity.domain.model import AppSession, UserRole
from shared.kernel import ForbiddenError
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
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> list[TeamResponse]:
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        teams = container.team_workspace.list_teams_by_game(game_id=game_id)
    else:
        teams = container.team_workspace.list_teams_by_game_and_captain(
            game_id=game_id,
            captain_user_id=session.nickname,
        )
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
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> TeamResponse:
    captain_user_id = (
        request.captain_user_id
        if session.role in {UserRole.TEACHER, UserRole.ADMIN}
        else session.nickname
    )
    team = container.team_workspace.create_team(
        game_id=request.game_id,
        name=request.name,
        captain_user_id=captain_user_id,
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
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> TeamResponse:
    existing = container.team_workspace.get_team(team_id)
    if existing.captain_user_id != session.nickname and session.role not in {UserRole.TEACHER, UserRole.ADMIN}:
        raise ForbiddenError("Редактировать код может только владелец игрока, преподаватель или админ")
    actor_user_id = (
        existing.captain_user_id
        if session.role in {UserRole.TEACHER, UserRole.ADMIN}
        else session.nickname
    )
    if session.role not in {UserRole.TEACHER, UserRole.ADMIN}:
        container.competition.assert_team_code_can_be_updated(team_id=team_id)
    team = container.team_workspace.update_slot_code(
        team_id=team_id,
        actor_user_id=actor_user_id,
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
    session: AppSession = Depends(get_current_session),
    container: ServiceContainer = Depends(get_container),
) -> TeamWorkspaceResponse:
    workspace = container.team_workspace.get_workspace_view(team_id=team_id, version_id=version_id)
    if workspace.captain_user_id != session.nickname and session.role not in {UserRole.TEACHER, UserRole.ADMIN}:
        raise ForbiddenError("Просматривать workspace может только капитан, преподаватель или админ")
    return TeamWorkspaceResponse(
        team_id=workspace.team_id,
        game_id=workspace.game_id,
        captain_user_id=workspace.captain_user_id,
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
