from pyston import PystonClient, File
import asyncio

async def execute(code, func, args, timeout):
    client = PystonClient()

    runner_code = f"from code_file import {func}\nargs = {args}\nout = {func}(args[0])\nprint(out)"

    code_file = File(code, filename="code_file.py")
    runner_file = File(runner_code, filename="runner_file.py")

    output = await client.execute(
        "python",
        [runner_file, code_file],
        run_timeout=timeout
    )
    return output.raw_json['run']['output']

def start_execute(code, func, args, timeout):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(execute(code, func, args, timeout))
    return result