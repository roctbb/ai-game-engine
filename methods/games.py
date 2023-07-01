from .exceptions import *
from models import Game, db


def get_game_by_id(game_id):
    game = Game.query.get(game_id)

    if not game:
        raise NotFound

    return game


def get_games():
    return Game.query.all()
