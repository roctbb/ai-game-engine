import asyncio
import json
import sys
import time
from importlib import import_module
from types import ModuleType

import redis

from .isolation import restricted_globals

__all__ = [
    'ScriptWrapper',
    'RedisClient',
    'GameEngineTeam',
    'GameEnginePlayer',
    'GameEngineClient',
    'GameEngineStats',
    'timeout_run',
]


class ScriptWrapper:
    def __init__(self, name, code):
        self.__name = name
        self.__code = code
        self.__module = self.__load_module()

    def __getattribute__(self, attribute):
        if '__' not in attribute and attribute != 'get_code':
            return getattr(self.__module, attribute)
        else:
            return super().__getattribute__(attribute)

    def __load_module(self):
        module = ModuleType(self.__name)

        try:
            exec(self.__code, restricted_globals, module.__dict__)
        except Exception as e:
            raise RuntimeError(f'Failed to load module {self.__name}: {str(e)}')

        sys.modules[self.__name] = module

        return import_module(self.__name)

    def __del__(self):
        if self.__name in sys.modules:
            del sys.modules[self.__name]

    def get_code(self):
        return self.__code


class RedisClient:
    def __init__(self, session_id, host, port):
        self.__redis = redis.Redis(host=host, port=port, decode_responses=True)
        self.__session_id = session_id

    def __pack_message(self, dtype, data, elapsed_time):
        return json.dumps({
            'session_id': self.__session_id,
            'data': data,
            'type': dtype,
            'elapsed': round(elapsed_time, 2)
        })

    def send_message(self, dtype, elapsed_time, data: dict = None):
        self.__redis.publish('game_engine_notifications', self.__pack_message(dtype, data, elapsed_time))

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

    def send_event(self, event, description: dict = None):
        self.__redis_client.send_message('event', self.__elapsed(), {
            'type': event,
            'description': description
        })

    def set_winner(self, team):
        self.send_event('winner', {'team_id': team.id})

    def start(self):
        self.__start_time = time.time()
        self.send_event('started')

    def end(self):
        self.send_event('ended')

    def send_frame(self, frame):
        self.__redis_client.send_message('frame', self.__elapsed(), frame)

    def send_stats(self, stats):
        self.__redis_client.send_message('stats', self.__elapsed(), stats.get_table())


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
        rows = [{
            'type': 'header',
            'cols': [' '] + self.__params
        }]

        for team in self.__teams:
            if len(team.players) > 1:
                sums = [0] * len(self.__params)

                for i, param in enumerate(self.__params):
                    for player in team.players:
                        sums[i] += self.__players[player.id][param]

                rows.append({
                    'type': 'subheader',
                    'cols': [team.name] + sums
                })

            for player in team.players:
                row = [0] * len(self.__params)

                for i, param in enumerate(self.__params):
                    row[i] += self.__players[player.id][param]

                rows.append({
                    'type': 'row',
                    'cols': [player.name] + row
                })

        return rows


def __process_wrapper(module, function_name, args):
    try:
        result = getattr(module, function_name)(*args)
    except Exception as e:
        return {'result': None, 'exception': e, 'finished': True}
    return {'result': result, 'exception': None, 'finished': True}


def timeout_run(timeout, module, function_name, args, bypass_errors=True):
    try:
        return_dict = asyncio.run(asyncio.wait_for(
            asyncio.to_thread(__process_wrapper, module, function_name, args),
            timeout=timeout
        ))
    except asyncio.TimeoutError:
        return_dict = {'result': None, 'exception': None, 'finished': False}

    if not return_dict['finished'] and not bypass_errors:
        raise TimeoutError('Function execution timed out')

    if return_dict['exception'] and not bypass_errors:
        raise return_dict['exception']

    if not return_dict['finished'] or return_dict['exception']:
        return None

    return return_dict['result']
