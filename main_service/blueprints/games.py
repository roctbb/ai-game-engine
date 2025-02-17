from flask import Blueprint
from flask import send_file, render_template
from helpers import requires_session
from methods import get_games

games_blueprint = Blueprint('games', __name__)


@games_blueprint.route('/<int:session_id>')
@requires_session
def get_game(game_session):
    return send_file(f'games/{game_session.game.code}/frontend/index.html')


@games_blueprint.route('/<int:session_id>/stats')
@requires_session
def get_stats(game_session):
    return render_template("stats/index.html", game_session=game_session)


@games_blueprint.route('/<code>/static/<path:path>')
def get_static_file(code, path):
    return send_file(f'games/{code}/frontend/static/{path}')


@games_blueprint.route('/')
def index():
    return render_template('games/index.html', games=get_games())
