import redis
import json
from methods import *


def process_message(message, socket_server):
    session_id = message.get('session_id')

    session = get_session_by_id(session_id)
    store_for_replay(session, message)

    if message.get('type') == 'frame':
        socket_server.emit("frame", json.dumps(message.get('data')), room=f"session_{session_id}")

    if message.get('type') == 'stats':
        update_session_stats(session, message.get('data'))
        socket_server.emit("update", json.dumps(message.get('data')), room=f"stats_{session_id}")

    if message.get('type') == 'event':
        event = message.get('data', {})

        if event.get('type') == 'ended':
            mark_started(session)
            stop_engine(session)

        if event.get('type') == 'started':
            mark_started(session)

        socket_server.emit("event", json.dumps(message.get('data')), room=f"session_{session_id}")


def redis_client(socket_server, app):
    with app.app_context():
        r = redis.Redis(decode_responses=True)
        p = r.pubsub()
        p.subscribe('game_engine_notifications')

        print("connected to Redis")

        while True:
            message = p.get_message()
            if message:
                print(message)
                if message.get('type') == 'message':
                    data = json.loads(message.get('data'))
                    process_message(data, socket_server)
            socket_server.sleep(0.1)
