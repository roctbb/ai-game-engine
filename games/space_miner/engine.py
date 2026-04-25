from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 16
_HEIGHT = 16
_MAX_TURNS = 340
_START = (1, 1)
_FUEL_MAX = 38
_ORE_TOTAL = 9
_RANDOM_WALLS = 34
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
    ore = game_map["ore"]
    assert isinstance(walls, set) and isinstance(ore, set)

    position = _START
    fuel = _FUEL_MAX
    mined = 0
    invalid_moves = 0
    turns = 0
    alive = True
    completed = False
    frames = [_frame(0, "running", position, walls, ore, fuel, mined, alive, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if not alive or completed:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, ore), fuel, mined)
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
        if position != _START or action != "stay":
            fuel -= 1
        turns = turn + 1

        if position in ore:
            ore.remove(position)
            mined += 1
            events.append({"type": "ore", "tick": turns, "x": position[0], "y": position[1]})
        if position == _START:
            fuel = _FUEL_MAX
            events.append({"type": "refuel", "tick": turns})
        if fuel <= 0 and position != _START:
            alive = False
            events.append({"type": "out_of_fuel", "message": "Топливо закончилось вне базы.", "tick": turns})
        if not ore and position == _START:
            completed = True
            events.append({"type": "completed", "tick": turns})

        frames.append(_frame(turns, "running", position, walls, ore, fuel, mined, alive, invalid_moves))

    score = max(0, mined * 100 + (250 if completed else 0) + (75 if alive else 0) - turns * 2 - invalid_moves * 15)
    metrics: dict[str, object] = {
        "turns": turns,
        "completed": completed,
        "solved": completed,
        "alive": alive,
        "ore_mined": mined,
        "ore_total": _ORE_TOTAL,
        "ore_left": len(ore),
        "fuel": fuel,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, ore, fuel, mined, alive, invalid_moves, score))
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
        seed = "space_miner_offline"
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
        if len(reachable) < _ORE_TOTAL + 12:
            continue
        rng.shuffle(reachable)
        ore = set(reachable[:_ORE_TOTAL])
        distances = [_distance(_START, cell, walls) for cell in ore]
        if all(distance <= _FUEL_MAX // 2 - 4 for distance in distances) and sum(distances) > _FUEL_MAX:
            return {"walls": walls, "ore": ore}
    walls = set(_BORDER_WALLS)
    reachable = sorted(_reachable_cells(_START, walls) - {_START})
    rng.shuffle(reachable)
    return {"walls": walls, "ore": set(reachable[:_ORE_TOTAL])}


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], fuel: int, mined: int) -> object:
    try:
        return fn(x, y, board, fuel, mined)
    except TypeError:
        try:
            return fn(x, y, board, fuel)
        except TypeError:
            try:
                return fn(x, y, board)
            except Exception:
                return None
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _fuel: int = 0, _mined: int = 0) -> str:
    return "right"


def _board(walls: set[tuple[int, int]], ore: set[tuple[int, int]]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in ore:
        board[x][y] = 1
    board[_START[0]][_START[1]] = 2
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


def _distance(start: tuple[int, int], goal: tuple[int, int], walls: set[tuple[int, int]]) -> int:
    queue = [start]
    dist = {start: 0}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        if current == goal:
            return dist[current]
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls or nxt in dist:
                continue
            dist[nxt] = dist[current] + 1
            queue.append(nxt)
    return 999


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    ore: set[tuple[int, int]],
    fuel: int,
    mined: int,
    alive: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, ore),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "base": {"x": _START[0], "y": _START[1]},
        "fuel": fuel,
        "fuel_max": _FUEL_MAX,
        "ore_mined": mined,
        "ore_left": len(ore),
        "alive": alive,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
