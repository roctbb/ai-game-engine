from flask import Blueprint
from flask import send_file

from helpers import requires_game

games_blueprint = Blueprint('games', __name__)


@games_blueprint.route('/<int:session_id>')
@requires_game
def get_game(game):
    return send_file(f'./games/{game.code}/frontend/index.html')


@games_blueprint.route('/<code>/static/<path>')
def get_static_file(code, path):
    return send_file(f'./games/{code}/frontend/static/{path}')
