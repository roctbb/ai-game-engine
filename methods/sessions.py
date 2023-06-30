import os
import subprocess
from config import *
from .exceptions import *
from models import Session, db


def session_path(session):
    return f'{HOME}/sessions/session_{session.id}'


def __write_player(path, player):
    with open(f"{path}/player_{player.id}.py", mode='w') as file:
        file.write(player.script)


def __write_player_files(session):
    path = session_path(session)
    os.mkdir(path)

    for team in session.teams:
        for player in team.players:
            __write_player(path, player)


def __generate_description(session):
    path = session_path(session)

    return {
        "session_id": session.id,
        "teams": [
            {
                "name": team.name,
                "players": [
                    {
                        "name": player.name,
                        "script": f"{path}/player_{player.id}.py"
                    } for player in team.players
                ]
            } for team in session.teams
        ]
    }


def create_session(game, teams):
    if not game or len(teams) != game.team_number:
        raise IncorrectNumberOfTeams

    for team in teams:
        if team.game_id != game.id or len(team.players) != game.team_size:
            raise IncorrectTeam

    session = Session(state="created", game_id=game.id, replay=[])

    db.session.add(session)
    db.session.commit()

    for team in teams:
        session.teams.append(team)

    __write_player_files(session)
    session.description = __generate_description(session)

    db.session.commit()

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


def store_for_replay(session, message):
    if not session.replay:
        session.replay = [message]
    else:
        new_record = session.replay[:]
        new_record.append(message)
        session.replay = new_record
    db.session.commit()
