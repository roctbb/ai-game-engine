from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 16
_HEIGHT = 16
_MAX_TURNS = 180
_SLOTS = ("green", "purple", "orange", "blue")
_STARTS = {
    "green": (1, 1),
    "purple": (14, 14),
    "orange": (14, 1),
    "blue": (1, 14),
}
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
    active_slots, role_code, role_team, role_name = _resolve_participants(ctx)
    bots = {role: _build_fn(role_code.get(role, ''), role, events, print_context) for role in active_slots}
    walls = _build_walls(ctx)
    collision_rng = random.Random(_map_seed(ctx, "territory_duel_offline") + ":collisions")

    positions = {slot: _STARTS[slot] for slot in active_slots}
    ownership = {position: slot for slot, position in positions.items()}
    invalid = {slot: 0 for slot in active_slots}
    turns = 0
    stopped_reason = "turn_limit"
    frames = [_frame(0, "running", active_slots, walls, ownership, positions, invalid, labels=role_name)]

    for turn in range(_MAX_TURNS):
        if not _has_any_expansion_move(active_slots, positions, walls, ownership):
            stopped_reason = "no_moves"
            events.append({"type": "no_moves", "tick": turn, "message": "Ни один игрок больше не может добраться до нейтральной клетки."})
            break
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        for slot in active_slots:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(walls, ownership, positions, active_slots, slot)
            action = _safe_call(fn, x, y, board, slot)
            if action not in _DELTAS:
                invalid[slot] += 1
                action = "stay"
                events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": slot})
            target = _move((x, y), str(action))
            if target in walls:
                invalid[slot] += 1
                target = (x, y)
                events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "slot": slot})
            elif target in ownership and ownership[target] != slot:
                invalid[slot] += 1
                target = (x, y)
                events.append({"type": "blocked_move", "reason": "enemy_territory", "message": "Нельзя наступать на уже покрашенную клетку другого цвета.", "tick": turn, "slot": slot})
            intents[slot] = target

        intents = _resolve_random_cell_collisions(active_slots, positions, intents, events, turn, collision_rng)

        positions = intents
        for slot in active_slots:
            ownership[positions[slot]] = slot
        turns = turn + 1
        frames.append(_frame(turns, "running", active_slots, walls, ownership, positions, invalid, labels=role_name))

    area = {slot: sum(1 for owner in ownership.values() if owner == slot) for slot in active_slots}
    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: area[slot] * 10 - invalid[slot] * 3 for slot in active_slots}
    scores = {role_team[slot]: max(0, slot_scores[slot]) for slot in active_slots}
    placements = _placements(active_slots, role_team, slot_scores)
    winner_slot = max(active_slots, key=lambda slot: (slot_scores[slot], area[slot]))

    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": winner_slot,
        "winner_slots": _winner_slots(active_slots, slot_scores),
        "is_tie": _is_tie(active_slots, slot_scores),
        "area": area,
        "painted_total": len(ownership),
        "neutral_left": (_WIDTH - 2) * (_HEIGHT - 2) - (len(walls) - len(_BORDER_WALLS)) - len(ownership),
        "stopped_reason": stopped_reason,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
        "active_slots": active_slots,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", active_slots, walls, ownership, positions, invalid, slot_scores, labels=role_name))
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
        active_slots = _slots_for_count(min(4, len(participants)))
        role_code = {}
        role_team = {}
        role_name = {}
        for i, role in enumerate(active_slots):
            p = participants[i]
            codes = p.get('codes_by_slot') if isinstance(p, dict) else {}
            code = codes.get('player', '') if isinstance(codes, dict) else ''
            role_code[role] = str(code) if code else ''
            tid = str(p.get('team_id', role)) if isinstance(p, dict) else role
            role_team[role] = tid
            name = p.get('display_name') or p.get('captain_user_id') if isinstance(p, dict) else None
            role_name[role] = str(name) if name else tid
        return active_slots, role_code, role_team, role_name
    codes = ctx.get('codes_by_slot')
    if isinstance(codes, dict):
        active_slots = [slot for slot in _SLOTS if codes.get(slot) or codes.get('player')]
        if len(active_slots) < 2:
            active_slots = _slots_for_count(2)
        role_code = {r: str(codes.get(r) or codes.get('player') or '') for r in active_slots}
        role_team = {r: f'team-{r}' for r in active_slots}
        return active_slots, role_code, role_team, dict(role_team)
    active_slots = _slots_for_count(2)
    role_team = {r: f'team-{r}' for r in active_slots}
    return active_slots, {r: '' for r in active_slots}, role_team, dict(role_team)


def _slots_for_count(count: int) -> list[str]:
    if count <= 2:
        return ["green", "purple"]
    if count == 3:
        return ["green", "purple", "orange"]
    return list(_SLOTS)



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

def _build_walls(context: dict[str, Any]) -> set[tuple[int, int]]:
    seed = _map_seed(context, "territory_duel_offline")
    rng = random.Random(seed)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in set(_STARTS.values())
    ]
    for _attempt in range(400):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        reachable = [_reachable_cells(_STARTS[slot], walls) for slot in _SLOTS]
        if len(set.intersection(*reachable)) >= 110:
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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], slot: str) -> object:
    try:
        return fn(x, y, board, slot)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _slot: str = "") -> str:
    return "stay"


def _board(
    walls: set[tuple[int, int]],
    ownership: dict[tuple[int, int], str],
    positions: dict[str, tuple[int, int]],
    active_slots: list[str],
    viewer: str,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for (x, y), owner in ownership.items():
        board[x][y] = 1 if owner == viewer else 2
    for slot in active_slots:
        if slot == viewer:
            continue
        ox, oy = positions[slot]
        board[ox][oy] = -2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _has_any_expansion_move(active_slots: list[str], positions: dict[str, tuple[int, int]], walls: set[tuple[int, int]], ownership: dict[tuple[int, int], str]) -> bool:
    return any(_can_reach_neutral(slot, positions[slot], walls, ownership) for slot in active_slots)


def _can_reach_neutral(slot: str, start: tuple[int, int], walls: set[tuple[int, int]], ownership: dict[tuple[int, int], str]) -> bool:
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in seen or nxt in walls:
                continue
            owner = ownership.get(nxt)
            if owner is not None and owner != slot:
                continue
            if owner is None:
                return True
            seen.add(nxt)
            queue.append(nxt)
    return False


def _resolve_random_cell_collisions(slots: list[str], positions: dict[str, tuple[int, int]], intents: dict[str, tuple[int, int]], events: list[dict[str, object]], turn: int, rng: random.Random) -> dict[str, tuple[int, int]]:
    result = dict(intents)
    by_target: dict[tuple[int, int], list[str]] = {}
    for slot, target in intents.items():
        by_target.setdefault(target, []).append(slot)
    for target, contenders in by_target.items():
        if len(contenders) <= 1:
            continue
        incumbents = [slot for slot in contenders if positions[slot] == target]
        winner = rng.choice(incumbents or contenders)
        blocked = [slot for slot in contenders if slot != winner]
        for slot in blocked:
            result[slot] = positions[slot]
        events.append({"type": "collision_bounce", "tick": turn + 1, "slots": contenders, "winner": winner, "blocked": blocked, "x": target[0], "y": target[1]})
    for index, first in enumerate(slots):
        for second in slots[index + 1:]:
            if intents[first] == positions[second] and intents[second] == positions[first]:
                result[first] = positions[first]
                result[second] = positions[second]
                events.append({"type": "swap_blocked", "tick": turn + 1, "slots": [first, second]})
    return result


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




def _winner_slots(active_slots: list[str], slot_scores: dict[str, int]) -> list[str]:
    best = max(slot_scores.values()) if slot_scores else 0
    return [slot for slot in active_slots if slot_scores.get(slot, 0) == best]

def _is_tie(active_slots: list[str], slot_scores: dict[str, int]) -> bool:
    return len(_winner_slots(active_slots, slot_scores)) > 1

def _placements(active_slots: list[str], role_team: dict[str, str], slot_scores: dict[str, int]) -> dict[str, int]:
    ordered = sorted(active_slots, key=lambda slot: slot_scores[slot], reverse=True)
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
    active_slots: list[str],
    walls: set[tuple[int, int]],
    ownership: dict[tuple[int, int], str],
    positions: dict[str, tuple[int, int]],
    invalid: dict[str, int],
    slot_scores: dict[str, int] | None = None,
    labels: dict[str, str] | None = None,
) -> dict[str, object]:
    area = {slot: sum(1 for owner in ownership.values() if owner == slot) for slot in active_slots}
    neutral_left = (_WIDTH - 2) * (_HEIGHT - 2) - (len(walls) - len(_BORDER_WALLS)) - len(ownership)
    frame: dict[str, object] = {
        "board": _board(walls, ownership, positions, active_slots, active_slots[0]),
        "boards": {slot: _board(walls, ownership, positions, active_slots, slot) for slot in active_slots},
        "width": _WIDTH,
        "height": _HEIGHT,
        "active_slots": active_slots,
        "labels": {slot: (labels or {}).get(slot, slot) for slot in active_slots},
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "area": area,
        "painted_total": len(ownership),
        "neutral_left": neutral_left,
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
