import redis
import json
import sys


class GameEngineClient:
    def __init__(self):
        self.__redis = redis.Redis(decode_responses=True)
        self.__description = json.loads(sys.argv[1])

        self.session_id = self.__description.get('session_id')
        self.teams = self.__description.get('teams')

    def __pack_message(self, type, data):
        return json.dumps({
            "session_id": self.session_id,
            "data": data,
            "type": type
        })

    def __send_message(self, type, data={}):
        self.__redis.publish("game_engine_notifications", self.__pack_message(type, data))

    def send_event(self, event, description={}):
        self.__send_message("event", {
            "type": event,
            "description": description
        })

    def start(self):
        self.send_event("started")

    def end(self):
        self.send_event("ended")

    def send_frame(self, frame):
        self.__send_message("frame", frame)

    def send_stats(self, stats):
        self.__send_message("stats", stats)
