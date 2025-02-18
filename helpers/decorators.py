from flask import request, abort, session, redirect

from models import *

__all__ = ['requires_auth', 'requires_session']


def requires_auth(func):
    def wrapper(*args, **kwargs):
        if not session.get('login'):
            return redirect('/login')
        user = User.query.filter_by(login=session.get('login')).first()
        if not user:
            return redirect('/login')
        return func(user, *args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


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
