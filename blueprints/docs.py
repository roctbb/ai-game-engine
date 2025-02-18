from flask import Blueprint
from flask import send_file, abort

from models import Game

docs_blueprint = Blueprint('docs', __name__)


@docs_blueprint.route('/<string:game_code>')
def get_docs(game_code):
    if len(Game.query.filter_by(code=game_code).all()) == 0:
        abort(404)

    try:
        return send_file(f'./games/{game_code}/frontend/docs.html')
    except FileNotFoundError:
        abort(404)
