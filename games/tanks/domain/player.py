from __future__ import annotations

from multiprocessing import Manager, Process
from types import ModuleType
from typing import Any

from domain.general_player import GeneralPlayer


class Player(GeneralPlayer):
    def __init__(self, player, properties=None):
        super().__init__()

        self.player = player
        props = properties or {}

        for key in props:
            self.properties[key] = props[key]

    def _update_decider(self):
        self.decider = lambda x, y, map_state: _timeout_run(0.4, self.player.script, "make_choice", (x, y, map_state))

    def step(self, point, map_state):
        for booster in self.boosters[:]:
            booster.tick()
            if booster.over():
                self.boosters.remove(booster)
        self._update_decider()
        return super(Player, self).step(point, map_state)


def _process_wrapper(script: object, function_name: str, return_dict: object, args: tuple[object, ...]) -> None:
    try:
        target = _resolve_script_callable(script=script, function_name=function_name)
        return_dict["result"] = target(*args)
    except Exception as exc:
        return_dict["exception"] = exc
    return_dict["finished"] = True


def _resolve_script_callable(script: object, function_name: str):
    if isinstance(script, str):
        module = ModuleType("legacy_tanks_player_script")
        exec(script, module.__dict__)
        return getattr(module, function_name)

    get_code = getattr(script, "getCode", None)
    if callable(get_code):
        module = ModuleType("legacy_tanks_player_script")
        exec(str(get_code()), module.__dict__)
        return getattr(module, function_name)

    return getattr(script, function_name)


def _timeout_run(
    timeout: float,
    script: object,
    function_name: str,
    args: tuple[object, ...],
    bypass_errors: bool = True,
) -> Any | None:
    with Manager() as manager:
        return_dict = manager.dict()
        return_dict["result"] = None
        return_dict["exception"] = None
        return_dict["finished"] = False

        process = Process(
            target=_process_wrapper,
            name="legacy-tanks-player-script",
            args=(script, function_name, return_dict, args),
        )
        process.start()
        process.join(timeout=timeout)
        process.terminate()
        result = dict(return_dict)

    if not result["finished"] and not bypass_errors:
        raise TimeoutError

    if result["exception"] and not bypass_errors:
        raise result["exception"]

    if not result["finished"] or result["exception"]:
        return None

    return result["result"]
