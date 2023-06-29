import json
import time
import redis
import sys

r = redis.Redis(decode_responses=True)

session_description = json.loads(sys.argv[1])

print(session_description)

for i in range(100):
    message = {
        "session_id": session_description.get('session_id'),
        "data": {},
        "type": "frame"
    }

    r.publish("game_engine_notifications", json.dumps(message))
    print("sent")
    time.sleep(1)
