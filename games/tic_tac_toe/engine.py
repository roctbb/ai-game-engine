import json
import time
import redis

r = redis.Redis(decode_responses=True)

for i in range(100):

    message = {
        "session_id": 1,
        "data": {},
        "type": "frame"
    }

    r.publish("game_engine_notifications", json.dumps(message))
    print("sent")
    time.sleep(1)
