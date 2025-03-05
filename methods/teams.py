from models import Team, Player, db
from .exceptions import *

__all__ = ['create_team', 'get_team_by_id', 'get_teams', 'is_team_owner', 'create_player', 'delete_player']


def create_team(name: str, user_id: int, game_id: int) -> Team:
    team = Team(name=name, user_id=user_id, game_id=game_id)

    db.session.add(team)
    db.session.commit()

    return team


def get_team_by_id(team_id: int) -> Team:
    team = Team.query.get(team_id)

    if not team:
        raise NotFound

    return team


def get_teams():
    return Team.query.all()


def is_team_owner(team_id: int, user_id: int) -> bool:
    return get_team_by_id(team_id).user_id == user_id


def create_player(team_id: int, name: str, script: str):
    player = Player(name=name, team_id=team_id, script=script)

    db.session.add(player)
    db.session.commit()


def delete_player(team_id: int, player_id: int):
    player = Player.query.get(player_id)

    if not player:
        raise NotFound

    if player.team_id != team_id:
        raise IncorrectPlayer

    db.session.delete(player)
    db.session.commit()
