from flask import Blueprint
from flask import render_template, redirect, request, abort
from helpers import requires_auth
from methods import *

lobby_blueprint = Blueprint('lobby', __name__)


@lobby_blueprint.route('/')
@requires_auth
def active(user):
    return render_template('lobbies/index.html', lobbies=get_lobbies(), title='Активные лобби')


@lobby_blueprint.route('/create', methods=['GET'])
@requires_auth
def create_page(user):
    return render_template('lobbies/create.html', games=get_games())


@lobby_blueprint.route('/create', methods=['POST'])
@requires_auth
def create(user):
    game_id = request.form.get('game_id')

    try:
        get_game_by_id(game_id)
    except:
        return render_template('lobbies/create.html', games=get_games(), error="Выберите игру")

    lobby_id = create_lobby(user.id, game_id)

    return redirect(f'/lobby/{lobby_id}')


@lobby_blueprint.route('/<int:lobby_id>')
@requires_auth
def lobby(user, lobby_id):
    try:
        description = get_lobby_description(lobby_id)
    except NotFound:
        return abort(404)

    team_added = description.get(str(user.id)) is not None

    teams = [get_team_by_id(team_id)
             for team_id in get_lobby_teams_ids(lobby_id)]

    return render_template('lobbies/lobby.html',
                           lobby_id=lobby_id,
                           teams=teams,
                           owner=is_lobby_owner(lobby_id, user.id),
                           team_added=team_added,
                           update=False)


@lobby_blueprint.route('/<int:lobby_id>/update', methods=['GET'])
@requires_auth
def update_page(user, lobby_id):
    teams = get_teams_by_owner(user.id)

    return render_template('lobbies/lobby.html', lobby_id=lobby_id, update=True, teams=teams)


@lobby_blueprint.route('/<int:lobby_id>/update', methods=['POST'])
@requires_auth
def update(user, lobby_id):
    team_id = request.form.get('team_id')

    try:
        get_team_by_id(team_id)
    except:
        return render_template('lobbies/lobby.html', lobby_id=lobby_id, update=True, error="Выберите команду")

    description = get_lobby_description(lobby_id)
    description[user.id] = team_id

    if len(description) > get_game_by_id(get_lobby_game_id(lobby_id)).team_number:
        return render_template('lobbies/lobby.html', lobbies=get_lobbies(), error='Лобби заполнено')

    set_lobby_description(lobby_id, description)

    return redirect(f'/lobby/{lobby_id}')


@lobby_blueprint.route('/<int:lobby_id>/start')
@requires_auth
def start_session(user, lobby_id):
    if not is_lobby_owner(lobby_id, user.id):
        return redirect(f'/{lobby_id}')

    teams_ids = get_lobby_teams_ids(lobby_id)

    try:
        selected_game = get_game_by_id(get_lobby_game_id(lobby_id))
        teams = [get_team_by_id(team_id) for team_id in teams_ids]

        game_session = create_session(selected_game, teams)
        run_engine(game_session)

        delete_lobby(lobby_id)

        return redirect(f'/games/{game_session.id}')
    except Exception as e:
        print(e)

        delete_lobby(lobby_id)

        return render_template('lobbies/index.html', lobbies=get_lobbies(), error="Ошибка запуска")
