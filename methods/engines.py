import json
import os
import subprocess
from config import DEBUG, HOME
from models import db


def stop_engine(session):
    if DEBUG:
        print(
            f" - stopping engine for session [{session.id} / {session.game.code}] with PID [{session.engine_pid}]")

    if session.engine_pid:
        os.system(f'kill {session.engine_pid}')
        session.engine_pid = None

    db.session.commit()


def run_engine(session):
    if session.engine_pid:
        stop_engine(session)

    session.engine_pid = get_pid(session.game.code, session.description)
    db.session.commit()

    if DEBUG:
        print(f" - running engine for session [{session.id} / {session.game.code}] with PID [{session.engine_pid}]")


def get_pid(code, description):
    print(' '.join(['python3', f'{HOME}/games/{code}/engine.py', "'" + json.dumps(description) + "'"]))
    process = subprocess.Popen(['python3', f'{HOME}/games/{code}/engine.py', json.dumps(description)])
    return process.pid
