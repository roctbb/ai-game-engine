from server import *
from config import *

if __name__ == "__main__":
    socketio.run(app, port=PORT, debug=False)