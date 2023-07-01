import json
from flask import redirect
from manage import *
from config import *
from blueprints import *
from helpers import *
from socket_server import socketio, redis_client

app.register_blueprint(games_blueprint, url_prefix='/games')
app.register_blueprint(stats_blueprint, url_prefix='/stats')
app.register_blueprint(auth_blueprint)
app.register_blueprint(sessions_blueprint, url_prefix='/sessions')


@app.route('/')
@requires_auth
def index(user):
    return redirect('/sessions')


if __name__ == '__main__':
    socketio.init_app(app)
    socketio.start_background_task(target=lambda: redis_client(socketio, app))
    print("running socket")
    socketio.run(app, port=PORT, debug=False)
