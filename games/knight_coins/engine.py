from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 10
_HEIGHT = 10
_MAX_TURNS = 130
_START = (1, 1)
_COINS_TOTAL = 8
_RANDOM_HOLES = 12
_MOVES = {
    "up_left": (-1, -2),
    "up_right": (1, -2),
    "right_up": (2, -1),
    "right_down": (2, 1),
    "down_right": (1, 2),
    "down_left": (-1, 2),
    "left_down": (-2, 1),
    "left_up": (-2, -1),
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
    holes = game_map["holes"]
    coins = game_map["coins"]
    exit_cell = game_map["exit"]
    assert isinstance(holes, set) and isinstance(coins, set) and isinstance(exit_cell, tuple)

    walls = set(_BORDER_WALLS) | holes
    position = _START
    collected = 0
    invalid_moves = 0
    escaped = False
    turns = 0
    frames = [_frame(0, "running", position, walls, coins, exit_cell, collected, escaped, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, coins, exit_cell))
        if action not in _MOVES:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if not _inside(target) or target in walls:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_jump", "tick": turn, "action": action})

        position = target
        turns = turn + 1
        if position in coins:
            coins.remove(position)
            collected += 1
            events.append({"type": "coin", "tick": turns, "x": position[0], "y": position[1]})
        if not coins and position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, coins, exit_cell, collected, escaped, invalid_moves))

    score = max(0, collected * 70 + (350 if escaped else 0) - turns * 2 - invalid_moves * 12)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "coins_collected": collected,
        "coins_total": _COINS_TOTAL,
        "coins_left": len(coins),
        "holes_total": len(holes),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, coins, exit_cell, collected, escaped, invalid_moves, score))
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
        seed = "knight_coins_offline"
    rng = random.Random(seed)
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) != _START]
    for _attempt in range(800):
        rng.shuffle(candidates)
        holes = set(candidates[:_RANDOM_HOLES])
        walls = set(_BORDER_WALLS) | holes
        reachable = sorted(_reachable_cells(_START, walls) - {_START})
        if len(reachable) < _COINS_TOTAL + 4:
            continue
        rng.shuffle(reachable)
        coins = set(reachable[:_COINS_TOTAL])
        exit_cell = max(reachable[_COINS_TOTAL:], key=lambda cell: abs(cell[0] - _START[0]) + abs(cell[1] - _START[1]))
        return {"holes": holes, "coins": coins, "exit": exit_cell}
    holes: set[tuple[int, int]] = set()
    reachable = sorted(_reachable_cells(_START, set(_BORDER_WALLS)) - {_START})
    rng.shuffle(reachable)
    return {"holes": holes, "coins": set(reachable[:_COINS_TOTAL]), "exit": reachable[-1]}


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
    return "right_down"


def _board(walls: set[tuple[int, int]], coins: set[tuple[int, int]], exit_cell: tuple[int, int]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in coins:
        board[x][y] = 1
    board[exit_cell[0]][exit_cell[1]] = 2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _MOVES[action]
    return position[0] + dx, position[1] + dy


def _inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in _MOVES:
            if action == "stay":
                continue
            nxt = _move(current, action)
            if not _inside(nxt) or nxt in walls or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    coins: set[tuple[int, int]],
    exit_cell: tuple[int, int],
    collected: int,
    escaped: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, coins, exit_cell),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "coins_collected": collected,
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
