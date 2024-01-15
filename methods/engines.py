import json
import os
import subprocess
from config import DEBUG, REDIS_HOST, REDIS_PORT
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

    session.engine_pid = create_process(session.id, session.game.code)
    db.session.commit()

    if DEBUG:
        print(f" - running engine for session [{session.id} / {session.game.code}] with PID [{session.engine_pid}]")


def create_process(session_id, code):
    process = subprocess.Popen(['python', f'games/{code}/engine.py', json.dumps({'session_id':session_id, 'redis_host': REDIS_HOST, 'redis_port': REDIS_PORT})])
    return process.pid
