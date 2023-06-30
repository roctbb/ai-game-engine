import redis
import json
import sys
from importlib.machinery import SourceFileLoader


class RedisClient:
    def __init__(self, session_id):
        self.__redis = redis.Redis(decode_responses=True)
        self.__session_id = session_id

    def __pack_message(self, type, data):
        return json.dumps({
            "session_id": self.__session_id,
            "data": data,
            "type": type
        })

    def send_message(self, type, data={}):
        self.__redis.publish("game_engine_notifications", self.__pack_message(type, data))


class GameEngineClient:
    def __init__(self):
        if len(sys.argv) > 1:
            self.__description = json.loads(sys.argv[1])
        else:
            self.__description = json.loads(input())

        self.session_id = self.__description.get('session_id')
        self.teams = self.__description.get('teams')

        self.__redis_client = RedisClient(self.session_id)

    def send_event(self, event, description={}):
        self.__redis_client.send_message("event", {
            "type": event,
            "description": description
        })

    def start(self):
        self.send_event("started")

    def end(self):
        self.send_event("ended")

    def send_frame(self, frame):
        self.__redis_client.send_message("frame", frame)

    def send_stats(self, stats):
        self.__redis_client.send_message("stats", stats)

    def load_script(self, name, path):
        return SourceFileLoader(name, path).load_module()
