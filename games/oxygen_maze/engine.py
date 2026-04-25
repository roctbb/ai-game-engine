from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 24
_HEIGHT = 20
_MAX_TURNS = 420
_START = (1, 1)
_OXYGEN_MAX = 28
_STATIONS_TOTAL = 5
_RANDOM_WALLS = 58
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
    stations = game_map["stations"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(stations, set) and isinstance(exit_cell, tuple)

    position = _START
    oxygen = _OXYGEN_MAX
    refills = 0
    invalid_moves = 0
    turns = 0
    escaped = False
    alive = True
    frames = [_frame(0, "running", position, walls, stations, exit_cell, oxygen, refills, escaped, alive, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped or not alive:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, stations, exit_cell), oxygen)
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
        if action != "stay" or position != _START:
            oxygen -= 1
        turns = turn + 1

        if position in stations:
            oxygen = _OXYGEN_MAX
            refills += 1
            events.append({"type": "refill", "tick": turns, "x": position[0], "y": position[1]})
        if position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        if oxygen <= 0 and not escaped:
            alive = False
            events.append({"type": "out_of_oxygen", "message": "Кислород закончился до выхода.", "tick": turns})

        frames.append(_frame(turns, "running", position, walls, stations, exit_cell, oxygen, refills, escaped, alive, invalid_moves))

    score = max(0, (450 if escaped else 0) + (100 if alive else 0) - turns * 2 - invalid_moves * 12 + refills * 10)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "solved": escaped,
        "alive": alive,
        "oxygen": oxygen,
        "refills": refills,
        "stations_total": _STATIONS_TOTAL,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, stations, exit_cell, oxygen, refills, escaped, alive, invalid_moves, score))
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
        seed = "oxygen_maze_offline"
    rng = random.Random(seed)
    exit_cell = (_WIDTH - 2, _HEIGHT - 2)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in (_START, exit_cell)
    ]
    for _attempt in range(500):
        route = _random_route(rng, exit_cell)
        wall_candidates = [cell for cell in candidates if cell not in route]
        rng.shuffle(wall_candidates)
        walls = set(_BORDER_WALLS) | set(wall_candidates[:_RANDOM_WALLS])
        distances = _distances(_START, walls)
        exit_distance = distances.get(exit_cell)
        if exit_distance is None or exit_distance <= _OXYGEN_MAX + 5:
            continue
        path = _shortest_path(_START, exit_cell, walls)
        if not path:
            continue
        required_stations = _route_station_cells(path)
        station_candidates = [cell for cell in distances if cell not in {_START, exit_cell} and cell not in required_stations]
        if len(station_candidates) < _STATIONS_TOTAL - len(required_stations):
            continue
        rng.shuffle(station_candidates)
        stations = set(required_stations)
        stations.update(station_candidates[: _STATIONS_TOTAL - len(stations)])
        if _can_escape_with_oxygen(walls, stations, exit_cell) and not _can_reach_without_refill(walls, exit_cell):
            return {"walls": walls, "stations": stations, "exit": exit_cell}
    walls = set(_BORDER_WALLS)
    return {"walls": walls, "stations": {(6, 3), (10, 6), (14, 9), (18, 12), (20, 16)}, "exit": exit_cell}


def _random_route(rng: random.Random, exit_cell: tuple[int, int]) -> set[tuple[int, int]]:
    route = {_START}
    current = _START
    waypoints = [
        (rng.randint(4, 7), rng.randint(2, 5)),
        (rng.randint(8, 12), rng.randint(6, 9)),
        (rng.randint(13, 17), rng.randint(9, 13)),
        (rng.randint(17, 21), rng.randint(13, 17)),
        exit_cell,
    ]
    for waypoint in waypoints:
        x, y = current
        tx, ty = waypoint
        if rng.randrange(2) == 0:
            route.update({(nx, y) for nx in range(min(x, tx), max(x, tx) + 1)})
            route.update({(tx, ny) for ny in range(min(y, ty), max(y, ty) + 1)})
        else:
            route.update({(x, ny) for ny in range(min(y, ty), max(y, ty) + 1)})
            route.update({(nx, ty) for nx in range(min(x, tx), max(x, tx) + 1)})
        current = waypoint
    return route


def _route_station_cells(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    indexes = [max(1, min(len(path) - 2, _OXYGEN_MAX - 6))]
    if len(path) > _OXYGEN_MAX * 2:
        indexes.append(max(1, min(len(path) - 2, _OXYGEN_MAX * 2 - 10)))
    result: list[tuple[int, int]] = []
    for index in indexes:
        cell = path[index]
        if cell not in result:
            result.append(cell)
    return result


def _shortest_path(start: tuple[int, int], goal: tuple[int, int], walls: set[tuple[int, int]]) -> list[tuple[int, int]]:
    queue = [start]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        if current == goal:
            path = [current]
            while came_from[current] is not None:
                current = came_from[current]  # type: ignore[assignment]
                path.append(current)
            path.reverse()
            return path
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls or nxt in came_from:
                continue
            came_from[nxt] = current
            queue.append(nxt)
    return []


def _can_escape_with_oxygen(walls: set[tuple[int, int]], stations: set[tuple[int, int]], exit_cell: tuple[int, int]) -> bool:
    queue = [(_START, _OXYGEN_MAX, 0)]
    seen = {(_START, _OXYGEN_MAX)}
    head = 0
    while head < len(queue):
        current, oxygen, refills = queue[head]
        head += 1
        if current == exit_cell:
            return refills > 0
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls:
                continue
            next_oxygen = oxygen - 1
            next_refills = refills
            if next_oxygen <= 0 and nxt != exit_cell:
                continue
            if nxt in stations:
                next_oxygen = _OXYGEN_MAX
                next_refills += 1
            state = (nxt, next_oxygen)
            if state in seen:
                continue
            seen.add(state)
            queue.append((nxt, next_oxygen, next_refills))
    return False


def _can_reach_without_refill(walls: set[tuple[int, int]], exit_cell: tuple[int, int]) -> bool:
    distances = _distances(_START, walls)
    distance = distances.get(exit_cell)
    return distance is not None and distance < _OXYGEN_MAX


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], oxygen: int) -> object:
    try:
        return fn(x, y, board, oxygen)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _oxygen: int = 0) -> str:
    return "right"


def _board(walls: set[tuple[int, int]], stations: set[tuple[int, int]], exit_cell: tuple[int, int]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in stations:
        board[x][y] = 1
    board[exit_cell[0]][exit_cell[1]] = 2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _distances(start: tuple[int, int], walls: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    queue = [start]
    dist = {start: 0}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls or nxt in dist:
                continue
            dist[nxt] = dist[current] + 1
            queue.append(nxt)
    return dist


def _frame(tick: int, phase: str, position: tuple[int, int], walls: set[tuple[int, int]], stations: set[tuple[int, int]], exit_cell: tuple[int, int], oxygen: int, refills: int, escaped: bool, alive: bool, invalid_moves: int, score: int | None = None) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, stations, exit_cell),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "oxygen": oxygen,
        "oxygen_max": _OXYGEN_MAX,
        "refills": refills,
        "escaped": escaped,
        "alive": alive,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
