from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 16
_HEIGHT = 16
_MAX_TURNS = 420
_START = (1, 1)
_LAMPS_TOTAL = 6
_RANDOM_WALLS = 36
_VISION_RADIUS = 2
_LAMP_LIGHT_RADIUS = 4
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
    lamps = game_map["lamps"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(lamps, set) and isinstance(exit_cell, tuple)

    position = _START
    lit = 0
    lit_lamps: set[tuple[int, int]] = set()
    escaped = False
    invalid_moves = 0
    turns = 0
    frames = [_frame(0, "running", position, walls, lamps, lit_lamps, exit_cell, lit, escaped, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _visible_board(walls, lamps, lit_lamps, exit_cell, position), lit)
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
        turns = turn + 1

        if position in lamps and position not in lit_lamps:
            lit_lamps.add(position)
            lit += 1
            events.append({"type": "lamp_lit", "tick": turns, "x": position[0], "y": position[1]})
        if position == exit_cell and lit == _LAMPS_TOTAL:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, lamps, lit_lamps, exit_cell, lit, escaped, invalid_moves))

    score = max(0, lit * 90 + (300 if escaped else 0) - turns * 2 - invalid_moves * 10)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "solved": escaped,
        "lamps_lit": lit,
        "lamps_total": _LAMPS_TOTAL,
        "lamps_left": _LAMPS_TOTAL - lit,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, lamps, lit_lamps, exit_cell, lit, escaped, invalid_moves, score))
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
        seed = "crystal_lamps_offline"
    rng = random.Random(seed)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) != _START
    ]
    for _attempt in range(500):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        reachable = sorted(_reachable_cells(_START, walls) - {_START})
        if len(reachable) < _LAMPS_TOTAL + 8:
            continue
        rng.shuffle(reachable)
        lamps = set(reachable[:_LAMPS_TOTAL])
        exit_cell = max(reachable[_LAMPS_TOTAL:], key=lambda cell: abs(cell[0] - _START[0]) + abs(cell[1] - _START[1]))
        return {"walls": walls, "lamps": lamps, "exit": exit_cell}
    walls = set(_BORDER_WALLS)
    reachable = sorted(_reachable_cells(_START, walls) - {_START})
    rng.shuffle(reachable)
    return {"walls": walls, "lamps": set(reachable[:_LAMPS_TOTAL]), "exit": reachable[-1]}


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], lamps_lit: int) -> object:
    try:
        return fn(x, y, board, lamps_lit)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _lamps_lit: int = 0) -> str:
    return "right"


def _board(
    walls: set[tuple[int, int]],
    lamps: set[tuple[int, int]],
    lit_lamps: set[tuple[int, int]],
    exit_cell: tuple[int, int],
    reveal_exit: bool,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in lamps:
        board[x][y] = 3 if (x, y) in lit_lamps else 1
    if reveal_exit:
        board[exit_cell[0]][exit_cell[1]] = 2
    return board


def _visible_board(
    walls: set[tuple[int, int]],
    lamps: set[tuple[int, int]],
    lit_lamps: set[tuple[int, int]],
    exit_cell: tuple[int, int],
    position: tuple[int, int],
) -> list[list[int]]:
    visible = _visible_cells(position, lit_lamps)
    if len(lit_lamps) == _LAMPS_TOTAL:
        visible.add(exit_cell)
    full = _board(walls, lamps, lit_lamps, exit_cell, reveal_exit=len(lit_lamps) == _LAMPS_TOTAL)
    board = [[-9 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in visible:
        board[x][y] = full[x][y]
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue = [start]
    seen = {start}
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
    lamps: set[tuple[int, int]],
    lit_lamps: set[tuple[int, int]],
    exit_cell: tuple[int, int],
    lit: int,
    escaped: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    visible = _visible_cells(position, lit_lamps)
    frame: dict[str, object] = {
        "board": _board(walls, lamps, lit_lamps, exit_cell, reveal_exit=lit == _LAMPS_TOTAL),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "lamps_lit": lit,
        "lamps_left": _LAMPS_TOTAL - lit,
        "lamps_total": _LAMPS_TOTAL,
        "lit_lamps": [{"x": x, "y": y} for x, y in sorted(lit_lamps)],
        "visible_cells": [{"x": x, "y": y} for x, y in sorted(visible)],
        "lit_cells": [{"x": x, "y": y} for x, y in sorted(_lit_cells(lit_lamps))],
        "vision_radius": _VISION_RADIUS,
        "lamp_light_radius": _LAMP_LIGHT_RADIUS,
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


def _visible_cells(position: tuple[int, int], lit_lamps: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return _cells_in_radius(position, _VISION_RADIUS) | _lit_cells(lit_lamps)


def _lit_cells(lit_lamps: set[tuple[int, int]]) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for lamp in lit_lamps:
        result |= _cells_in_radius(lamp, _LAMP_LIGHT_RADIUS)
    return result


def _cells_in_radius(center: tuple[int, int], radius: int) -> set[tuple[int, int]]:
    cx, cy = center
    cells = set()
    for y in range(max(0, cy - radius), min(_HEIGHT, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(_WIDTH, cx + radius + 1)):
            if abs(x - cx) + abs(y - cy) <= radius:
                cells.add((x, y))
    return cells


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
