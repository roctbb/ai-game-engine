from models import *
from .sessions import *

__all__ = ['get_lobby_by_id', 'get_all_lobbies', 'is_lobby_owner', 'try_run_lobby', 'create_lobby', 'add_team',
           'leave_lobby', 'delete_lobby']


def get_lobby_by_id(lobby_id: int) -> Lobby:
    lobby = Lobby.query.get(lobby_id)

    if not lobby:
        raise NotFound

    return lobby


def get_all_lobbies() -> list[Lobby]:
    return Lobby.query.all()


def is_lobby_owner(lobby: Lobby, user_id: int) -> bool:
    return lobby.owner_id == user_id


def try_run_lobby(lobby: Lobby):
    selected_game = lobby.game
    teams = lobby.teams

    try:
        if len(teams) >= selected_game.min_teams:
            raise IncorrectNumberOfTeams

        game_session = create_session(selected_game, teams)
        run_engine(game_session)
        lobby.is_started = True
    except Exception:
        lobby.is_started = False

    db.session.commit()


def create_lobby(owner: User, game: Game) -> Lobby:
    lobby = Lobby(owner_id=owner.id, game_id=game.id)

    lobby.description = {}

    db.session.add(lobby)
    db.session.commit()

    return lobby


def add_team(lobby: Lobby, new_team: Team):
    if new_team in lobby.teams:
        raise AlreadyExists
    if new_team.game_id != lobby.game_id:
        raise IncorrectTeam
    if len(lobby.teams) == lobby.game.max_teams:
        raise LobbyFull

    lobby.teams = [team for team in lobby.teams if team.user_id != new_team.user_id]
    lobby.teams.append(new_team)

    db.session.commit()


def leave_lobby(lobby: Lobby, user: User):
    lobby.teams = [team for team in lobby.teams if team.user_id != user.id]
    db.session.commit()


def delete_lobby(lobby_id: Lobby):
    db.session.delete(get_lobby_by_id(lobby_id))
    db.session.commit()
