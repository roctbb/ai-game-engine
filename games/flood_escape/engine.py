from __future__ import annotations

import json
import os
import random
from collections import deque
from typing import Any, Callable


_WIDTH = 16
_HEIGHT = 16
_MAX_TURNS = 220
_START = (1, 1)
_RANDOM_WALLS = 36
_WATER_SOURCES_TOTAL = 4
_FLOOD_EVERY = 4
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
    water = game_map["water"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(water, set) and isinstance(exit_cell, tuple)

    position = _START
    turns = 0
    invalid_moves = 0
    escaped = False
    alive = True
    frames = [_frame(0, "running", position, walls, water, exit_cell, escaped, alive, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped or not alive:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, water, exit_cell))
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if target in walls or target in water:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        position = target
        turns = turn + 1

        if position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        elif turns % _FLOOD_EVERY == 0:
            water = _spread_water(water, walls, exit_cell)
            events.append({"type": "flood", "tick": turns, "water_cells": len(water)})
            if position in water:
                alive = False
                events.append({"type": "flooded", "tick": turns, "x": position[0], "y": position[1]})

        frames.append(_frame(turns, "running", position, walls, water, exit_cell, escaped, alive, invalid_moves))

    score = max(0, (400 if escaped else 0) + (100 if alive else 0) - turns * 2 - invalid_moves * 15)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "solved": escaped,
        "alive": alive,
        "water_cells": len(water),
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, water, exit_cell, escaped, alive, invalid_moves, score))
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
        seed = "flood_escape_offline"
    rng = random.Random(seed)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) != _START
    ]
    for _attempt in range(600):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        distances = _distances(_START, walls)
        reachable = [cell for cell, dist in distances.items() if cell != _START and dist >= 12]
        if len(reachable) < _WATER_SOURCES_TOTAL + 1:
            continue
        exit_cell = max(reachable, key=lambda cell: distances[cell])
        water_choices = [
            cell
            for cell in distances
            if cell not in {_START, exit_cell} and distances[cell] >= max(8, distances[exit_cell] - 5)
        ]
        if len(water_choices) < _WATER_SOURCES_TOTAL:
            continue
        rng.shuffle(water_choices)
        water = set(water_choices[:_WATER_SOURCES_TOTAL])
        if _can_escape_before_flood(walls, water, exit_cell):
            return {"walls": walls, "water": water, "exit": exit_cell}

    walls = set(_BORDER_WALLS)
    distances = _distances(_START, walls)
    exit_cell = max(distances, key=lambda cell: distances[cell])
    far = sorted((cell for cell in distances if cell not in {_START, exit_cell}), key=lambda cell: distances[cell], reverse=True)
    return {"walls": walls, "water": set(far[:_WATER_SOURCES_TOTAL]), "exit": exit_cell}


def _can_escape_before_flood(walls: set[tuple[int, int]], water: set[tuple[int, int]], exit_cell: tuple[int, int]) -> bool:
    position = _START
    current_water = set(water)
    for step in range(1, _MAX_TURNS + 1):
        path = _first_step_to_exit(position, walls, current_water, exit_cell)
        if path is None:
            return False
        position = _move(position, path)
        if position == exit_cell:
            return True
        if step % _FLOOD_EVERY == 0:
            current_water = _spread_water(current_water, walls, exit_cell)
            if position in current_water:
                return False
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


def _board(walls: set[tuple[int, int]], water: set[tuple[int, int]], exit_cell: tuple[int, int]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in water:
        board[x][y] = -2
    board[exit_cell[0]][exit_cell[1]] = 1
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _spread_water(water: set[tuple[int, int]], walls: set[tuple[int, int]], exit_cell: tuple[int, int]) -> set[tuple[int, int]]:
    result = set(water)
    for cell in list(water):
        for action in ("up", "down", "left", "right"):
            nxt = _move(cell, action)
            if nxt not in walls and nxt != exit_cell:
                result.add(nxt)
    return result


def _distances(start: tuple[int, int], walls: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    queue: deque[tuple[int, int]] = deque([start])
    dist = {start: 0}
    while queue:
        current = queue.popleft()
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls or nxt in dist:
                continue
            dist[nxt] = dist[current] + 1
            queue.append(nxt)
    return dist


def _first_step_to_exit(
    start: tuple[int, int],
    walls: set[tuple[int, int]],
    water: set[tuple[int, int]],
    exit_cell: tuple[int, int],
) -> str | None:
    queue = [start]
    came_from = {start: ("stay", start)}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        if current == exit_cell:
            while came_from[current][1] != start:
                current = came_from[current][1]
            return came_from[current][0]
        for action in ("right", "down", "left", "up"):
            nxt = _move(current, action)
            if nxt in walls or nxt in water or nxt in came_from:
                continue
            came_from[nxt] = (action, current)
            queue.append(nxt)
    return None


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    water: set[tuple[int, int]],
    exit_cell: tuple[int, int],
    escaped: bool,
    alive: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, water, exit_cell),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "water_cells": len(water),
        "escaped": escaped,
        "alive": alive,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
