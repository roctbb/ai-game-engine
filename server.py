from flask import redirect

from blueprints import *
from helpers import *
from manage import *
from redis_client import redis_client
from socket_server import socketio

app.register_blueprint(auth_blueprint)
app.register_blueprint(docs_blueprint, url_prefix='/docs')
app.register_blueprint(games_blueprint, url_prefix='/games')
app.register_blueprint(stats_blueprint, url_prefix='/stats')
app.register_blueprint(teams_blueprint, url_prefix='/teams')
app.register_blueprint(lobby_blueprint, url_prefix='/lobby')
app.register_blueprint(sessions_blueprint, url_prefix='/sessions')


@app.route('/')
@requires_auth
def index(*_):
    return redirect('/lobby')


if __name__ == '__main__':
    socketio.init_app(app)
    socketio.start_background_task(target=lambda: redis_client(socketio, app))
    socketio.run(app, host=HOST, port=PORT, debug=DEBUG, allow_unsafe_werkzeug=True)
