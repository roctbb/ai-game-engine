from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 180
_START = (1, 1)
_WATER_MAX = 3
_FIRES_TOTAL = 8
_WATER_SOURCES_TOTAL = 4
_RANDOM_WALLS = 20
_SPREAD_EVERY = 12
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
    spread_rng = random.Random(str(ctx.get("run_id") or "fire_rescue_offline") + "_spread")
    walls = game_map["walls"]
    fires = game_map["fires"]
    water_sources = game_map["water_sources"]
    assert isinstance(walls, set) and isinstance(fires, set) and isinstance(water_sources, set)

    position = _START
    water = _WATER_MAX
    extinguished = 0
    invalid_moves = 0
    turns = 0
    fires_total = len(fires)
    frames = [_frame(0, "running", position, walls, fires, water_sources, water, extinguished, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if not fires:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, fires, water_sources), water)
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if target in walls:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        elif target in fires and water <= 0:
            invalid_moves += 1
            target = position
            events.append({"type": "no_water", "message": "Нельзя тушить пожар: закончилась вода.", "tick": turn, "x": target[0], "y": target[1]})

        position = target
        turns += 1

        if position in water_sources:
            water = _WATER_MAX
            events.append({"type": "water_refill", "tick": turn + 1, "x": position[0], "y": position[1]})
        if position in fires and water > 0:
            fires.remove(position)
            water -= 1
            extinguished += 1
            events.append({"type": "fire_extinguished", "tick": turn + 1, "x": position[0], "y": position[1]})
        if fires and (turn + 1) % _SPREAD_EVERY == 0:
            new_fire = _spread_fire(fires, walls, water_sources, position, spread_rng)
            if new_fire is not None:
                fires.add(new_fire)
                fires_total += 1
                events.append({"type": "fire_spread", "tick": turn + 1, "x": new_fire[0], "y": new_fire[1]})

        frames.append(_frame(turn + 1, "running", position, walls, fires, water_sources, water, extinguished, invalid_moves))

    completed = not fires
    score = max(0, extinguished * 100 + (250 if completed else 0) - turns * 2 - invalid_moves * 15)
    metrics: dict[str, object] = {
        "turns": turns,
        "extinguished": extinguished,
        "fires_total": fires_total,
        "fires_left": len(fires),
        "water": water,
        "completed": completed,
        "solved": completed,
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, fires, water_sources, water, extinguished, invalid_moves, score))
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
        seed = "fire_rescue_offline"
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
        reachable = sorted(_reachable_cells(walls) - {_START})
        if len(reachable) < _FIRES_TOTAL + _WATER_SOURCES_TOTAL + 10:
            continue
        rng.shuffle(reachable)
        fires = set(reachable[:_FIRES_TOTAL])
        water_sources = set(reachable[_FIRES_TOTAL:_FIRES_TOTAL + _WATER_SOURCES_TOTAL])
        return {"walls": walls, "fires": fires, "water_sources": water_sources}
    walls = set(_BORDER_WALLS)
    reachable = sorted(_reachable_cells(walls) - {_START})
    rng.shuffle(reachable)
    return {
        "walls": walls,
        "fires": set(reachable[:_FIRES_TOTAL]),
        "water_sources": set(reachable[_FIRES_TOTAL:_FIRES_TOTAL + _WATER_SOURCES_TOTAL]),
    }


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], water: int) -> object:
    try:
        return fn(x, y, board, water)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _water: int = 0) -> str:
    return "right"


def _board(walls: set[tuple[int, int]], fires: set[tuple[int, int]], water_sources: set[tuple[int, int]]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in fires:
        board[x][y] = 1
    for x, y in water_sources:
        board[x][y] = 2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _reachable_cells(walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue = [_START]
    seen = {_START}
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


def _spread_fire(
    fires: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    water_sources: set[tuple[int, int]],
    position: tuple[int, int],
    rng: random.Random,
) -> tuple[int, int] | None:
    candidates: list[tuple[int, int]] = []
    blocked = walls | water_sources | fires | {position, _START}
    for fire in fires:
        for action in ("up", "down", "left", "right"):
            cell = _move(fire, action)
            if cell not in blocked:
                candidates.append(cell)
    return rng.choice(candidates) if candidates else None


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    fires: set[tuple[int, int]],
    water_sources: set[tuple[int, int]],
    water: int,
    extinguished: int,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, fires, water_sources),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "water": water,
        "extinguished": extinguished,
        "fires_left": len(fires),
        "fire_spread_every": _SPREAD_EVERY,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
