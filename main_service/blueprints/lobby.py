from flask import Blueprint
from flask import render_template, redirect, request, abort
from helpers import requires_auth
from methods import *

lobby_blueprint = Blueprint('lobby', __name__)


@lobby_blueprint.route('/')
@requires_auth
def active(user):
    return render_template('lobbies/index.html', lobbies=get_all_lobbies(), games=get_games(), user=user,
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
                           update=False)


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
        game = get_game_by_id(game_id)
    except:
        return render_template('lobbies/create.html', games=get_games(), error="Выберите игру")

    lobby_id = create_lobby(user, game).id

    return redirect(f'/lobby/{lobby_id}')


@lobby_blueprint.route('/<int:lobby_id>/update', methods=['GET'])
@requires_auth
def update_page(user, lobby_id):
    lobby = get_lobby_by_id(lobby_id)
    teams = list(team for team in user.teams if team.game_id == lobby.game_id)
    return render_template('lobbies/lobby.html', lobby_id=lobby_id, update=True, teams=teams)


@lobby_blueprint.route('/<int:lobby_id>/update', methods=['POST'])
@requires_auth
def update(user, lobby_id):
    team_id = request.form.get('team_id')

    try:
        lobby = get_lobby_by_id(lobby_id)
        team = get_team_by_id(team_id)

        add_team(lobby, team)

    except ExplainableException as e:
        return render_template('lobbies/lobby.html', lobby_id=lobby_id, update=True, error=e.text)

    return redirect(f'/lobby/{lobby_id}')


@lobby_blueprint.route('/<int:lobby_id>/delete/<int:id>', methods=['GET'])
@requires_auth
def delete_user(user, lobby_id, id):
    lobby = get_lobby_by_id(lobby_id)

    if not is_lobby_owner(lobby, user):
        return redirect(f'/{lobby_id}')

    return redirect(f'/lobby/{lobby_id}')


@lobby_blueprint.route('/<int:lobby_id>/leave', methods=['GET'])
@requires_auth
def leave_the_lobby(user, lobby_id):
    lobby = get_lobby_by_id(lobby_id)
    leave_lobby(lobby, user)

    return redirect(f'/')
