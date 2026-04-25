from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 11
_HEIGHT = 11
_MAX_TURNS = 90
_START = (5, 10)
_FINISH = (5, 0)
_LANES = tuple(range(1, 10))
_CARS_PER_LANE = 2
_DELTAS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0), "stay": (0, 0)}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    move_fn, compile_error = _build_player_fn(ctx, events, print_context)
    cars = _build_cars(ctx)
    position = _START
    invalid_moves = 0
    car_hits = 0
    escaped = False
    turns = 0
    frames = [_frame(0, "running", position, cars, escaped, invalid_moves, car_hits)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(cars))
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if not _inside(target) or target in cars:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_step", "tick": turn, "action": action})

        cars = _advance_cars(cars)
        position = target
        turns = turn + 1
        if position in cars:
            car_hits += 1
            position = _START
            events.append({"type": "car_hit", "tick": turns})
        if position == _FINISH:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, cars, escaped, invalid_moves, car_hits))

    score = max(0, (500 if escaped else 0) - turns * 3 - invalid_moves * 10 - car_hits * 80)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "lanes_total": len(_LANES),
        "cars_total": len(cars),
        "invalid_moves": invalid_moves,
        "car_hits": car_hits,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, cars, escaped, invalid_moves, car_hits, score))
    return {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "replay_ref": None}


def _load_context() -> dict[str, Any]:
    raw = os.getenv("AGP_RUN_CONTEXT")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_cars(context: dict[str, Any]) -> set[tuple[int, int]]:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "road_crossing_offline"
    rng = random.Random(seed)
    cars: set[tuple[int, int]] = set()
    for y in _LANES:
        start = rng.randrange(_WIDTH)
        gap = rng.randrange(4, 7)
        for index in range(_CARS_PER_LANE):
            cars.add(((start + index * gap) % _WIDTH, y))
    return cars


def _build_player_fn(context: dict[str, Any], events: list[dict[str, object]], print_context: dict[str, int]) -> tuple[Callable[..., object], str | None]:
    code = ""
    codes = context.get("codes_by_slot")
    if isinstance(codes, dict) and isinstance(codes.get("agent"), str):
        code = str(codes["agent"])
    namespace = {"__builtins__": _builtins(events, print_context)}
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("make_move") or namespace.get("choose_move")
    return (fn if callable(fn) else _fallback_move), compile_error


def _builtins(events: list[dict[str, object]], print_context: dict[str, int]) -> dict[str, object]:
    def bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message += end
        for line in message.splitlines() or [""]:
            events.append({"type": "bot_print", "tick": int(print_context.get("tick", 0)), "role": "agent", "message": line})

    return {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
        "float": float, "frozenset": frozenset, "int": int, "len": len, "list": list, "max": max, "min": min,
        "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]]) -> object:
    try:
        return fn(x, y, board)
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]]) -> str:
    return "up"


def _board(cars: set[tuple[int, int]]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in cars:
        board[x][y] = -1
    board[_FINISH[0]][_FINISH[1]] = 1
    return board


def _advance_cars(cars: set[tuple[int, int]]) -> set[tuple[int, int]]:
    moved = set()
    for x, y in cars:
        dx = 1 if y % 2 == 1 else -1
        moved.add(((x + dx) % _WIDTH, y))
    return moved


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    cars: set[tuple[int, int]],
    escaped: bool,
    invalid_moves: int,
    car_hits: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(cars),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "finish": {"x": _FINISH[0], "y": _FINISH[1]},
        "escaped": escaped,
        "invalid_moves": invalid_moves,
        "car_hits": car_hits,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
