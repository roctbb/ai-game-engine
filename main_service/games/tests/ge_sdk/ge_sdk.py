import time
import redis
import json
import sys
import pika
import uuid
from multiprocessing import Process, Manager


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
            pika.ConnectionParameters(
                host='127.0.0.1',
                port='5672',
                virtual_host='/',
                credentials=pika.PlainCredentials(
                    'rmuser',
                    'rmpassword',
                )
            )
        )

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='code_queue_callback')
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

        self.tasks = dict()

    def on_response(self, ch, method, props, body):
        try:
            parsed_response = json.loads(body)

            self.tasks[props.correlation_id].update({
                'status': 'done',
                'response': parsed_response
            })
        except IndexError:
            pass

    def add_task(self, code: str, func: str, args: tuple = (), timeout: float = 0.5) -> uuid.UUID:
        corr_id = str(uuid.uuid4())
        self.tasks[corr_id] = {
            'status': 'queued',
            'id': corr_id,
            'task': {
                'code': code,
                'func': func,
                'args': args,
                'timeout': timeout,
            },
            'response': None,
        }

        self.channel.basic_publish(
            exchange='',
            routing_key='code_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=corr_id,
            ),
            body=json.dumps(self.tasks[corr_id]['task']),
        )
        return corr_id

    def get_response(self, uid: uuid.UUID):
        task = self.tasks.get(uid)
        if task is None:
            return None
        return task['response']

code_runner_client = CodeRunnerClient()

def timeout_run(timeout, code, function_name, args, bypass_errors=True):
    id_ = code_runner_client.add_task(code, function_name, args, timeout)
    
    result = code_runner_client.get_response(id_)
    while result is None:
        result = code_runner_client.get_response(id_)
     
    if result['error']:
        if bypass_errors:
            return None
        else:
            raise Exception
    else:
        return result['return_list']
    
def run_multiple(tasks: list[dict]):
    ids = list()
    results = list()
    for task in tasks:
        ids.append(code_runner_client.add_task(
            task['code'], task['func'], task['args'], task['timeout']
        ))
        results.append(None)

    executed_count = 0
    while executed_count != len(tasks):
        executed_count = 0
        for ind, id_ in enumerate(ids):
            res = code_runner_client.get_response(id_) 
            if res is not None:
                executed_count += 1
                results[ind] = res
        print(executed_count)

    return results

    