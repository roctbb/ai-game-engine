from flask_socketio import SocketIO
from flask_socketio import join_room, leave_room, send
import redis

socketio = SocketIO(cors_allowed_origins='*')


@socketio.on('subscribe')
def subscribe_to_frames(data):
    if not data or not isinstance(data, dict):
        return

    session_id = data.get('session_id')

    if not session_id:
        return

    join_room(f"session_{session_id}")
    socketio.emit("hello", "test", room=f"session_{session_id}")
    print("joined to room", f"session_{session_id}")
