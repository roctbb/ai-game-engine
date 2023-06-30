import json

from manage import *
from config import *
from blueprints import *
from socket_server import socketio, redis_client

app.register_blueprint(games_blueprint, url_prefix='/games')
app.register_blueprint(stats_blueprint, url_prefix='/stats')

if __name__ == '__main__':
    socketio.init_app(app)
    socketio.start_background_task(target=lambda: redis_client(socketio, app))
    print("running socket")
    socketio.run(app, port=PORT, debug=False)
