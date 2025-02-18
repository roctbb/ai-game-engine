import json

from flask import request
from flask_socketio import SocketIO
from flask_socketio import join_room

from methods import get_session_by_id, NotFound

socketio = SocketIO(cors_allowed_origins='*', async_mode='threading')


@socketio.on('subscribe')
def subscribe_to_frames(data):
    if not data or not isinstance(data, dict):
        return

    session_id = data.get('session_id')

    if not session_id:
        return

    try:
        session = get_session_by_id(session_id)

        if data.get('mode') == 'game':
            if session.state == "ended":
                socketio.emit("replay", json.dumps(session.replay), to=request.sid)
                print("sent replay to", request.sid)
            else:
                join_room(f"session_{session_id}")
                socketio.emit("hello", "test", room=f"session_{session_id}")
                print("joined to room", f"session_{session_id}")

        if data.get('mode') == 'stats':
            socketio.emit("stats", json.dumps(session.stats), to=request.sid)
            join_room(f"stats_{session_id}")
    except NotFound:
        socketio.emit("error", {"message": "Session not found"}, to=request.sid)
