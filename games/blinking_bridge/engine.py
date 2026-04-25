from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 16
_HEIGHT = 16
_MAX_TURNS = 240
_START = (1, 1)
_RANDOM_WALLS = 18
_BRIDGES_TOTAL = 28
_BARRIER_XS = (3, 5, 7, 9, 11)
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
    bridges = game_map["bridges"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(bridges, dict) and isinstance(exit_cell, tuple)

    position = _START
    invalid_moves = 0
    bridge_steps = 0
    escaped = False
    turns = 0
    frames = [_frame(0, "running", position, walls, bridges, exit_cell, bridge_steps, escaped, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        board = _board(walls, bridges, exit_cell, turn)
        action = _safe_call(move_fn, position[0], position[1], board)
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if not _inside(target) or _blocked(target, walls, bridges, turn):
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})

        position = target
        turns = turn + 1
        if position in bridges:
            bridge_steps += 1
            events.append({"type": "bridge_step", "tick": turns, "x": position[0], "y": position[1]})
        if position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, bridges, exit_cell, bridge_steps, escaped, invalid_moves))

    score = max(0, (450 if escaped else 0) + bridge_steps * 5 - turns * 2 - invalid_moves * 12)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "solved": escaped,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "bridges_total": len(bridges),
        "bridge_steps": bridge_steps,
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, bridges, exit_cell, bridge_steps, escaped, invalid_moves, score))
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
        seed = "blinking_bridge_offline"
    rng = random.Random(seed)
    exit_cell = (_WIDTH - 2, _HEIGHT - 2)
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) not in (_START, exit_cell)]
    for _attempt in range(800):
        route_ys = [rng.randint(2, _HEIGHT - 3) for _ in _BARRIER_XS]
        mandatory_bridges = {(x, y) for x, y in zip(_BARRIER_XS, route_ys, strict=True)}
        protected = _protected_route(route_ys, exit_cell)
        barrier_walls = {
            (x, y)
            for x in _BARRIER_XS
            for y in range(1, _HEIGHT - 1)
            if (x, y) not in mandatory_bridges
        }
        wall_candidates = [cell for cell in candidates if cell not in protected and cell not in mandatory_bridges and cell not in barrier_walls]
        rng.shuffle(wall_candidates)
        walls = set(_BORDER_WALLS) | barrier_walls | set(wall_candidates[:_RANDOM_WALLS])
        bridge_candidates = [cell for cell in candidates if cell not in walls and cell not in protected and cell not in mandatory_bridges]
        rng.shuffle(bridge_candidates)
        bridge_cells = list(mandatory_bridges) + bridge_candidates[: max(0, _BRIDGES_TOTAL - len(mandatory_bridges))]
        bridges = {cell: rng.randrange(2) for cell in bridge_cells}
        if not _requires_many_bridges(walls, bridges, exit_cell, minimum=3):
            continue
        if exit_cell in _reachable_cells(_START, walls, bridges):
            return {"walls": walls, "bridges": bridges, "exit": exit_cell}
    walls = set(_BORDER_WALLS)
    bridges = {(3, 2): 0, (5, 4): 1, (7, 6): 0, (9, 8): 1, (11, 10): 0}
    walls.update({(x, y) for x in _BARRIER_XS for y in range(1, _HEIGHT - 1) if (x, y) not in bridges})
    return {"walls": walls, "bridges": bridges, "exit": (_WIDTH - 2, _HEIGHT - 2)}


def _protected_route(route_ys: list[int], exit_cell: tuple[int, int]) -> set[tuple[int, int]]:
    route = {_START}
    current = _START
    for barrier_x, bridge_y in zip(_BARRIER_XS, route_ys, strict=True):
        step = 1 if bridge_y >= current[1] else -1
        route.update({(current[0], y) for y in range(current[1], bridge_y + step, step)})
        route.update({(x, bridge_y) for x in range(current[0], barrier_x + 2)})
        current = (barrier_x + 1, bridge_y)
    step = 1 if exit_cell[1] >= current[1] else -1
    route.update({(current[0], y) for y in range(current[1], exit_cell[1] + step, step)})
    route.update({(x, exit_cell[1]) for x in range(current[0], exit_cell[0] + 1)})
    return route


def _requires_many_bridges(
    walls: set[tuple[int, int]],
    bridges: dict[tuple[int, int], int],
    exit_cell: tuple[int, int],
    minimum: int,
) -> bool:
    queue = [(_START, 0)]
    seen = {(_START, 0)}
    head = 0
    while head < len(queue):
        current, bridge_steps = queue[head]
        head += 1
        if current == exit_cell:
            return bridge_steps >= minimum
        if bridge_steps >= minimum:
            continue
        for action in ("up", "right", "down", "left"):
            nxt = _move(current, action)
            if not _inside(nxt) or nxt in walls:
                continue
            state = (nxt, bridge_steps + (1 if nxt in bridges else 0))
            if state in seen:
                continue
            seen.add(state)
            queue.append(state)
    return True


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


def _board(walls: set[tuple[int, int]], bridges: dict[tuple[int, int], int], exit_cell: tuple[int, int], tick: int) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for (x, y), phase in bridges.items():
        board[x][y] = 2 if _bridge_open(phase, tick) else -2
    board[exit_cell[0]][exit_cell[1]] = 1
    return board


def _bridge_open(phase: int, tick: int) -> bool:
    return (phase + tick) % 2 == 0


def _blocked(position: tuple[int, int], walls: set[tuple[int, int]], bridges: dict[tuple[int, int], int], tick: int) -> bool:
    if position in walls:
        return True
    phase = bridges.get(position)
    return phase is not None and not _bridge_open(phase, tick)


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]], bridges: dict[tuple[int, int], int]) -> set[tuple[int, int]]:
    queue = [(start, 0)]
    seen = {(start, 0)}
    cells = {start}
    head = 0
    while head < len(queue):
        current, parity = queue[head]
        head += 1
        for action in ("up", "right", "down", "left", "stay"):
            nxt = _move(current, action)
            if not _inside(nxt) or _blocked(nxt, walls, bridges, parity):
                continue
            state = (nxt, 1 - parity)
            if state in seen:
                continue
            seen.add(state)
            cells.add(nxt)
            queue.append(state)
    return cells


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    bridges: dict[tuple[int, int], int],
    exit_cell: tuple[int, int],
    bridge_steps: int,
    escaped: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, bridges, exit_cell, tick),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "bridge_steps": bridge_steps,
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
