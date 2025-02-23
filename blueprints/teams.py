from re import match

from flask import Blueprint
from flask import render_template, redirect, request, abort

from helpers import requires_auth
from methods import NotFound, IncorrectPlayer
from methods import get_team_by_id, get_games, get_game_by_id, create_team, is_team_owner, delete_player, create_player

teams_blueprint = Blueprint('teams', __name__)


@teams_blueprint.route('/')
@requires_auth
def my(user):
    return render_template('teams/index.html', teams=user.teams)


@teams_blueprint.route('/<int:team_id>')
@requires_auth
def team_info(user, team_id):
    try:
        team = get_team_by_id(team_id)
    except NotFound:
        return abort(404)

    if not is_team_owner(team_id, user.id):
        return redirect('/teams')

    return render_template('teams/team.html', team=team, is_full=(len(team.players) >= team.game.max_team_players))


@teams_blueprint.route('/create', methods=['get'])
@requires_auth
def create_page(*_):
    return render_template('teams/create.html', games=get_games())


@teams_blueprint.route('/create', methods=['post'])
@requires_auth
def create(user):
    team_name = request.form.get('team_name')
    game_id = request.form.get('game_id')

    if not team_name:
        return render_template('teams/create.html', games=get_games(), error='Введите имя команды')

    if not game_id:
        return render_template('teams/create.html', games=get_games(), error='Выберите игру', team_name=team_name)

    if not match(r'^(?!\s*$).+', team_name):
        return render_template('teams/create.html', games=get_games(), error='Имя не должно быть пустым')

    try:
        selected_game = get_game_by_id(int(game_id))
    except NotFound:
        return render_template('teams/create.html', games=get_games(), error='Выберите игру', team_name=team_name)

    create_team(team_name, user.id, selected_game.id)

    return redirect('/teams')


@teams_blueprint.route('/<int:team_id>/add_player', methods=['get'])
@requires_auth
def add_player_page(user, team_id):
    try:
        if not is_team_owner(team_id, user.id):
            return redirect('/teams')
    except NotFound:
        return abort(404)

    return render_template('teams/add_player.html')


@teams_blueprint.route('/<int:team_id>/add_player', methods=['post'])
@requires_auth
def add_player(user, team_id):
    try:
        if not is_team_owner(team_id, user.id):
            return redirect('/teams')
    except NotFound:
        return abort(404)

    team = get_team_by_id(team_id)

    if len(team.players) >= team.game.max_team_players:
        return render_template('teams/add_player.html', error='Команда заполнена')

    player_name = request.form.get('player_name')
    script = request.form.get('script')

    if not player_name:
        return render_template('teams/add_player.html', error='Введите имя команды')

    if not match(r'^(?!\s*$).+', player_name):
        return render_template('teams/add_player.html', error='Имя не должно быть пустым')

    if not script or not match(r'^(?!\s*$).+', script):
        return render_template('teams/add_player.html', error='Введите код', player_name=player_name)

    create_player(team_id, player_name, script)

    return redirect(f'/teams/{team_id}')


@teams_blueprint.route('/<int:team_id>/delete/<int:player_id>')
@requires_auth
def del_player(user, team_id, player_id):
    if not is_team_owner(team_id, user.id):
        return redirect('/teams')

    try:
        delete_player(team_id, player_id)
    except NotFound:
        abort(404)
    except IncorrectPlayer:
        abort(400)

    return redirect(f'/teams/{team_id}')
