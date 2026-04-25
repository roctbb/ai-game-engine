from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 22
_HEIGHT = 18
_MAX_TURNS = 360
_START = (1, 1)
_RANDOM_WALLS = 58
_DOOR_XS = (5, 10, 15)
_DOORS_TOTAL = len(_DOOR_XS) * (_HEIGHT - 2)
_SWITCHES_TOTAL = 6
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
    doors = game_map["doors"]
    switches = game_map["switches"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(doors, set) and isinstance(switches, set) and isinstance(exit_cell, tuple)

    position = _START
    switched = False
    escaped = False
    switch_flips = 0
    last_switch: tuple[int, int] | None = None
    turns = 0
    invalid_moves = 0
    frames = [_frame(0, "running", position, walls, doors, switches, exit_cell, switched, escaped, invalid_moves, switch_flips)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, doors, switches, exit_cell, switched), switched)
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if target in walls or (target in doors and not switched):
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        position = target
        turns = turn + 1

        if position in switches and position != last_switch:
            switched = not switched
            switch_flips += 1
            last_switch = position
            events.append({"type": "switch_toggle", "tick": turns, "open": switched, "x": position[0], "y": position[1]})
        elif position not in switches:
            last_switch = None
        if position == exit_cell and switched:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, doors, switches, exit_cell, switched, escaped, invalid_moves, switch_flips))

    score = max(0, (450 if escaped else 0) + (100 if switched else 0) - turns * 2 - invalid_moves * 10)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "switched": switched,
        "switch_flips": switch_flips,
        "switches_total": _SWITCHES_TOTAL,
        "doors_total": len(doors),
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, doors, switches, exit_cell, switched, escaped, invalid_moves, switch_flips, score))
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
        seed = "switch_maze_offline"
    rng = random.Random(seed)
    exit_cell = (_WIDTH - 2, _HEIGHT - 2)
    doors = _door_cells()
    land_cells = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in {_START, exit_cell} and (x, y) not in doors
    ]
    for _attempt in range(600):
        switch_y = rng.randint(3, _HEIGHT - 4)
        main_switch = (3, switch_y)
        protected = _protected_route(main_switch, exit_cell)
        wall_candidates = [cell for cell in land_cells if cell not in protected and cell != main_switch]
        rng.shuffle(wall_candidates)
        walls = set(_BORDER_WALLS) | set(wall_candidates[:_RANDOM_WALLS])
        reachable_before = sorted(_reachable_cells(_START, walls | doors) - {_START})
        switch_candidates = [cell for cell in reachable_before if cell[0] < _DOOR_XS[0] and cell not in protected and cell != main_switch]
        if main_switch not in reachable_before or len(switch_candidates) < _SWITCHES_TOTAL - 1:
            continue
        rng.shuffle(switch_candidates)
        switches = {main_switch, *switch_candidates[: _SWITCHES_TOTAL - 1]}
        before_open = _reachable_cells(_START, walls | doors)
        if (
            exit_cell not in before_open
            and exit_cell in _reachable_cells(main_switch, walls)
            and all(exit_cell in _reachable_cells(switch_cell, walls | (switches - {switch_cell})) for switch_cell in switches)
        ):
            return {"walls": walls, "doors": doors, "switches": switches, "exit": exit_cell}
    walls = set(_BORDER_WALLS)
    return {
        "walls": walls,
        "doors": doors,
        "switches": {(3, 6), (2, 3), (2, 10), (4, 12), (3, 14), (1, 8)},
        "exit": exit_cell,
    }


def _door_cells() -> set[tuple[int, int]]:
    return {(x, y) for x in _DOOR_XS for y in range(1, _HEIGHT - 1)}


def _protected_route(main_switch: tuple[int, int], exit_cell: tuple[int, int]) -> set[tuple[int, int]]:
    sx, sy = main_switch
    route = {(1, y) for y in range(1, sy + 1)}
    route.update({(x, sy) for x in range(1, exit_cell[0] + 1)})
    route.update({(exit_cell[0], y) for y in range(sy, exit_cell[1] + 1)})
    return route - _door_cells()


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], switched: bool) -> object:
    try:
        return fn(x, y, board, switched)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _switched: bool = False) -> str:
    return "right"


def _board(
    walls: set[tuple[int, int]],
    doors: set[tuple[int, int]],
    switches: set[tuple[int, int]],
    exit_cell: tuple[int, int],
    switched: bool,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    if not switched:
        for x, y in doors:
            board[x][y] = -2
    for x, y in switches:
        board[x][y] = 1
    board[exit_cell[0]][exit_cell[1]] = 2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _reachable_cells(start: tuple[int, int], blocked: set[tuple[int, int]]) -> set[tuple[int, int]]:
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


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    doors: set[tuple[int, int]],
    switches: set[tuple[int, int]],
    exit_cell: tuple[int, int],
    switched: bool,
    escaped: bool,
    invalid_moves: int,
    switch_flips: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, doors, switches, exit_cell, switched),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "switched": switched,
        "switches": [{"x": x, "y": y} for x, y in sorted(switches)],
        "switch_flips": switch_flips,
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
