import json 

from config import *
from .exceptions import *
from models import Session, db

def __generate_description(session):
    return json.dumps({
        "session_id": session.id,
        "teams": [
            {
                "id": team.id,
                "name": team.name,
                "players": [
                    {
                        "id": player.id,
                        "name": player.name,
                        "script": player.script if player.script else ''
                    } for player in team.players
                ]
            } for team in session.teams
        ]
    })


def create_session(game, teams):
    from redis_client import redis
    
    if not game or (len(teams) != game.team_number and game.team_number != -1):
        raise IncorrectNumberOfTeams

    for team in teams:
        if team.game_id != game.id or len(team.players) != game.team_size:
            raise IncorrectTeam

    session = Session(state="created", game_id=game.id, replay=[])

    db.session.add(session)
    db.session.commit()

    for team in teams:
        session.teams.append(team)

    session.description = __generate_description(session)
    
    db.session.commit()
    
    redis.set(f'session-{session.id}', session.description)

    return session


def get_session_by_id(session_id):
    session = Session.query.get(session_id)

    if not session:
        raise NotFound

    return session


def mark_started(session):
    session.replay = []
    session.state = "started"
    db.session.commit()


def mark_ended(session):
    session.state = "ended"
    db.session.commit()


def set_winner(session, team):
    session.winner_id = team.user_id
    db.session.commit()


def store_for_replay(session, message):
    if not session.replay:
        session.replay = [message]
    else:
        new_record = session.replay[:]
        new_record.append(message)
        session.replay = new_record
    db.session.commit()


def grab_sessions(user):
    teams = user.teams

    sessions = []
    for team in teams:
        sessions.extend(team.sessions)

    sessions = list(set(sessions))

    sessions.sort(key=lambda s: s.created_on)
    return sessions


def get_sessions(state=None):
    if not state:
        return Session.query.all()
    return Session.query.filter_by(state=state).all()
