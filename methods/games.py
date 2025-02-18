from models import Game
from .exceptions import *

__all__ = ['get_game_by_id', 'get_game_by_code', 'get_games']


def get_game_by_id(game_id: int) -> Game:
    game = Game.query.get(game_id)

    if not game:
        raise NotFound

    return game


def get_game_by_code(game_code: str) -> Game:
    game = Game.query.filter_by(code=game_code).first()

    if not game:
        raise NotFound

    return game


def get_games() -> list[Game]:
    return Game.query.all()
