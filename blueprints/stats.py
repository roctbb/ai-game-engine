from flask import Blueprint
from flask import render_template

from helpers import requires_session

stats_blueprint = Blueprint('stats', __name__)


@stats_blueprint.route('/<int:session_id>')
@requires_session
def get_stats(game_session):
    return render_template("stats/index.html", game_session=game_session)
