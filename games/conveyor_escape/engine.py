from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 90
_START = (1, 1)
_RANDOM_WALLS = 16
_CONVEYORS_TOTAL = 18
_DELTAS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0), "stay": (0, 0)}
_CONVEYOR_VALUES = {"up": 2, "right": 3, "down": 4, "left": 5}
_VALUE_TO_ACTION = {value: action for action, value in _CONVEYOR_VALUES.items()}
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
    conveyors = game_map["conveyors"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(conveyors, dict) and isinstance(exit_cell, tuple)

    position = _START
    invalid_moves = 0
    conveyor_steps = 0
    escaped = False
    turns = 0
    frames = [_frame(0, "running", position, walls, conveyors, exit_cell, conveyor_steps, escaped, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, conveyors, exit_cell))
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target, pushed, blocked = _transition(position, str(action), walls, conveyors)
        if blocked:
            invalid_moves += 1
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        if pushed:
            conveyor_steps += pushed
            events.append({"type": "conveyor", "tick": turn + 1, "steps": pushed})
        position = target
        turns = turn + 1
        if position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, conveyors, exit_cell, conveyor_steps, escaped, invalid_moves))

    score = max(0, (450 if escaped else 0) + conveyor_steps * 4 - turns * 2 - invalid_moves * 12)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "conveyors_total": len(conveyors),
        "conveyor_steps": conveyor_steps,
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, conveyors, exit_cell, conveyor_steps, escaped, invalid_moves, score))
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
        seed = "conveyor_escape_offline"
    rng = random.Random(seed)
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) != _START]
    for _attempt in range(700):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        conveyor_cells = candidates[_RANDOM_WALLS:_RANDOM_WALLS + _CONVEYORS_TOTAL]
        conveyors = {cell: rng.choice(("up", "right", "down", "left")) for cell in conveyor_cells if cell not in walls}
        reachable = sorted(_reachable_cells(_START, walls, conveyors) - {_START} - set(conveyors))
        if len(reachable) < 8:
            continue
        exit_cell = max(reachable, key=lambda cell: abs(cell[0] - _START[0]) + abs(cell[1] - _START[1]))
        return {"walls": walls, "conveyors": conveyors, "exit": exit_cell}
    walls = set(_BORDER_WALLS)
    conveyors = {(3, 1): "right", (5, 1): "down", (5, 4): "right", (8, 4): "down", (8, 8): "left"}
    return {"walls": walls, "conveyors": conveyors, "exit": (3, 8)}


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
        "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
        "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]]) -> object:
    try:
        return fn(x, y, board)
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]]) -> str:
    return "right"


def _board(walls: set[tuple[int, int]], conveyors: dict[tuple[int, int], str], exit_cell: tuple[int, int]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for (x, y), action in conveyors.items():
        board[x][y] = _CONVEYOR_VALUES[action]
    board[exit_cell[0]][exit_cell[1]] = 1
    return board


def _transition(position: tuple[int, int], action: str, walls: set[tuple[int, int]], conveyors: dict[tuple[int, int], str]) -> tuple[tuple[int, int], int, bool]:
    target = _move(position, action)
    if not _inside(target) or target in walls:
        return position, 0, True
    pushed = 0
    seen = {target}
    current = target
    while current in conveyors:
        nxt = _move(current, conveyors[current])
        if not _inside(nxt) or nxt in walls:
            return current, pushed, False
        if nxt in seen:
            return current, pushed, False
        seen.add(nxt)
        current = nxt
        pushed += 1
    return current, pushed, False


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]], conveyors: dict[tuple[int, int], str]) -> set[tuple[int, int]]:
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "right", "down", "left"):
            nxt, _pushed, blocked = _transition(current, action, walls, conveyors)
            if blocked or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    conveyors: dict[tuple[int, int], str],
    exit_cell: tuple[int, int],
    conveyor_steps: int,
    escaped: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, conveyors, exit_cell),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "conveyor_steps": conveyor_steps,
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
