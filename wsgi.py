from server import *

if __name__ == "__main__":
    socketio.run(app, port=PORT, debug=False)
