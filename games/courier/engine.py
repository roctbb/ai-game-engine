from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 10
_HEIGHT = 10
_MAX_TURNS = 120
_START = (1, 1)
_RANDOM_WALLS = 14
_PACKAGES_TOTAL = 3
_DEPOTS_TOTAL = 3
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
    packages = game_map["packages"]
    depots = game_map["depots"]
    assert isinstance(walls, set) and isinstance(packages, set) and isinstance(depots, set)

    position = _START
    carrying = False
    delivered = 0
    invalid_moves = 0
    turns = 0
    frames = [_frame(0, "running", position, packages, depots, walls, carrying, delivered, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if not packages and not carrying:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(packages, depots, walls, position), carrying)
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
        turns += 1

        if not carrying and position in packages:
            carrying = True
            packages.remove(position)
            events.append({"type": "pickup", "tick": turn + 1, "x": position[0], "y": position[1]})
        elif carrying and position in depots:
            carrying = False
            delivered += 1
            events.append({"type": "delivery", "tick": turn + 1, "x": position[0], "y": position[1]})

        frames.append(_frame(turn + 1, "running", position, packages, depots, walls, carrying, delivered, invalid_moves))

    completed = not packages and not carrying
    score = max(0, delivered * 120 + (200 if completed else 0) - turns * 2 - invalid_moves * 15)
    metrics: dict[str, object] = {
        "turns": turns,
        "delivered": delivered,
        "packages_total": _PACKAGES_TOTAL,
        "packages_left": len(packages) + (1 if carrying else 0),
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "completed": completed,
        "solved": completed,
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, packages, depots, walls, carrying, delivered, invalid_moves, score))
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
        seed = "courier_offline"
    rng = random.Random(seed)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) != _START
    ]
    for _attempt in range(400):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        reachable = sorted(_reachable_cells(walls) - {_START})
        if len(reachable) < _PACKAGES_TOTAL + _DEPOTS_TOTAL + 6:
            continue
        rng.shuffle(reachable)
        packages = set(reachable[:_PACKAGES_TOTAL])
        depots = set(reachable[_PACKAGES_TOTAL:_PACKAGES_TOTAL + _DEPOTS_TOTAL])
        return {"walls": walls, "packages": packages, "depots": depots}
    walls = set(_BORDER_WALLS)
    reachable = sorted(_reachable_cells(walls) - {_START})
    rng.shuffle(reachable)
    return {
        "walls": walls,
        "packages": set(reachable[:_PACKAGES_TOTAL]),
        "depots": set(reachable[_PACKAGES_TOTAL:_PACKAGES_TOTAL + _DEPOTS_TOTAL]),
    }


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], carrying: bool) -> object:
    try:
        return fn(x, y, board, carrying)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _carrying: bool = False) -> str:
    return "right"


def _board(
    packages: set[tuple[int, int]],
    depots: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    position: tuple[int, int],
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in packages:
        board[x][y] = 1
    for x, y in depots:
        board[x][y] = 2
    board[position[0]][position[1]] = 0
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    packages: set[tuple[int, int]],
    depots: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    carrying: bool,
    delivered: int,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(packages, depots, walls, position),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "packages_left": len(packages) + (1 if carrying else 0),
        "delivered": delivered,
        "carrying": carrying,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
