from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 22
_HEIGHT = 18
_MAX_TURNS = 360
_START = (1, 1)
_PLANKS_TOTAL = 7
_RIVER_XS = (5, 10, 15)
_WATER_TOTAL = len(_RIVER_XS) * (_HEIGHT - 2)
_RANDOM_WALLS = 46
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
    planks_on_map = game_map["planks"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(water, set) and isinstance(planks_on_map, set) and isinstance(exit_cell, tuple)

    position = _START
    planks = 0
    collected = 0
    crossed_water = 0
    invalid_moves = 0
    escaped = False
    turns = 0
    frames = [_frame(0, "running", position, walls, water, planks_on_map, exit_cell, planks, collected, escaped, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        board = _board(walls, water, planks_on_map, exit_cell)
        action = _safe_call(move_fn, position[0], position[1], board, planks)
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if target in walls:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        elif target in water and planks <= 0:
            invalid_moves += 1
            target = position
            events.append({"type": "no_planks", "message": "Нельзя перейти воду: нет доски.", "tick": turn, "x": target[0], "y": target[1]})

        position = target
        turns = turn + 1
        if position in water:
            planks -= 1
            crossed_water += 1
            water.remove(position)
            events.append({"type": "water_crossed", "tick": turns, "x": position[0], "y": position[1]})
        if position in planks_on_map:
            planks_on_map.remove(position)
            planks += 1
            collected += 1
            events.append({"type": "plank", "tick": turns, "x": position[0], "y": position[1]})
        if position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, water, planks_on_map, exit_cell, planks, collected, escaped, invalid_moves))

    score = max(0, collected * 60 + crossed_water * 25 + (350 if escaped else 0) - turns * 2 - invalid_moves * 12)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "planks_collected": collected,
        "planks_total": _PLANKS_TOTAL,
        "planks": planks,
        "water_crossed": crossed_water,
        "water_total": _WATER_TOTAL,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, water, planks_on_map, exit_cell, planks, collected, escaped, invalid_moves, score))
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
        seed = "river_planks_offline"
    rng = random.Random(seed)
    water = _river_cells()
    land_cells = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in water and (x, y) != _START
    ]
    for _attempt in range(800):
        route_y = rng.randint(3, _HEIGHT - 4)
        exit_cell = (_WIDTH - 2, _HEIGHT - 2)
        protected = _protected_route(route_y, exit_cell)
        mandatory_planks = {(river_x - 1, route_y) for river_x in _RIVER_XS}
        candidates = [cell for cell in land_cells if cell not in protected and cell not in mandatory_planks and cell != exit_cell]
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        open_land = [cell for cell in land_cells if cell not in walls and cell != exit_cell and cell not in mandatory_planks]
        if len(open_land) < _PLANKS_TOTAL:
            continue
        rng.shuffle(open_land)
        planks = set(mandatory_planks)
        planks.update(open_land[: _PLANKS_TOTAL - len(planks)])
        if _can_escape(walls, water, planks, exit_cell):
            return {"walls": walls, "water": water, "planks": planks, "exit": exit_cell}
    walls = set(_BORDER_WALLS)
    return {
        "walls": walls,
        "water": water,
        "planks": {(4, 6), (9, 6), (14, 6), (2, 2), (7, 4), (12, 8), (18, 10)},
        "exit": (_WIDTH - 2, _HEIGHT - 2),
    }


def _river_cells() -> set[tuple[int, int]]:
    return {(x, y) for x in _RIVER_XS for y in range(1, _HEIGHT - 1)}


def _protected_route(route_y: int, exit_cell: tuple[int, int]) -> set[tuple[int, int]]:
    route = {(1, y) for y in range(1, route_y + 1)}
    route.update({(x, route_y) for x in range(1, _WIDTH - 1)})
    route.update({(exit_cell[0], y) for y in range(route_y, exit_cell[1] + 1)})
    return route - _river_cells()


def _can_escape(walls: set[tuple[int, int]], water: set[tuple[int, int]], planks: set[tuple[int, int]], exit_cell: tuple[int, int]) -> bool:
    queue = [(_START[0], _START[1], 0, frozenset(planks))]
    seen = {(_START[0], _START[1], 0, frozenset(planks))}
    head = 0
    while head < len(queue):
        x, y, count, left_planks = queue[head]
        head += 1
        if (x, y) == exit_cell:
            return True
        for action in ("up", "down", "left", "right"):
            nx, ny = _move((x, y), action)
            if (nx, ny) in walls:
                continue
            new_count = count
            new_planks = set(left_planks)
            if (nx, ny) in water:
                if new_count <= 0:
                    continue
                new_count -= 1
            if (nx, ny) in new_planks:
                new_count += 1
                new_planks.remove((nx, ny))
            state = (nx, ny, new_count, frozenset(new_planks))
            if state in seen:
                continue
            seen.add(state)
            queue.append(state)
    return False


def _reachable_plain(start: tuple[int, int], blocked: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in blocked or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], planks: int) -> object:
    try:
        return fn(x, y, board, planks)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _planks: int = 0) -> str:
    return "right"


def _board(walls: set[tuple[int, int]], water: set[tuple[int, int]], planks: set[tuple[int, int]], exit_cell: tuple[int, int]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in water:
        board[x][y] = -2
    for x, y in planks:
        board[x][y] = 1
    board[exit_cell[0]][exit_cell[1]] = 2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    water: set[tuple[int, int]],
    planks_on_map: set[tuple[int, int]],
    exit_cell: tuple[int, int],
    planks: int,
    collected: int,
    escaped: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, water, planks_on_map, exit_cell),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "planks": planks,
        "planks_collected": collected,
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
