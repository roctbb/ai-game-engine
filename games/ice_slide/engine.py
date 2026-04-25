from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 110
_START = (1, 1)
_EXIT = (10, 10)
_RANDOM_WALLS = 24
_DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
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
    walls = _build_walls(ctx)

    position = _START
    turns = 0
    invalid_moves = 0
    reached_exit = False
    frames = [_frame(0, "running", position, turns, invalid_moves, reached_exit, walls)]

    for turn in range(_MAX_TURNS):
        if position == _EXIT:
            reached_exit = True
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls))
        if action not in _DELTAS:
            invalid_moves += 1
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})
            frames.append(_frame(turn + 1, "running", position, turns, invalid_moves, reached_exit, walls))
            continue
        target = _slide(position, str(action), walls)
        if target == position:
            invalid_moves += 1
            events.append({"type": "blocked_slide", "tick": turn, "action": action})
        else:
            position = target
            turns += 1
            events.append({"type": "slide", "tick": turn + 1, "action": action, "x": position[0], "y": position[1]})
        reached_exit = position == _EXIT
        frames.append(_frame(turn + 1, "running", position, turns, invalid_moves, reached_exit, walls))
        if reached_exit:
            events.append({"type": "exit_reached", "tick": turn + 1})
            break

    score = max(0, 500 + (200 if reached_exit else 0) - turns * 8 - invalid_moves * 20)
    metrics: dict[str, object] = {
        "turns": turns,
        "invalid_moves": invalid_moves,
        "reached_exit": reached_exit,
        "solved": reached_exit,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})
    frames.append(_frame(len(frames), "finished", position, turns, invalid_moves, reached_exit, walls, score))
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


def _build_walls(context: dict[str, Any]) -> set[tuple[int, int]]:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "ice_slide_offline"
    rng = random.Random(seed)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in {_START, _EXIT}
    ]
    for _attempt in range(800):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        if _can_reach_exit(walls):
            return walls
    return set(_BORDER_WALLS)


def _can_reach_exit(walls: set[tuple[int, int]]) -> bool:
    queue = [_START]
    seen = {_START}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        if current == _EXIT:
            return True
        for action in _DELTAS:
            nxt = _slide(current, action, walls)
            if nxt != current and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]]) -> object:
    try:
        return fn(x, y, board)
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]]) -> str:
    return "right"


def _board(walls: set[tuple[int, int]]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    board[_EXIT[0]][_EXIT[1]] = 1
    return board


def _slide(position: tuple[int, int], action: str, walls: set[tuple[int, int]]) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    x, y = position
    while True:
        nx, ny = x + dx, y + dy
        if (nx, ny) in walls or not (0 <= nx < _WIDTH and 0 <= ny < _HEIGHT):
            return x, y
        x, y = nx, ny
        if (x, y) == _EXIT:
            return x, y


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    turns: int,
    invalid_moves: int,
    reached_exit: bool,
    walls: set[tuple[int, int]],
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "exit": {"x": _EXIT[0], "y": _EXIT[1]},
        "turns": turns,
        "invalid_moves": invalid_moves,
        "reached_exit": reached_exit,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
