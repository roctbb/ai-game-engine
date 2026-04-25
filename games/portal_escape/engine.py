from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 26
_HEIGHT = 20
_MAX_TURNS = 320
_START = (1, 1)
_RANDOM_WALLS = 56
_PORTAL_PAIR_IDS = (2, 3, 4, 5)
_BARRIER_XS = (5, 10, 15, 20)
_ZONES = (
    range(1, 5),
    range(6, 10),
    range(11, 15),
    range(16, 20),
    range(21, 25),
)
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
    portals = game_map["portals"]
    exit_cell = game_map["exit"]
    assert isinstance(walls, set) and isinstance(portals, dict) and isinstance(exit_cell, tuple)

    position = _START
    turns = 0
    invalid_moves = 0
    escaped = False
    frames = [_frame(0, "running", position, walls, portals, exit_cell, escaped, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if escaped:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, portals, exit_cell))
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if target in walls:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        else:
            portal_jump = _portal_target(target, portals)
            if portal_jump is not None:
                portal_id, target = portal_jump
                events.append({"type": "portal", "tick": turn + 1, "portal_id": portal_id, "to_x": target[0], "to_y": target[1]})

        position = target
        turns = turn + 1
        if position == exit_cell:
            escaped = True
            events.append({"type": "escaped", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, portals, exit_cell, escaped, invalid_moves))

    score = max(0, (400 if escaped else 0) - turns * 2 - invalid_moves * 10)
    metrics: dict[str, object] = {
        "turns": turns,
        "escaped": escaped,
        "solved": escaped,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "portal_pairs_total": len(portals),
        "portals_total": sum(len(pair) for pair in portals.values()),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, portals, exit_cell, escaped, invalid_moves, score))
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
        seed = "portal_escape_offline"
    rng = random.Random(seed)
    barrier = {(x, y) for x in _BARRIER_XS for y in range(1, _HEIGHT - 1)}
    zone_cells = [
        [(x, y) for y in range(1, _HEIGHT - 1) for x in zone_xs if (x, y) != _START]
        for zone_xs in _ZONES
    ]
    candidates = [cell for cells in zone_cells for cell in cells]
    for _attempt in range(1500):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | barrier | set(candidates[:_RANDOM_WALLS])
        open_by_zone = [[cell for cell in cells if cell not in walls] for cells in zone_cells]
        if any(len(cells) < 12 for cells in open_by_zone):
            continue

        portals: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}
        used: set[tuple[int, int]] = set()
        source = _START
        valid = True
        for index, portal_id in enumerate(_PORTAL_PAIR_IDS):
            source_reachable = _reachable_cells(source, walls)
            left_options = [
                cell for cell in source_reachable & set(open_by_zone[index])
                if cell not in used and cell != source
            ]
            right_options = [cell for cell in open_by_zone[index + 1] if cell not in used]
            if not left_options or not right_options:
                valid = False
                break
            left = rng.choice(_prefer_cells_near_barrier(left_options, right_side=True))
            right = rng.choice(_prefer_cells_near_barrier(right_options, right_side=False))
            portals[portal_id] = (left, right)
            used.update((left, right))
            source = right
        if not valid:
            continue

        final_reachable = _reachable_cells(source, walls) & set(open_by_zone[-1]) - used
        if not final_reachable:
            continue
        exit_cell = max(final_reachable, key=lambda cell: (cell[0], abs(cell[1] - _START[1])))
        blocked_without_portal = exit_cell not in _reachable_cells(_START, walls)
        if blocked_without_portal and _valid_portal_pairs(portals) and _can_reach_exit(walls, portals, exit_cell):
            return {"walls": walls, "portals": portals, "exit": exit_cell}
    walls = set(_BORDER_WALLS) | barrier | {
        (3, y) for y in range(4, 17) if y not in {6, 12}
    } | {
        (8, y) for y in range(2, 15) if y not in {4, 10}
    } | {
        (13, y) for y in range(5, 18) if y not in {8, 14}
    } | {
        (18, y) for y in range(2, 16) if y not in {5, 11}
    } | {
        (x, 7) for x in range(21, 24)
    }
    portals = {
        2: ((4, 12), (6, 3)),
        3: ((9, 10), (11, 5)),
        4: ((14, 14), (16, 4)),
        5: ((19, 11), (21, 15)),
    }
    return {"walls": walls - set(_portal_cells(portals)) - {_START, (24, 17)}, "portals": portals, "exit": (24, 17)}


def _prefer_cells_near_barrier(cells: list[tuple[int, int]], *, right_side: bool) -> list[tuple[int, int]]:
    if not cells:
        return []
    edge_x = max(x for x, _y in cells) if right_side else min(x for x, _y in cells)
    preferred = [cell for cell in cells if cell[0] == edge_x]
    return preferred or cells


def _can_reach_exit(walls: set[tuple[int, int]], portals: dict[int, tuple[tuple[int, int], tuple[int, int]]], exit_cell: tuple[int, int]) -> bool:
    queue = [_START]
    seen = {_START}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        if current == exit_cell:
            return True
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls:
                continue
            portal_jump = _portal_target(nxt, portals)
            if portal_jump is not None:
                _portal_id, nxt = portal_jump
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return False


def _portal_target(
    position: tuple[int, int],
    portals: dict[int, tuple[tuple[int, int], tuple[int, int]]],
) -> tuple[int, tuple[int, int]] | None:
    for portal_id, pair in portals.items():
        if len(pair) != 2:
            continue
        left, right = pair
        if position == left:
            return portal_id, right
        if position == right:
            return portal_id, left
    return None


def _portal_cells(portals: dict[int, tuple[tuple[int, int], tuple[int, int]]]) -> set[tuple[int, int]]:
    return {cell for pair in portals.values() for cell in pair}


def _valid_portal_pairs(portals: dict[int, tuple[tuple[int, int], tuple[int, int]]]) -> bool:
    if tuple(sorted(portals)) != _PORTAL_PAIR_IDS:
        return False
    cells = [cell for pair in portals.values() for cell in pair]
    return all(len(pair) == 2 and pair[0] != pair[1] for pair in portals.values()) and len(cells) == len(set(cells))


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


def _board(
    walls: set[tuple[int, int]],
    portals: dict[int, tuple[tuple[int, int], tuple[int, int]]],
    exit_cell: tuple[int, int],
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for portal_id, pair in portals.items():
        for x, y in pair:
            board[x][y] = portal_id
    board[exit_cell[0]][exit_cell[1]] = 1
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    portals: dict[int, tuple[tuple[int, int], tuple[int, int]]],
    exit_cell: tuple[int, int],
    escaped: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, portals, exit_cell),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "portal_pairs": [
            {
                "id": portal_id,
                "a": {"x": pair[0][0], "y": pair[0][1]},
                "b": {"x": pair[1][0], "y": pair[1][1]},
            }
            for portal_id, pair in sorted(portals.items())
        ],
        "portals": [
            {"id": portal_id, "x": x, "y": y}
            for portal_id, pair in sorted(portals.items())
            for x, y in pair
        ],
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "escaped": escaped,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
