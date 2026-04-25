from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 120
_START = (1, 1)
_RANDOM_WALLS = 18
_JUMPS_TOTAL = 18
_DELTAS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0), "stay": (0, 0)}
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
    jumps = game_map["jumps"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(jumps, dict) and isinstance(exit_cell, tuple)

    position = _START
    invalid_moves = 0
    jump_moves = 0
    escaped = False
    turns = 0
    frames = [_frame(0, "running", position, walls, jumps, exit_cell, jump_moves, escaped, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, jumps, exit_cell))
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target, distance = _transition(position, str(action), walls, jumps)
        if target == position and action != "stay":
            invalid_moves += 1
            events.append({"type": "blocked_jump", "tick": turn, "action": action})
        if distance > 1:
            jump_moves += 1
            events.append({"type": "jump", "tick": turn + 1, "distance": distance})

        position = target
        turns = turn + 1
        if position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, jumps, exit_cell, jump_moves, escaped, invalid_moves))

    score = max(0, (450 if escaped else 0) + jump_moves * 8 - turns * 2 - invalid_moves * 12)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "solved": escaped,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "jumps_total": len(jumps),
        "jump_moves": jump_moves,
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, jumps, exit_cell, jump_moves, escaped, invalid_moves, score))
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
        seed = "jump_maze_offline"
    rng = random.Random(seed)
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) != _START]
    for _attempt in range(800):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        jump_cells = [cell for cell in candidates[_RANDOM_WALLS:_RANDOM_WALLS + _JUMPS_TOTAL] if cell not in walls]
        jumps = {cell: rng.choice((2, 3)) for cell in jump_cells}
        reachable = sorted(_reachable_cells(_START, walls, jumps) - {_START} - set(jumps))
        if len(reachable) < 8:
            continue
        exit_cell = max(reachable, key=lambda cell: abs(cell[0] - _START[0]) + abs(cell[1] - _START[1]))
        return {"walls": walls, "jumps": jumps, "exit": exit_cell}
    walls = set(_BORDER_WALLS)
    jumps = {(3, 1): 2, (5, 1): 3, (5, 4): 2, (8, 4): 3, (8, 7): 2}
    return {"walls": walls, "jumps": jumps, "exit": (10, 10)}


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


def _board(walls: set[tuple[int, int]], jumps: dict[tuple[int, int], int], exit_cell: tuple[int, int]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for (x, y), distance in jumps.items():
        board[x][y] = distance
    board[exit_cell[0]][exit_cell[1]] = 1
    return board


def _transition(position: tuple[int, int], action: str, walls: set[tuple[int, int]], jumps: dict[tuple[int, int], int]) -> tuple[tuple[int, int], int]:
    if action == "stay":
        return position, 0
    distance = jumps.get(position, 1)
    dx, dy = _DELTAS[action]
    target = (position[0] + dx * distance, position[1] + dy * distance)
    if not _inside(target) or target in walls:
        return position, distance
    return target, distance


def _inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]], jumps: dict[tuple[int, int], int]) -> set[tuple[int, int]]:
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "right", "down", "left"):
            nxt, _distance = _transition(current, action, walls, jumps)
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    jumps: dict[tuple[int, int], int],
    exit_cell: tuple[int, int],
    jump_moves: int,
    escaped: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, jumps, exit_cell),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "jump_moves": jump_moves,
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
