from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 15
_HEIGHT = 15
_MAX_TURNS = 260
_START = (1, 1)
_CHARGER = _START
_BATTERY_MAX = 34
_DIRT_TOTAL = 16
_RANDOM_WALLS = 28
_DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    "stay": (0, 0),
}
_BORDER_WALLS = {
    *{(x, 0) for x in range(_WIDTH)},
    *{(x, _HEIGHT - 1) for x in range(_WIDTH)},
    *{(0, y) for y in range(_HEIGHT)},
    *{(_WIDTH - 1, y) for y in range(_HEIGHT)},
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    move_fn, compile_error = _build_player_fn(ctx, events, print_context)
    game_map = _build_map(ctx)
    walls = game_map["walls"]
    dirt = game_map["dirt"]
    assert isinstance(walls, set) and isinstance(dirt, set)

    position = _START
    battery = _BATTERY_MAX
    cleaned = 0
    invalid_moves = 0
    turns = 0
    alive = True
    frames = [_frame(0, "running", position, walls, dirt, battery, cleaned, invalid_moves, alive)]

    for turn in range(_MAX_TURNS):
        if (not dirt and position == _CHARGER) or not alive:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, dirt), battery)
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if target in walls:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        position = target
        turns += 1
        battery -= 1

        if position in dirt:
            dirt.remove(position)
            cleaned += 1
            events.append({"type": "cleaned", "tick": turn + 1, "x": position[0], "y": position[1]})
        if position == _CHARGER:
            battery = _BATTERY_MAX
            events.append({"type": "charged", "tick": turn + 1})
        if battery <= 0 and position != _CHARGER:
            alive = False
            events.append({"type": "battery_empty", "message": "Батарейка разрядилась вне зарядной базы.", "tick": turn + 1})

        frames.append(_frame(turn + 1, "running", position, walls, dirt, battery, cleaned, invalid_moves, alive))

    completed = not dirt and alive and position == _CHARGER
    score = max(0, cleaned * 80 + (250 if completed else 0) + battery - turns - invalid_moves * 10)
    metrics: dict[str, object] = {
        "turns": turns,
        "cleaned": cleaned,
        "dirt_total": _DIRT_TOTAL,
        "dirt_left": len(dirt),
        "battery": battery,
        "battery_max": _BATTERY_MAX,
        "returned_to_base": position == _CHARGER,
        "alive": alive,
        "completed": completed,
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, dirt, battery, cleaned, invalid_moves, alive, score))
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


def _build_map(context: dict[str, Any]) -> dict[str, object]:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "robot_vacuum_offline"
    rng = random.Random(seed)
    cells = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) != _START
    ]
    for _attempt in range(400):
        rng.shuffle(cells)
        walls = set(_BORDER_WALLS) | set(cells[:_RANDOM_WALLS])
        reachable = sorted(_reachable_cells(walls) - {_START})
        if len(reachable) < _DIRT_TOTAL + 12:
            continue
        rng.shuffle(reachable)
        return {"walls": walls, "dirt": set(reachable[:_DIRT_TOTAL])}
    walls = set(_BORDER_WALLS)
    reachable = sorted(_reachable_cells(walls) - {_START})
    rng.shuffle(reachable)
    return {"walls": walls, "dirt": set(reachable[:_DIRT_TOTAL])}


def _build_player_fn(
    context: dict[str, Any],
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[Callable[..., object], str | None]:
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
        "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
        "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], battery: int) -> object:
    try:
        return fn(x, y, board, battery)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _battery: int = 0) -> str:
    return "right"


def _board(walls: set[tuple[int, int]], dirt: set[tuple[int, int]]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in dirt:
        board[x][y] = 1
    board[_CHARGER[0]][_CHARGER[1]] = 2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _reachable_cells(walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue = [_START]
    seen = {_START}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    dirt: set[tuple[int, int]],
    battery: int,
    cleaned: int,
    invalid_moves: int,
    alive: bool,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, dirt),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "charger": {"x": _CHARGER[0], "y": _CHARGER[1]},
        "battery": battery,
        "cleaned": cleaned,
        "dirt_left": len(dirt),
        "invalid_moves": invalid_moves,
        "alive": alive,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
