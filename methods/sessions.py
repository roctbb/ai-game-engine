import json

from config import *
from . import run_engine, stop_engine
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


def create_session(game, teams, user=None):
    from redis_client import redis

    if not game or game.min_teams > len(teams) or len(teams) > game.max_teams:
        raise IncorrectNumberOfTeams

    for team in teams:
        if team.game_id != game.id or len(team.players) < game.min_team_players or len(team.players) > game.max_team_players:
            raise IncorrectTeam

    session = Session(state="created", game_id=game.id, replay=[], created_by=user.id if user else None)

    db.session.add(session)
    db.session.commit()

    for team in teams:
        session.teams.append(team)

    session.description = __generate_description(session)

    db.session.commit()

    redis.set(f'session-{session.id}', session.description)
    run_engine(session)
    return session


def get_session_by_id(session_id):
    session = Session.query.get(session_id)

    if not session:
        raise NotFound

    return session


def restart_session(session):
    session.state = "created"
    session.winner_id = None
    session.stats = []
    session.replay = None

    if session.engine_pid:
        stop_engine(session)

    run_engine(session)


def can_restart_session(session, user):
    return session.creator == user


def mark_started(session):
    session.replay = []
    session.state = "started"
    db.session.commit()


def mark_ended(session):
    session.state = "ended"

    if session.lobby:
        from .lobby import try_run_lobby
        try_run_lobby(session.lobby)

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
