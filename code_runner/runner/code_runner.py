import typing
import inspect

class CodeRunner:
    def __init__(self, code: str):
        self.code = code

    def run(self, 
        func: str,
        timeout: float = 0.5,
        args: tuple[typing.Any] = (),
    ) -> tuple[typing.Any]:
        raise NotImplemented
    