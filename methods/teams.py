from .exceptions import *
from models import Team, Player, db


def create_team(name, user_id, game_id):
    team = Team(name=name, user_id=user_id, game_id=game_id)

    db.session.add(team)
    db.session.commit()

    return team


def get_team_by_id(team_id):
    team = Team.query.get(team_id)

    if not team:
        raise NotFound

    return team


def get_teams_by_owner(user_id):
    teams = Team.query.filter_by(user_id=user_id).all()

    return teams


def get_teams():
    return Team.query.all()


def is_team_owner(team_id, user_id):
    return get_team_by_id(team_id).user_id == user_id


def create_player(team_id, name, script):
    player = Player(name=name, team_id=team_id, script=script)

    db.session.add(player)
    db.session.commit()


def delete_player(team_id, player_id):
    player = Player.query.get(player_id)

    if not player:
        raise NotFound

    if player.team_id != team_id:
        raise IncorrectPlayer

    db.session.delete(player)
    db.session.commit()
