from models import db

__all__ = ['update_session_stats']


def update_session_stats(session, stats):
    session.stats = stats
    db.session.commit()
