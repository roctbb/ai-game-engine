import time
import redis
import json
import sys
import pika
import uuid

from types import ModuleType
from importlib import import_module


class ScriptWrapper:
    def __init__(self, name, code):
        self.__name = name
        self.__code = code

    def __getattribute__(self, attribute):
        if '__' not in attribute and attribute != "getCode":
            module = self.__load_module()
            return getattr(module, attribute)
        else:
            return super().__getattribute__(attribute)

    def __load_module(self):
        module = ModuleType(self.__name)
        exec(self.__code, module.__dict__)

        sys.modules[self.__name] = module

        return import_module(self.__name)

    def getCode(self):
        return self.__code

class RedisClient:
    def __init__(self, session_id, host, port):
        self.__redis = redis.Redis(host=host, port=port, decode_responses=True)
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
        
    def get_description(self):
        return json.loads(self.__redis.get(f'session-{self.__session_id}'))


class GameEngineTeam:
    def __init__(self, description):
        self.name = description.get('name')
        self.id = description.get('id')
        self.players = [GameEnginePlayer(player_description) for player_description in description.get('players')]


class GameEnginePlayer:
    def __init__(self, description):
        self.name = description.get('name')
        self.id = description.get('id')        
        self.script = ScriptWrapper(f'{self.name}_{self.id}', description.get('script'))


class GameEngineClient:
    def __init__(self):
        args = json.loads(sys.argv[1])
        
        self.__redis_client = RedisClient(args['session_id'], args['redis_host'], args['redis_port'])
        
        self.__description = self.__redis_client.get_description()

        self.session_id = self.__description.get('session_id')
        self.teams = [GameEngineTeam(team_description) for team_description in self.__description.get('teams')]

        self.__start_time = 0

    def __elapsed(self):
        return time.time() - self.__start_time

    def send_event(self, event, description={}):
        self.__redis_client.send_message("event", self.__elapsed(), {
            "type": event,
            "description": description
        })

    def set_winner(self, team):
        self.send_event("winner", {"team_id": team.id})

    def start(self):
        self.__start_time = time.time()
        self.send_event("started")

    def end(self):
        self.send_event("ended")

    def send_frame(self, frame):
        self.__redis_client.send_message("frame", self.__elapsed(), frame)

    def send_stats(self, stats):
        self.__redis_client.send_message("stats", self.__elapsed(), stats.get_table())


class GameEngineStats:
    def __init__(self, teams, params):
        self.__teams = teams
        self.__players = {}
        self.__params = []

        self.set_params(params)

    def set_params(self, params):
        self.__params = params

        for team in self.__teams:
            for player in team.players:
                self.__players[player.id] = {
                    param: 0 for param in params
                }

    def set_value(self, player, param, value):
        if param in self.__params:
            self.__players[player.id][param] = value

    def get_value(self, player, param):
        if param in self.__params:
            return self.__players[player.id][param]

    def add_value(self, player, param, value):
        self.set_value(player, param, self.get_value(player, param) + value)

    def get_table(self):
        rows = []

        rows.append({
            "type": "header",
            "cols": [" "] + self.__params
        })

        for team in self.__teams:
            if len(team.players) > 1:
                sums = [0] * len(self.__params)

                for i, param in enumerate(self.__params):
                    for player in team.players:
                        sums[i] += self.__players[player.id][param]

                rows.append({
                    "type": "subheader",
                    "cols": [team.name] + sums
                })

            for player in team.players:
                row = [0] * len(self.__params)

                for i, param in enumerate(self.__params):
                    row[i] += self.__players[player.id][param]

                rows.append({
                    "type": "row",
                    "cols": [player.name] + row
                })

        return rows

class CodeRunnerClient:
    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='localhost'))

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

        self.response = None
        self.corr_id = None

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, code, function_name, args, timeout):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='rpc_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(code, function_name, timeout, args))

    def await_response(self):
        while self.response is None:
            self.connection.process_data_events(time_limit=None)
        return json.loads(self.response)


def timeout_run(timeout, code, function_name, args, bypass_errors=True):
    code_runner = CodeRunnerClient()
    code_runner.call(code, function_name, args, timeout)
    out = code_runner.await_response()
     
    if out[0]:
        if bypass_errors:
            return None
        else:
            raise out[1]
    else:
        return out[1]
    
def 

    

'''app = Celery('tasks', backend="redis://localhost", broker="redis://localhost")

@app.task
def send_code(code, function, args, timeout):
    code_runner = PythonCodeRunner(code, "http://127.0.0.1:2000/api/v2/")
    result = code_runner.run(function, timeout, (args))
    return result'''
