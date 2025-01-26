from .exceptions import *
from models import *
from .sessions import *
from .teams import *


def get_lobby(id):
    lobby = Lobby.query.get(id)

    if not lobby:
        raise NotFound

    return lobby


def get_lobbies():
    return Lobby.query.all()


def get_lobby_description(id):
    return get_lobby(id).description


def set_lobby_description(id, description):
    lobby = Lobby.query.get(id)

    lobby.description = description

    db.session.commit()


def get_lobby_teams_ids(lobby_id):
    return [x[1] for x in get_lobby_description(lobby_id).items()]


def is_lobby_owner(lobby_id, user_id):
    return get_lobby(lobby_id).owner_id == user_id

def try_run_lobby(lobby):
    selected_game = lobby.game
    teams = lobby.teams

    if len(teams) >= selected_game.min_teams:
        game_session = create_session(selected_game, teams)
        run_engine(game_session)

def create_lobby(owner_id, game_id):
    lobby = Lobby(owner_id=owner_id, game_id=game_id)

    lobby.description = {}

    db.session.add(lobby)
    db.session.commit()

    return lobby.id


def delete_lobby(lobby_id):
    db.session.delete(get_lobby(lobby_id))
    db.session.commit()
