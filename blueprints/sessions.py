from flask import Blueprint
from flask import render_template
from helpers import *
from methods import *

sessions_blueprint = Blueprint('sessions', __name__)


@sessions_blueprint.route('/')
@requires_auth
def my(user):
    return render_template('sessions/index.html', title="Мои игровые сессии", sessions=grab_sessions(user))


@sessions_blueprint.route('/active')
def active():
    sessions = get_sessions('started')
    return render_template('sessions/index.html', sessions=sessions, title='Активные сессии')


@sessions_blueprint.route('/archive')
def archive():
    sessions = get_sessions('ended')
    return render_template('sessions/index.html', sessions=sessions, title='Завершенные сессии')


@sessions_blueprint.route('/create', methods=['get'])
@requires_auth
def create_page(user):
    games = get_games()
    return render_template('sessions/create.html', games=games)


@sessions_blueprint.route('/create', methods=['post'])
@requires_auth
def create(user):
    game_id = request.form.get('game_id')
    games = get_games()

    try:
        selected_game = get_game_by_id(game_id)
    except:
        return render_template('sessions/create.html', games=games, error="Выберите игру")

    teams_ids = request.form.getlist('teams')
    if not teams_ids:
        return render_template('sessions/create.html', game=selected_game)

    try:
        teams = []
        for team_id in teams_ids:
            teams.append(get_team_by_id(team_id))

        game_session = create_session(selected_game, teams)
        run_engine(game_session)

        return redirect('/sessions')
    except Exception as e:
        print(e)
        return render_template('sessions/create.html', game=selected_game, error="Ошибка запуска")
