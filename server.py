import json

from manage import *
from config import *
from blueprints import *
from socket_server import socketio, redis_client

app.register_blueprint(games_blueprint, url_prefix='/games')

if __name__ == '__main__':
    socketio.init_app(app)
    socketio.start_background_task(target=lambda: redis_client(socketio))
    print("running socket")
    socketio.run(app, port=PORT, debug=False)
