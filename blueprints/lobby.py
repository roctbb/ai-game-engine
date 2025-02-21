from flask import Blueprint
from flask import render_template, redirect, request, abort

from helpers import requires_auth
from methods.auth import get_user_by_id
from methods.exceptions import *
from methods.games import get_games, get_game_by_id
from methods.lobby import *
from methods.teams import get_team_by_id

lobby_blueprint = Blueprint('lobby', __name__)


@lobby_blueprint.route('/')
@requires_auth
def active(user):
    return render_template('lobbies/index.html',
                           lobbies=get_all_lobbies(),
                           games=get_games(),
                           user=user,
                           title='Активные лобби')


@lobby_blueprint.route('/<int:lobby_id>')
@requires_auth
def index(user, lobby_id):
    try:
        lobby = get_lobby_by_id(lobby_id)
    except NotFound:
        return abort(404)

    team_added = any(team.user_id == user.id for team in lobby.teams)
    teams = lobby.teams

    return render_template('lobbies/lobby.html',
                           lobby_id=lobby_id,
                           teams=teams,
                           owner=is_lobby_owner(lobby, user),
                           team_added=team_added,
                           is_ready=is_lobby_ready(lobby))


@lobby_blueprint.route('/create', methods=['GET'])
@requires_auth
def create_page(user):
    if not user.is_admin:
        abort(403)

    return render_template('lobbies/create.html', games=get_games())


@lobby_blueprint.route('/create', methods=['POST'])
@requires_auth
def create(user):
    if not user.is_admin:
        abort(403)

    game_id = request.form.get('game_id')

    try:
        game = get_game_by_id(int(game_id))
    except NotFound:
        return render_template('lobbies/create.html', games=get_games(), error='Выберите игру')

    lobby_id = create_lobby(user, game).id

    return redirect(f'/lobby/{lobby_id}')


@lobby_blueprint.route('/<int:lobby_id>/update', methods=['GET'])
@requires_auth
def update_page(user, lobby_id):
    lobby = get_lobby_by_id(lobby_id)
    teams = list(team for team in user.teams if team.game_id == lobby.game_id)

    return render_template('lobbies/update.html', lobby_id=lobby_id, teams=teams)


@lobby_blueprint.route('/<int:lobby_id>/update', methods=['POST'])
@requires_auth
def update(user, lobby_id):
    team_id = request.form.get('team_id')

    try:
        lobby = get_lobby_by_id(lobby_id)
        team = get_team_by_id(int(team_id))

        team_added = any(team.user_id == user.id for team in lobby.teams)

        if team_added:
            leave_lobby(lobby, user)

        add_team(lobby, team)
    except ExplainableException as e:
        return render_template('lobbies/update.html', lobby_id=lobby_id, error=e.text)

    return redirect(f'/lobby/{lobby_id}')


@lobby_blueprint.route('/<int:lobby_id>/delete/<int:deleted_user_id>', methods=['GET'])
@requires_auth
def delete_user(user, lobby_id, deleted_user_id):
    lobby = get_lobby_by_id(lobby_id)

    if not is_lobby_owner(lobby, user):
        return redirect(f'lobby/{lobby_id}')

    try:
        deleted_user = get_user_by_id(deleted_user_id)
    except NotFound:
        abort(404)

    leave_lobby(lobby, deleted_user)

    return redirect(f'/lobby/{lobby_id}')


@lobby_blueprint.route('/<int:lobby_id>/leave', methods=['GET'])
@requires_auth
def leave_the_lobby(user, lobby_id):
    lobby = get_lobby_by_id(lobby_id)
    leave_lobby(lobby, user)

    return redirect(f'/')


@lobby_blueprint.route('/<int:lobby_id>/launch', methods=['GET'])
@requires_auth
def launch_the_lobby(user, lobby_id):
    try:
        lobby = get_lobby_by_id(lobby_id)
    except NotFound:
        abort(404)

    if not (is_lobby_owner(lobby, user) and is_lobby_ready(lobby)):
        return redirect(f'/lobby/{lobby_id}')

    try:
        session_id = try_run_lobby(lobby)

        return redirect(f'/games/{session_id}' if session_id > -1 else f'/lobby/{lobby_id}')
    except IncorrectNumberOfTeams:
        return redirect(f'/lobby/{lobby_id}')
