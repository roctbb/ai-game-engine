from models import *
from flask import request, abort


def requires_session(func):
    def wrapper(session_id, *args, **kwargs):
        session_id = request.view_args.get('session_id')

        if not session_id:
            abort(404)

        game_session = Session.query.get(session_id)

        if not game_session:
            abort(404)

        return func(game_session, *args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper
