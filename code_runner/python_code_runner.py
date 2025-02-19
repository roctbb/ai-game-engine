from .code_runner import CodeRunner
import typing
import inspect
import pyston
import json
import asyncio

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
        if ser['type'] == 'list': return [
            _deserialize_args(a) for a in ser['value']
        ]
        if ser['type'] == 'dict': return {
            k: _deserialize_args(v) for k, v, in ser['value']
        }
    except Exception:
        raise ValueError('Unable to deserialize data')

class PythonCodeRunner(CodeRunner):
    def run(self, 
        func: str,
        timeout: float = 0.5,
        args: tuple[typing.Any] = (),
    ) -> tuple[typing.Any]:
        assert isinstance(args, tuple)

        client = pyston.PystonClient()

        runner_code = f'''
try:
    import json
    import traceback

    { inspect.get_source(_serialize_args) }

    { inspect.get_source(_deserialize_args) }

    from code_file import { func }

    args = _deserialize_args(json.loads(\'{ json.dumps(_serialize_args(args)) }\'))
    out = { func }(*args)

    print(json.dumps(_serialize_args(out)))
except Exception as e:
    print(json.dumps({{"type": "Exception", "value": traceback.format_exc()}}))
'''
        
        code_file = pyston.File(self.code, filename='code_file.py')
        runner_file = pyston.File(runner_code, filename='runner_file.py')

        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

        output = loop.run_until_complete(client.execute(
            'python',
            [runner_file, code_file],
            run_timeout=timeout
        ))

        try:
            output_dict = json.loads(output)

            if output_dict['type'] == 'exception':
                return (True, output_dict['value'])
            else:
                return (False, _deserialize_args(output_dict))
        except Exception:
            return (True, 'Unable to deserealize data')
        
