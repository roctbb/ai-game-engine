from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 13
_HEIGHT = 13
_MAX_TURNS = 130
_SLOTS = ("red", "blue")
_BASES = {"red": (1, 1), "blue": (11, 11)}
_STARTS = {"red": (1, 2), "blue": (11, 10)}
_RANDOM_WALLS = 24
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
    bots = {slot: _build_player_fn(ctx, slot, events, print_context) for slot in _SLOTS}
    walls = _build_walls(ctx)

    positions = dict(_STARTS)
    has_flag = {slot: False for slot in _SLOTS}
    captures = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    turns = 0
    frames = [_frame(0, "running", walls, positions, has_flag, captures, invalid)]

    for turn in range(_MAX_TURNS):
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        for slot in _SLOTS:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(walls, positions, slot, has_flag[slot])
            action = _safe_call(fn, x, y, board, has_flag[slot], slot)
            if action not in _DELTAS:
                invalid[slot] += 1
                action = "stay"
                events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": slot})
            target = _move((x, y), str(action))
            if target in walls:
                invalid[slot] += 1
                target = (x, y)
                events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "slot": slot})
            intents[slot] = target

        if intents["red"] == intents["blue"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "collision_bounce", "tick": turn + 1})
        elif intents["red"] == positions["blue"] and intents["blue"] == positions["red"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "swap_blocked", "tick": turn + 1})

        positions = intents
        turns = turn + 1
        for slot in _SLOTS:
            opponent = _opponent(slot)
            if not has_flag[slot] and positions[slot] == _BASES[opponent]:
                has_flag[slot] = True
                events.append({"type": "flag_taken", "tick": turns, "slot": slot})
            if has_flag[slot] and positions[slot] == _BASES[slot]:
                has_flag[slot] = False
                captures[slot] += 1
                events.append({"type": "capture", "tick": turns, "slot": slot, "count": captures[slot]})
        frames.append(_frame(turns, "running", walls, positions, has_flag, captures, invalid))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: captures[slot] * 300 + (80 if has_flag[slot] else 0) - invalid[slot] * 10 for slot in _SLOTS}
    team_ids = _team_ids(ctx)
    scores = {team_ids[slot]: max(0, slot_scores[slot]) for slot in _SLOTS}
    placements = _placements(team_ids, slot_scores)
    winner_slot = max(_SLOTS, key=lambda slot: (slot_scores[slot], captures[slot]))
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": winner_slot,
        "winner_slots": _winner_slots(slot_scores),
        "is_tie": _is_tie(slot_scores),
        "captures": captures,
        "has_flag": has_flag,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", walls, positions, has_flag, captures, invalid, slot_scores))
    payload: dict[str, object] = {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "scores": scores}
    if str(ctx.get("run_kind") or "training_match") == "competition_match":
        payload["placements"] = placements
    return payload


def _load_context() -> dict[str, Any]:
    raw = os.getenv("AGP_RUN_CONTEXT")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_walls(context: dict[str, Any]) -> set[tuple[int, int]]:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "capture_flag_offline"
    rng = random.Random(seed)
    blocked = set(_STARTS.values()) | set(_BASES.values())
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in blocked
    ]
    for _attempt in range(500):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        red_reachable = _reachable_cells(_STARTS["red"], walls)
        blue_reachable = _reachable_cells(_STARTS["blue"], walls)
        if _BASES["blue"] in red_reachable and _BASES["red"] in blue_reachable:
            return walls
    return set(_BORDER_WALLS)


def _build_player_fn(
    context: dict[str, Any],
    slot: str,
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[Callable[..., object], str | None]:
    code = ""
    codes = context.get("codes_by_slot")
    if isinstance(codes, dict) and isinstance(codes.get(slot), str):
        code = str(codes[slot])
    namespace = {"__builtins__": _builtins(slot, events, print_context)}
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("make_move") or namespace.get("choose_move")
    return (fn if callable(fn) else _fallback_move), compile_error


def _builtins(slot: str, events: list[dict[str, object]], print_context: dict[str, int]) -> dict[str, object]:
    def bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message += end
        for line in message.splitlines() or [""]:
            events.append({"type": "bot_print", "tick": int(print_context.get("tick", 0)), "role": slot, "message": line})

    return {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
        "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
        "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], has_flag: bool, slot: str) -> object:
    try:
        return fn(x, y, board, has_flag, slot)
    except TypeError:
        try:
            return fn(x, y, board, has_flag)
        except TypeError:
            try:
                return fn(x, y, board)
            except Exception:
                return None
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _has_flag: bool = False, _slot: str = "") -> str:
    return "stay"


def _board(
    walls: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    viewer: str,
    carrying_flag: bool,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    own_base = _BASES[viewer]
    enemy_base = _BASES[_opponent(viewer)]
    board[own_base[0]][own_base[1]] = 2
    board[enemy_base[0]][enemy_base[1]] = 1 if not carrying_flag else 0
    opponent = _opponent(viewer)
    ox, oy = positions[opponent]
    board[ox][oy] = -2
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


def _opponent(slot: str) -> str:
    return "blue" if slot == "red" else "red"


def _team_ids(ctx: dict[str, Any]) -> dict[str, str]:
    team_id = ctx.get("team_id")
    return {
        "red": str(team_id) if isinstance(team_id, str) and team_id else "team-red",
        "blue": "team-blue",
    }



def _winner_slots(slot_scores: dict[str, int]) -> list[str]:
    best = max(slot_scores.values()) if slot_scores else 0
    return [slot for slot in _SLOTS if slot_scores.get(slot, 0) == best]

def _is_tie(slot_scores: dict[str, int]) -> bool:
    return len(_winner_slots(slot_scores)) > 1

def _placements(team_ids: dict[str, str], slot_scores: dict[str, int]) -> dict[str, int]:
    ordered = sorted(_SLOTS, key=lambda slot: slot_scores[slot], reverse=True)
    result: dict[str, int] = {}
    last_score: int | None = None
    last_place = 0
    for index, slot in enumerate(ordered, start=1):
        score = slot_scores[slot]
        if score != last_score:
            last_place = index
            last_score = score
        result[team_ids[slot]] = last_place
    return result


def _frame(
    tick: int,
    phase: str,
    walls: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    has_flag: dict[str, bool],
    captures: dict[str, int],
    invalid: dict[str, int],
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, positions, "red", has_flag["red"]),
        "boards": {slot: _board(walls, positions, slot, has_flag[slot]) for slot in _SLOTS},
        "width": _WIDTH,
        "height": _HEIGHT,
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "bases": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in _BASES.items()},
        "has_flag": has_flag,
        "captures": captures,
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
