from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 180
_DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
_OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    move_fn, compile_error = _build_player_fn(ctx, events, print_context)
    rng = _rng(ctx)

    snake = [(3, 3), (2, 3), (1, 3)]
    food = _next_food(rng, snake)
    turns = 0
    eaten = 0
    invalid_moves = 0
    alive = True
    direction = "right"
    frames = [_frame(0, "running", snake, food, alive, eaten, invalid_moves, direction)]

    for turn in range(_MAX_TURNS):
        if not alive or food is None:
            break
        print_context["tick"] = turn
        head_x, head_y = snake[0]
        board = _board(snake, food)
        action = _safe_call(move_fn, head_x, head_y, board)
        if action not in _DELTAS:
            invalid_moves += 1
            action = direction
            events.append({"type": "invalid_action", "tick": turn, "action": repr(action)})
        if len(snake) > 1 and action == _OPPOSITE[direction]:
            invalid_moves += 1
            action = direction
            events.append({"type": "reverse_blocked", "tick": turn})
        dx, dy = _DELTAS[str(action)]
        new_head = (head_x + dx, head_y + dy)
        direction = str(action)
        grows = new_head == food
        occupied = set(snake if grows else snake[:-1])
        if not _inside(new_head) or new_head in occupied:
            alive = False
            events.append({"type": "crash", "tick": turn + 1, "x": new_head[0], "y": new_head[1]})
        else:
            snake.insert(0, new_head)
            if grows:
                eaten += 1
                food = _next_food(rng, snake)
                events.append({"type": "food", "tick": turn + 1, "x": new_head[0], "y": new_head[1]})
            else:
                snake.pop()
        turns = turn + 1
        frames.append(_frame(turns, "running", snake, food, alive, eaten, invalid_moves, direction))

    won = alive and food is None
    score = max(0, eaten * 100 + len(snake) * 5 + (200 if won else 0) - invalid_moves * 10 - (50 if not alive else 0))
    metrics: dict[str, object] = {
        "turns": turns,
        "food_eaten": eaten,
        "food_total": None,
        "length": len(snake),
        "alive": alive,
        "won": won,
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})
    frames.append(_frame(len(frames), "finished", snake, food, alive, eaten, invalid_moves, direction, score))
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


def _rng(context: dict[str, Any]) -> random.Random:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "snake_offline"
    return random.Random(seed)


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


def _fallback_move(x: int, y: int, board: list[list[int]]) -> str:
    food = _find_food(board)
    if food and food[0] > x:
        return "right"
    if food and food[0] < x:
        return "left"
    if food and food[1] > y:
        return "down"
    return "up"


def _board(snake: list[tuple[int, int]], food: tuple[int, int] | None) -> list[list[int]]:
    board = [[0 for _ in range(_WIDTH)] for _ in range(_HEIGHT)]
    for x in range(_WIDTH):
        board[0][x] = -1
        board[_HEIGHT - 1][x] = -1
    for y in range(_HEIGHT):
        board[y][0] = -1
        board[y][_WIDTH - 1] = -1
    for x, y in snake:
        board[y][x] = -1
    if food is not None:
        board[food[1]][food[0]] = 1
    return board


def _find_food(board: list[list[int]]) -> tuple[int, int] | None:
    for y, row in enumerate(board):
        for x, value in enumerate(row):
            if value == 1:
                return x, y
    return None


def _next_food(rng: random.Random, snake: list[tuple[int, int]]) -> tuple[int, int] | None:
    occupied = set(snake)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in occupied
    ]
    return rng.choice(candidates) if candidates else None


def _inside(cell: tuple[int, int]) -> bool:
    x, y = cell
    return 1 <= x < _WIDTH - 1 and 1 <= y < _HEIGHT - 1


def _frame(
    tick: int,
    phase: str,
    snake: list[tuple[int, int]],
    food: tuple[int, int] | None,
    alive: bool,
    eaten: int,
    invalid_moves: int,
    direction: str,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(snake, food),
        "head": {"x": snake[0][0], "y": snake[0][1]},
        "snake": [{"x": x, "y": y} for x, y in snake],
        "food": {"x": food[0], "y": food[1]} if food else None,
        "width": _WIDTH,
        "height": _HEIGHT,
        "alive": alive,
        "food_eaten": eaten,
        "invalid_moves": invalid_moves,
        "direction": direction,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
