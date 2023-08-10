from .exceptions import *
from models import *


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


def get_lobby_game_id(lobby_id):
    return get_lobby(lobby_id).game_id


def get_lobby_teams_ids(lobby_id):
    return [x[1] for x in get_lobby_description(lobby_id).items()]


def is_lobby_owner(lobby_id, user_id):
    return get_lobby(lobby_id).owner_id == user_id


def create_lobby(owner_id, game_id):
    lobby = Lobby(owner_id=owner_id, game_id=game_id)

    lobby.description = {}

    db.session.add(lobby)
    db.session.commit()

    return lobby.id


def delete_lobby(lobby_id):
    db.session.delete(get_lobby(lobby_id))
    db.session.commit()
