from .exceptions import *
from models import Team, db


def get_team_by_id(team_id):
    team = Team.query.get(team_id)

    if not team:
        raise NotFound

    return team


def get_teams():
    return Team.query.all()
