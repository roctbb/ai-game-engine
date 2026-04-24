from __future__ import annotations

from app.dependencies import ServiceContainer
from execution.domain.model import Run, RunKind
from identity.domain.model import AppSession, UserRole
from shared.kernel import ForbiddenError, NotFoundError


def ensure_can_view_run(container: ServiceContainer, session: AppSession, run: Run) -> None:
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        return
    if run.requested_by == session.nickname:
        return
    try:
        team = container.team_workspace.get_team(run.team_id)
        if team.captain_user_id == session.nickname:
            return
    except NotFoundError:
        pass

    if run.run_kind is RunKind.TRAINING_MATCH and run.lobby_id:
        try:
            if container.training_lobby.find_user_team_in_lobby(
                lobby_id=run.lobby_id,
                user_id=session.nickname,
            ):
                return
        except NotFoundError:
            pass

    if run.run_kind is RunKind.COMPETITION_MATCH and run.lobby_id:
        try:
            competition = container.competition.get_competition(run.lobby_id)
            user_teams = container.team_workspace.list_teams_by_game_and_captain(
                game_id=run.game_id,
                captain_user_id=session.nickname,
            )
            if any(team.team_id in competition.entrants for team in user_teams):
                return
            if competition.lobby_id and container.training_lobby.find_user_team_in_lobby(
                lobby_id=competition.lobby_id,
                user_id=session.nickname,
            ):
                return
        except NotFoundError:
            pass

    raise ForbiddenError("Просматривать этот запуск может только участник, преподаватель или админ")
