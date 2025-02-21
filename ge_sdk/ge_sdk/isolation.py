import math
import random
import types

__all__ = ['restricted_globals']

allowed_math = types.SimpleNamespace(
    sqrt=math.sqrt,
    pow=math.pow,
    sin=math.sin,
    cos=math.cos,
    log=math.log,
)

allowed_random = types.SimpleNamespace(
    randint=random.randint,
    choice=random.choice,
    shuffle=random.shuffle,
    uniform=random.uniform,
    random=random.random,
)

restricted_globals = {
    "__builtins__": {
        "print": print,
        "len": len,
        "range": range,
        "abs": abs,
        "round": round,
        "sorted": sorted,
        "map": map,
        "filter": filter,
        "enumerate": enumerate,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "tuple": tuple,
        "dict": dict,
        "set": set,
    },
    "math": allowed_math,
    "random": allowed_random,
}
