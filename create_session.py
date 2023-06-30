import sys
import time
from models import *
from manage import *
from methods import get_session_by_id, run_engine, create_session

with app.app_context():
    code = sys.argv[1]
    teams = sys.argv[2:]

    game = Game.query.filter_by(code=code).first()

    teams = [Team.query.get(team_id) for team_id in teams]
    session = create_session(game, teams)
    run_engine(session)

    while True:
        time.sleep(1)
