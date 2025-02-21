from .code_runner import CodeRunner
import typing
import inspect
import pyston
import json
import asyncio
import traceback

def _serialize_args(arg: typing.Any, depth: int = 5) -> dict[str, typing.Any]:
    if depth == 0:
        return {'type': 'none'}
    if isinstance(arg, int):
        return {'type': 'int', 'value': str(arg)}
    elif isinstance(arg, float):
        return {'type': 'float', 'value': str(arg)}
    elif isinstance(arg, bool):
        return {'type': 'bool', 'value': str(arg)}
    elif arg is None:
        return {'type': 'none'}
    elif isinstance(arg, str):
        return {'type': 'str', 'value': str(arg)}
    elif isinstance(arg, list):
        return {'type': 'list', 'value': [
            _serialize_args(a, depth=(depth - 1)) for a in arg
        ]}
    elif isinstance(arg, tuple):
        return {'type': 'tuple', 'value': [
            _serialize_args(a, depth=(depth - 1)) for a in arg
        ]}
    elif isinstance(arg, dict):
        return {'type': 'list', 'value': {
            k: _serialize_args(v, depth=(depth - 1)) for k, v in arg
        }}
    else:
        raise ValueError('Unserialized')

def _deserialize_args(ser: dict[str, typing.Any]) -> typing.Any:
    try: 
        if ser['type'] == 'none': return None
        if ser['type'] == 'int': return int(ser['value'])
        if ser['type'] == 'float': return float(ser['value'])
        if ser['type'] == 'bool': return bool(ser['value'])
        if ser['type'] == 'str': return str(ser['value'])
        if ser['type'] == 'Exception': return str(ser['value'])
        if ser['type'] == 'list': return [
            _deserialize_args(a) for a in ser['value']
        ]
        if ser['type'] == 'tuple': return tuple([
            _deserialize_args(a) for a in ser['value']
        ])
        if ser['type'] == 'dict': return {
            k: _deserialize_args(v) for k, v, in ser['value']
        }
    except Exception:
        raise ValueError('Unable to deserialize data')

class PythonCodeRunner(CodeRunner):
    def __init__(self, code: str, base_url: str):
        '''
        base_url inn format = http://container-name:port/api/v2/piston/
        '''

        super().__init__(code)
        self.base_url = base_url

    async def run(self, 
        func: str,
        timeout: float = 0.5,
        args: tuple[typing.Any] = (),
    ) -> tuple[typing.Any]:
        assert isinstance(args, tuple)

        # 'http://127.0.0.1:3000/api/v2/piston/'
        self.client = pyston.PystonClient(base_url=self.base_url)

        _serialize_args_code = inspect.getsource(_serialize_args).replace('\t', '    ').replace('\n', '\n    ')
        _deserialize_args_code = inspect.getsource(_deserialize_args).replace('\t', '    ').replace('\n', '\n    ')

        runner_code = f'''
try:
    import json
    import traceback
    import typing

    { _serialize_args_code }

    { _deserialize_args_code }

    from code_file import { func }

    args = _deserialize_args(json.loads(\'{ json.dumps(_serialize_args(args)) }\'))
    out = { func }(*args)

    print(json.dumps(_serialize_args(out)))
except Exception as e:
    print(json.dumps({{"type": "Exception", "value": traceback.format_exc()}}))
'''
        
        code_file = pyston.File(self.code, filename='code_file.py')
        runner_file = pyston.File(runner_code, filename='runner_file.py')   

        output = await self.client.execute(
            'python',
            [runner_file, code_file],
            run_timeout=timeout
        )

        await self.client.close_session()

        try:
            output_dict = json.loads(str(output))

            if output_dict['type'] == 'exception':
                return (True, output_dict['value'])
            else:
                return_things = _deserialize_args(output_dict)
                if not isinstance(return_things, tuple):
                    return (False, tuple([return_things]))
                return (False, _deserialize_args(output_dict))
        except Exception:
            return (True, traceback.format_exc())

EXAMPLE_CODE = '''
def func(a, b):
    return (a + b)
'''

# some code for debug
if __name__ == '__main__':
    runner = PythonCodeRunner(
        EXAMPLE_CODE,
        'http://127.0.0.1:2000/api/v2/'
    )

    loop = asyncio.get_event_loop()
    print(loop.run_until_complete(runner.run('func', timeout=0.5, args=(1, 2))))
