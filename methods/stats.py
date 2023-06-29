from models import db
from .exceptions import *

def update_session_stats(session, stats):
    session.stats = stats
    db.session.commit()