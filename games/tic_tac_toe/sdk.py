import time
import redis
import json
import sys
from importlib.machinery import SourceFileLoader
from multiprocessing import Process, Manager


class ScriptWrapper:
    def __init__(self, path):
        self.__path = path

    def __getattribute__(self, attribute):
        if '__' not in attribute:
            module = self.__load_module()
            return getattr(module, attribute)
        else:
            return super().__getattribute__(attribute)

    def __load_module(self):
        name = self.__path.split('/')[-1].rstrip(".py")
        return SourceFileLoader(name, self.__path).load_module()


class RedisClient:
    def __init__(self, session_id):
        self.__redis = redis.Redis(decode_responses=True)
        self.__session_id = session_id

    def __pack_message(self, type, data, elapsed_time):
        return json.dumps({
            "session_id": self.__session_id,
            "data": data,
            "type": type,
            "elapsed": round(elapsed_time, 2)
        })

    def send_message(self, type, elapsed_time, data={}):
        self.__redis.publish("game_engine_notifications", self.__pack_message(type, data, elapsed_time))


class GameEngineTeam:
    def __init__(self, description):
        self.name = description.get('name')
        self.players = [GameEnginePlayer(player_description) for player_description in description.get('players')]


class GameEnginePlayer:
    def __init__(self, description):
        self.name = description.get('name')
        self.script = ScriptWrapper(description.get('script'))


class GameEngineClient:
    def __init__(self):
        if len(sys.argv) > 1:
            self.__description = json.loads(sys.argv[1])
        else:
            self.__description = json.loads(input())

        self.session_id = self.__description.get('session_id')
        self.teams = [GameEngineTeam(team_description) for team_description in self.__description.get('teams')]

        self.__redis_client = RedisClient(self.session_id)
        self.__start_time = 0

    def __elapsed(self):
        return time.time() - self.__start_time

    def send_event(self, event, description={}):
        self.__redis_client.send_message("event", self.__elapsed(), {
            "type": event,
            "description": description
        })

    def start(self):
        self.__start_time = time.time()
        self.send_event("started")

    def end(self):
        self.send_event("ended")

    def send_frame(self, frame):
        self.__redis_client.send_message("frame", self.__elapsed(), frame)

    def send_stats(self, stats):
        self.__redis_client.send_message("stats", self.__elapsed(), stats)


def __proccess_wrapper(module, function_name, return_dict, args):
    try:
        return_dict['result'] = getattr(module, function_name)(*args)
    except Exception as e:
        return_dict['exception'] = e

    return_dict['finished'] = True


def timeout_run(timeout, module, function_name, args):
    with Manager() as manager:

        return_dict = manager.dict()

        return_dict['result'] = None
        return_dict['exception'] = None
        return_dict['finished'] = False

        thread = Process(
            target=__proccess_wrapper,
            name="ABC",
            args=[module, function_name, return_dict, args],
        )

        s = time.time()
        thread.start()
        thread.join(timeout=timeout)
        thread.terminate()

        return_dict = dict(return_dict)

    if not return_dict['finished']:
        raise TimeoutError

    if return_dict['exception']:
        raise return_dict['exception']

    return return_dict["result"]


def measured(func):
    def wrapper(*args, **kwargs):
        start = time.time()

        func(*args, **kwargs)

        end = time.time()

        print(func.__name__, "took", round(end - start, 1), "seconds")

    wrapper.__name__ = func.__name__
    return wrapper
