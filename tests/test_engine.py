import time

from manage import app
from methods import *
from models import *


def test_can_create_engine():
    with app.app_context():
        game = Game.query.filter_by(code='tic_tac_toe').first()
        team1 = Team.query.get(1)
        team2 = Team.query.get(2)

        session = create_session(game, [team1, team2])

        run_engine(session)

        time.sleep(5)

        stop_engine(session)

        time.sleep(6)