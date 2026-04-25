from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 85
_SLOTS = ("amber", "teal")
_STARTS = {"amber": (1, 1), "teal": (10, 10)}
_RANDOM_WALLS = 18
_JUMPS_TOTAL = 18
_GEMS_TOTAL = 14
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
    role_code, role_team, role_name = _resolve_participants(ctx)
    bots = {role: _build_fn(role_code.get(role, ''), role, events, print_context) for role in _SLOTS}
    game_map = _build_map(ctx)
    walls = game_map["walls"]
    jumps = game_map["jumps"]
    gems = game_map["gems"]
    assert isinstance(walls, set) and isinstance(jumps, dict) and isinstance(gems, set)

    positions = dict(_STARTS)
    collected = {slot: 0 for slot in _SLOTS}
    jump_moves = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    turns = 0
    frames = [_frame(0, "running", positions, walls, jumps, gems, collected, jump_moves, invalid)]

    for turn in range(_MAX_TURNS):
        if not gems:
            break
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        distances: dict[str, int] = {}
        for slot in _SLOTS:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(walls, jumps, gems, positions, slot)
            action = _safe_call(fn, x, y, board, collected[slot], slot)
            if action not in _DELTAS:
                invalid[slot] += 1
                action = "stay"
                events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": slot})
            target, distance = _transition((x, y), str(action), walls, jumps)
            if target == (x, y) and action != "stay":
                invalid[slot] += 1
                events.append({"type": "blocked_jump", "tick": turn, "slot": slot})
            intents[slot] = target
            distances[slot] = distance

        if intents["amber"] == intents["teal"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            distances = {slot: 0 for slot in _SLOTS}
            events.append({"type": "collision_bounce", "tick": turn + 1})
        elif intents["amber"] == positions["teal"] and intents["teal"] == positions["amber"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            distances = {slot: 0 for slot in _SLOTS}
            events.append({"type": "swap_blocked", "tick": turn + 1})

        positions = intents
        for slot in _SLOTS:
            if distances[slot] > 1:
                jump_moves[slot] += 1
            if positions[slot] in gems:
                gems.remove(positions[slot])
                collected[slot] += 1
                events.append({"type": "gem", "tick": turn + 1, "slot": slot})
        turns = turn + 1
        frames.append(_frame(turns, "running", positions, walls, jumps, gems, collected, jump_moves, invalid))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: collected[slot] * 100 + jump_moves[slot] * 4 - invalid[slot] * 10 for slot in _SLOTS}
    scores = {role_team[slot]: max(0, slot_scores[slot]) for slot in _SLOTS}
    placements = _placements(role_team, slot_scores)
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": max(_SLOTS, key=lambda slot: (slot_scores[slot], collected[slot])),
        "winner_slots": _winner_slots(slot_scores),
        "is_tie": _is_tie(slot_scores),
        "gems_left": len(gems),
        "gems_total": _GEMS_TOTAL,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "jumps_total": len(jumps),
        "collected": collected,
        "jump_moves": jump_moves,
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", positions, walls, jumps, gems, collected, jump_moves, invalid, slot_scores))
    payload: dict[str, object] = {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "scores": scores}
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



def _resolve_participants(ctx):
    participants = ctx.get('participants')
    if isinstance(participants, list) and len(participants) >= 2:
        role_code = {}
        role_team = {}
        role_name = {}
        for i, role in enumerate(_SLOTS):
            p = participants[i]
            codes = p.get('codes_by_slot') if isinstance(p, dict) else {}
            code = codes.get('player', '') if isinstance(codes, dict) else ''
            role_code[role] = str(code) if code else ''
            tid = str(p.get('team_id', role)) if isinstance(p, dict) else role
            role_team[role] = tid
            name = p.get('display_name') or p.get('captain_user_id') if isinstance(p, dict) else None
            role_name[role] = str(name) if name else tid
        return role_code, role_team, role_name
    codes = ctx.get('codes_by_slot')
    if isinstance(codes, dict):
        code = str(codes.get('player', ''))
        return {r: code for r in _SLOTS}, {r: r for r in _SLOTS}, {r: r for r in _SLOTS}
    return {r: '' for r in _SLOTS}, {r: r for r in _SLOTS}, {r: r for r in _SLOTS}



def _map_seed(context, fallback):
    participants = context.get('participants')
    if isinstance(participants, list) and len(participants) >= 2:
        run_ids = [str(p.get('run_id', '')) for p in participants if isinstance(p, dict) and p.get('run_id')]
        seed = min(run_ids) if run_ids else context.get('run_id', fallback)
    else:
        seed = context.get('run_id')
    if not isinstance(seed, str) or not seed:
        seed = fallback
    return seed

def _build_fn(code, role, events, print_context):
    namespace = {'__builtins__': _builtins(role, events, print_context)}
    compile_error = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("make_move") or namespace.get("choose_move")
    return (fn if callable(fn) else _fallback_move), compile_error

def _build_map(context: dict[str, Any]) -> dict[str, object]:
    seed = _map_seed(context, "jump_gem_duel_offline")
    rng = random.Random(seed)
    starts = set(_STARTS.values())
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) not in starts]
    for _attempt in range(900):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        jump_cells = [cell for cell in candidates[_RANDOM_WALLS:_RANDOM_WALLS + _JUMPS_TOTAL] if cell not in walls]
        jumps = {cell: rng.choice((2, 3)) for cell in jump_cells}
        shared = (
            _reachable_cells(_STARTS["amber"], walls, jumps)
            & _reachable_cells(_STARTS["teal"], walls, jumps)
        ) - starts - set(jumps)
        shared_list = sorted(shared)
        if len(shared_list) < _GEMS_TOTAL + 4:
            continue
        rng.shuffle(shared_list)
        return {"walls": walls, "jumps": jumps, "gems": set(shared_list[:_GEMS_TOTAL])}
    walls = set(_BORDER_WALLS)
    jumps = {(3, 1): 2, (5, 1): 3, (5, 4): 2, (8, 4): 3, (8, 7): 2, (4, 8): 3}
    gems = {(2, 3), (3, 8), (4, 4), (6, 2), (7, 7), (9, 3), (2, 9), (9, 8), (6, 9), (3, 5), (8, 2), (5, 7), (7, 4), (4, 9)}
    return {"walls": walls, "jumps": jumps, "gems": gems}


def _build_player_fn(context: dict[str, Any], slot: str, events: list[dict[str, object]], print_context: dict[str, int]) -> tuple[Callable[..., object], str | None]:
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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], score: int, slot: str) -> object:
    try:
        return fn(x, y, board, score, slot)
    except TypeError:
        try:
            return fn(x, y, board, score)
        except TypeError:
            try:
                return fn(x, y, board)
            except Exception:
                return None
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _score: int = 0, _slot: str = "") -> str:
    return "stay"


def _board(
    walls: set[tuple[int, int]],
    jumps: dict[tuple[int, int], int],
    gems: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    viewer: str,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for (x, y), distance in jumps.items():
        board[x][y] = distance
    for x, y in gems:
        board[x][y] = 1
    opponent = "teal" if viewer == "amber" else "amber"
    ox, oy = positions[opponent]
    board[ox][oy] = -2
    return board


def _transition(position: tuple[int, int], action: str, walls: set[tuple[int, int]], jumps: dict[tuple[int, int], int]) -> tuple[tuple[int, int], int]:
    if action == "stay":
        return position, 0
    distance = jumps.get(position, 1)
    dx, dy = _DELTAS[action]
    target = (position[0] + dx * distance, position[1] + dy * distance)
    if not _inside(target) or target in walls:
        return position, distance
    return target, distance


def _inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]], jumps: dict[tuple[int, int], int]) -> set[tuple[int, int]]:
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "right", "down", "left"):
            nxt, _distance = _transition(current, action, walls, jumps)
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen




def _winner_slots(slot_scores: dict[str, int]) -> list[str]:
    best = max(slot_scores.values()) if slot_scores else 0
    return [slot for slot in _SLOTS if slot_scores.get(slot, 0) == best]

def _is_tie(slot_scores: dict[str, int]) -> bool:
    return len(_winner_slots(slot_scores)) > 1

def _placements(role_team: dict[str, str], slot_scores: dict[str, int]) -> dict[str, int]:
    ordered = sorted(_SLOTS, key=lambda slot: slot_scores[slot], reverse=True)
    result: dict[str, int] = {}
    last_score: int | None = None
    last_place = 0
    for index, slot in enumerate(ordered, start=1):
        score = slot_scores[slot]
        if score != last_score:
            last_place = index
            last_score = score
        result[role_team[slot]] = last_place
    return result


def _frame(
    tick: int,
    phase: str,
    positions: dict[str, tuple[int, int]],
    walls: set[tuple[int, int]],
    jumps: dict[tuple[int, int], int],
    gems: set[tuple[int, int]],
    collected: dict[str, int],
    jump_moves: dict[str, int],
    invalid: dict[str, int],
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, jumps, gems, positions, "amber"),
        "boards": {slot: _board(walls, jumps, gems, positions, slot) for slot in _SLOTS},
        "width": _WIDTH,
        "height": _HEIGHT,
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "collected": collected,
        "gems_left": len(gems),
        "jump_moves": jump_moves,
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
