from flask import Blueprint
from flask import render_template, redirect, request

from helpers import *
from methods.games import *
from methods.sessions import *
from methods.teams import get_team_by_id

sessions_blueprint = Blueprint('sessions', __name__)


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
def create_page(*_):
    games = get_games()
    return render_template('sessions/create.html', games=games)


@sessions_blueprint.route('/create', methods=['post'])
@requires_auth
def create(user):
    game_id = request.form.get('game_id')
    games = get_games()

    try:
        selected_game = get_game_by_id(game_id)
    except Exception:
        return render_template('sessions/create.html', games=games, error='Выберите игру')

    teams_ids = request.form.getlist('teams')
    if not teams_ids:
        return render_template('sessions/create.html', game=selected_game)

    try:
        teams = [get_team_by_id(int(team_id)) for team_id in teams_ids]
        game_session = create_session(selected_game, teams, user)

        return redirect(f'/games/{game_session.id}')
    except Exception as e:
        print(e)
        return render_template('sessions/create.html', game=selected_game, error='Ошибка запуска')


@sessions_blueprint.route('/<int:session_id>/restart')
@requires_auth
def get_stats(user, session_id):
    session = get_session_by_id(session_id)

    if can_restart_session(session, user):
        restart_session(session)

    return redirect('/sessions')
