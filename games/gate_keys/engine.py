from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 22
_HEIGHT = 18
_MAX_TURNS = 420
_START = (1, 1)
_KEYS_TOTAL = 7
_GATE_XS = (5, 10, 15)
_GATES_PER_BARRIER = 3
_GATES_TOTAL = len(_GATE_XS) * _GATES_PER_BARRIER
_RANDOM_WALLS = 54
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
    keys_on_map = game_map["keys"]
    gates = game_map["gates"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(keys_on_map, set) and isinstance(gates, set) and isinstance(exit_cell, tuple)

    position = _START
    keys = 0
    collected = 0
    gates_opened = 0
    invalid_moves = 0
    escaped = False
    turns = 0
    frames = [_frame(0, "running", position, walls, keys_on_map, gates, exit_cell, keys, collected, escaped, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        board = _board(walls, keys_on_map, gates, exit_cell)
        action = _safe_call(move_fn, position[0], position[1], board, keys)
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if target in walls:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        elif target in gates and keys <= 0:
            invalid_moves += 1
            target = position
            events.append({"type": "locked_gate", "message": "Ворота закрыты: нужен ключ.", "tick": turn, "x": target[0], "y": target[1]})

        position = target
        turns = turn + 1
        if position in keys_on_map:
            keys_on_map.remove(position)
            keys += 1
            collected += 1
            events.append({"type": "key", "tick": turns, "x": position[0], "y": position[1]})
        if position in gates:
            gates.remove(position)
            keys -= 1
            gates_opened += 1
            events.append({"type": "gate_opened", "tick": turns, "x": position[0], "y": position[1]})
        if position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, keys_on_map, gates, exit_cell, keys, collected, escaped, invalid_moves))

    score = max(0, collected * 60 + gates_opened * 50 + (350 if escaped else 0) - turns * 2 - invalid_moves * 12)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "solved": escaped,
        "keys": keys,
        "keys_collected": collected,
        "keys_total": _KEYS_TOTAL,
        "gates_opened": gates_opened,
        "gates_total": _GATES_TOTAL,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, keys_on_map, gates, exit_cell, keys, collected, escaped, invalid_moves, score))
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
        seed = "gate_keys_offline"
    rng = random.Random(seed)
    exit_cell = (_WIDTH - 2, _HEIGHT - 2)
    left_cells = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _GATE_XS[0]) if (x, y) != _START]
    land_cells = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in (_START, exit_cell) and x not in _GATE_XS
    ]
    for _attempt in range(700):
        gate_rows_by_x = {x: sorted(rng.sample(range(2, _HEIGHT - 2), _GATES_PER_BARRIER)) for x in _GATE_XS}
        gates = {(x, y) for x, rows in gate_rows_by_x.items() for y in rows}
        route_rows = [rng.choice(gate_rows_by_x[x]) for x in _GATE_XS]
        protected = _protected_route(route_rows, exit_cell)
        barrier_walls = {
            (x, y)
            for x in _GATE_XS
            for y in range(1, _HEIGHT - 1)
            if (x, y) not in gates
        }
        wall_candidates = [cell for cell in land_cells if cell not in protected]
        rng.shuffle(wall_candidates)
        random_walls = set(wall_candidates[:_RANDOM_WALLS])
        walls = set(_BORDER_WALLS) | barrier_walls | random_walls
        reachable_left = sorted(_reachable_cells(_START, walls | gates) & set(left_cells))
        if len(reachable_left) < _KEYS_TOTAL:
            continue
        rng.shuffle(reachable_left)
        keys = set(reachable_left[:_KEYS_TOTAL])
        blocked_exit = exit_cell not in _reachable_cells(_START, walls | gates)
        if blocked_exit and _can_escape(walls, keys, gates, exit_cell) and _min_gates_to_exit(walls, gates, exit_cell) >= len(_GATE_XS):
            return {"walls": walls, "keys": keys, "gates": gates, "exit": exit_cell}
    walls = set(_BORDER_WALLS)
    gates = {(5, 4), (5, 8), (5, 12), (10, 5), (10, 9), (10, 13), (15, 4), (15, 10), (15, 14)}
    walls.update({(x, y) for x in _GATE_XS for y in range(1, _HEIGHT - 1) if (x, y) not in gates})
    return {
        "walls": walls,
        "keys": {(2, 2), (2, 4), (2, 6), (2, 8), (3, 3), (3, 10), (4, 14)},
        "gates": gates,
        "exit": exit_cell,
    }


def _protected_route(route_rows: list[int], exit_cell: tuple[int, int]) -> set[tuple[int, int]]:
    route = {_START}
    current = _START
    for barrier_x, gate_y in zip(_GATE_XS, route_rows, strict=True):
        step = 1 if gate_y >= current[1] else -1
        route.update({(current[0], y) for y in range(current[1], gate_y + step, step)})
        route.update({(x, gate_y) for x in range(current[0], barrier_x + 2)})
        current = (barrier_x + 1, gate_y)
    step = 1 if exit_cell[1] >= current[1] else -1
    route.update({(current[0], y) for y in range(current[1], exit_cell[1] + step, step)})
    route.update({(x, exit_cell[1]) for x in range(current[0], exit_cell[0] + 1)})
    return route


def _can_escape(walls: set[tuple[int, int]], keys: set[tuple[int, int]], gates: set[tuple[int, int]], exit_cell: tuple[int, int]) -> bool:
    start_state = (_START[0], _START[1], 0, frozenset(keys))
    queue = [start_state]
    seen = {start_state}
    head = 0
    while head < len(queue):
        x, y, count, left_keys = queue[head]
        head += 1
        if (x, y) == exit_cell:
            return True
        for action in ("up", "down", "left", "right"):
            nx, ny = _move((x, y), action)
            if (nx, ny) in walls:
                continue
            new_count = count
            new_keys = set(left_keys)
            if (nx, ny) in gates:
                if new_count <= 0:
                    continue
                new_count -= 1
            if (nx, ny) in new_keys:
                new_count += 1
                new_keys.remove((nx, ny))
            state = (nx, ny, new_count, frozenset(new_keys))
            if state in seen:
                continue
            seen.add(state)
            queue.append(state)
    return False


def _min_gates_to_exit(walls: set[tuple[int, int]], gates: set[tuple[int, int]], exit_cell: tuple[int, int]) -> int:
    queue = [(_START, 0)]
    seen = {_START: 0}
    head = 0
    while head < len(queue):
        current, opened = queue[head]
        head += 1
        if current == exit_cell:
            return opened
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls:
                continue
            next_opened = opened + (1 if nxt in gates else 0)
            if seen.get(nxt, _GATES_TOTAL + 1) <= next_opened:
                continue
            seen[nxt] = next_opened
            queue.append((nxt, next_opened))
    return _GATES_TOTAL + 1


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
    return {"abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate, "float": float, "int": int, "len": len, "list": list, "max": max, "min": min, "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip}


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], keys: int) -> object:
    try:
        return fn(x, y, board, keys)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _keys: int = 0) -> str:
    return "right"


def _board(walls: set[tuple[int, int]], keys: set[tuple[int, int]], gates: set[tuple[int, int]], exit_cell: tuple[int, int]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in gates:
        board[x][y] = -2
    for x, y in keys:
        board[x][y] = 1
    board[exit_cell[0]][exit_cell[1]] = 2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _frame(tick: int, phase: str, position: tuple[int, int], walls: set[tuple[int, int]], keys_on_map: set[tuple[int, int]], gates: set[tuple[int, int]], exit_cell: tuple[int, int], keys: int, collected: int, escaped: bool, invalid_moves: int, score: int | None = None) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, keys_on_map, gates, exit_cell),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "keys": keys,
        "keys_collected": collected,
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
