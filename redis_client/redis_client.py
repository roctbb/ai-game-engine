import json
from redis import Redis

from config import REDIS_HOST, REDIS_PORT
from methods import *

redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def process_message(message, socket_server):
    session_id = message.get('session_id')

    session = get_session_by_id(session_id)
    store_for_replay(session, message)

    if message.get('type') == 'frame':
        socket_server.emit("frame", json.dumps(message.get('data')), room=f"session_{session_id}")

    if message.get('type') == 'stats':
        update_session_stats(session, message.get('data'))
        socket_server.emit("stats", json.dumps(message.get('data')), room=f"stats_{session_id}")

    if message.get('type') == 'event':
        event = message.get('data', {})
        event_type = event.get('type')
        event_description = event.get('description', {})

        if event_type == 'ended':
            mark_ended(session)
            stop_engine(session)

        if event_type == 'winner':
            winner_team = get_team_by_id(event_description.get('team_id'))
            set_winner(session, winner_team)

        if event_type == 'started':
            mark_started(session)

        socket_server.emit("event", json.dumps(message.get('data')), room=f"session_{session_id}")


def redis_client(socket_server, app):
    with app.app_context():
        p = redis.pubsub()
        p.subscribe('game_engine_notifications')

        print("connected to Redis")

        while True:
            message = p.get_message()
            if message:
                print(message)
                if message.get('type') == 'message':
                    data = json.loads(message.get('data'))
                    try:
                        process_message(data, socket_server)
                    except Exception as e:
                        print("Message processing exception:", e)

            socket_server.sleep(0.1)
