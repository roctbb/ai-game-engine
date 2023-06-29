import sys
import time

from manage import *
from methods import get_session_by_id, run_engine

with app.app_context():
    session_id = sys.argv[1]

    session = get_session_by_id(session_id)
    run_engine(session)

    while True:
        time.sleep(1)
