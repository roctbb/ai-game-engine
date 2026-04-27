from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 17
_HEIGHT = 17
_MAX_TURNS = 180
_SLOTS = ("red", "blue", "green", "yellow")
_BASES = {
    "red": (1, 1),
    "blue": (15, 15),
    "green": (15, 1),
    "yellow": (1, 15),
}
_STARTS = dict(_BASES)
_FLAG_HOME = (8, 8)
_RANDOM_WALLS = 34
_BUILD_LIMIT = 3
_SHOT_RANGE = 7
_FREEZE_TURNS = 3
_DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    "stay": (0, 0),
}
_SHOOT_ACTIONS = {f"shoot_{name}": delta for name, delta in _DELTAS.items() if name != "stay"}
_BUILD_ACTIONS = {f"build_{name}": delta for name, delta in _DELTAS.items() if name != "stay"}
_ALL_ACTIONS = set(_DELTAS) | set(_SHOOT_ACTIONS) | set(_BUILD_ACTIONS)
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
    bots = {slot: _build_fn(role_code.get(slot, ""), slot, events, print_context) for slot in active_slots}
    fixed_walls = _build_walls(ctx, active_slots)
    collision_rng = random.Random(_map_seed(ctx, "capture_flag_offline") + ":collisions")

    positions = {slot: _STARTS[slot] for slot in active_slots}
    flag: dict[str, object] = {"carrier": None, "x": _FLAG_HOME[0], "y": _FLAG_HOME[1]}
    built_walls: set[tuple[int, int]] = set()
    builds_left = {slot: _BUILD_LIMIT for slot in active_slots}
    frozen = {slot: 0 for slot in active_slots}
    captures = {slot: 0 for slot in active_slots}
    invalid = {slot: 0 for slot in active_slots}
    shots = {slot: 0 for slot in active_slots}
    turns = 0
    frames = [
        _frame(
            0,
            "running",
            active_slots,
            fixed_walls,
            built_walls,
            positions,
            flag,
            captures,
            invalid,
            builds_left,
            frozen,
            [],
            shots,
            role_name,
        )
    ]

    for turn in range(_MAX_TURNS):
        print_context["tick"] = turn
        actions: dict[str, str] = {}
        intents: dict[str, tuple[int, int]] = {slot: positions[slot] for slot in active_slots}
        shots_this_turn: list[dict[str, object]] = []

        for slot in active_slots:
            if frozen[slot] > 0:
                frozen[slot] -= 1
                actions[slot] = "stay"
                events.append({"type": "frozen_skip", "tick": turn, "slot": slot, "left": frozen[slot]})
                continue

            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(fixed_walls, built_walls, positions, active_slots, slot, flag)
            action = _safe_call(fn, x, y, board, flag.get("carrier") == slot, slot)
            action = str(action).strip().lower() if isinstance(action, str) else ""
            if action not in _ALL_ACTIONS:
                invalid[slot] += 1
                action = "stay"
                events.append(
                    {
                        "type": "invalid_action",
                        "message": "Недопустимое действие: верните ход, shoot_* или build_*.",
                        "tick": turn,
                        "slot": slot,
                    }
                )
            actions[slot] = action

        for slot, action in actions.items():
            if action in _BUILD_ACTIONS:
                _apply_build(
                    slot,
                    _BUILD_ACTIONS[action],
                    active_slots,
                    fixed_walls,
                    built_walls,
                    positions,
                    flag,
                    builds_left,
                    invalid,
                    events,
                    turn,
                )

        for slot, action in actions.items():
            if action not in _DELTAS or frozen[slot] > 0:
                continue
            target = _move(positions[slot], action)
            if target in fixed_walls or target in built_walls:
                invalid[slot] += 1
                events.append(
                    {
                        "type": "blocked_move",
                        "message": "Ход заблокирован стеной.",
                        "tick": turn,
                        "slot": slot,
                    }
                )
                target = positions[slot]
            intents[slot] = target

        intents = _resolve_collisions(active_slots, positions, intents, flag, events, turn, collision_rng)
        positions = intents
        turns = turn + 1

        carrier = flag.get("carrier")
        if isinstance(carrier, str) and positions.get(carrier) == _BASES[carrier]:
            captures[carrier] += 1
            flag = {"carrier": None, "x": _FLAG_HOME[0], "y": _FLAG_HOME[1]}
            events.append({"type": "capture", "tick": turns, "slot": carrier, "count": captures[carrier]})

        if flag.get("carrier") is None:
            flag_pos = _flag_position(flag)
            for slot in active_slots:
                if frozen[slot] == 0 and positions[slot] == flag_pos:
                    flag = {"carrier": slot, "x": None, "y": None}
                    events.append({"type": "flag_taken", "tick": turns, "slot": slot})
                    break

        for slot, action in actions.items():
            if action in _SHOOT_ACTIONS and frozen[slot] == 0:
                shots[slot] += 1
                shot_event = _apply_shot(
                    slot,
                    _SHOOT_ACTIONS[action],
                    active_slots,
                    fixed_walls,
                    built_walls,
                    positions,
                    flag,
                    frozen,
                )
                shot_event["tick"] = turn + 1
                shots_this_turn.append(shot_event)
                events.append(shot_event)

        frames.append(
            _frame(
                turns,
                "running",
                active_slots,
                fixed_walls,
                built_walls,
                positions,
                flag,
                captures,
                invalid,
                builds_left,
                frozen,
                shots_this_turn,
                shots,
                role_name,
            )
        )

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {
        slot: captures[slot] * 500
        + (120 if flag.get("carrier") == slot else 0)
        + shots[slot] * 3
        + builds_left[slot] * 4
        - invalid[slot] * 12
        for slot in active_slots
    }
    scores = {role_team[slot]: max(0, slot_scores[slot]) for slot in active_slots}
    placements = _placements(active_slots, role_team, slot_scores)
    winner_slot = max(active_slots, key=lambda slot: (captures[slot], slot_scores[slot]))
    metrics: dict[str, object] = {
        "turns": turns,
        "active_slots": active_slots,
        "winner_slot": winner_slot,
        "winner_slots": _winner_slots(active_slots, slot_scores),
        "is_tie": _is_tie(active_slots, slot_scores),
        "captures": captures,
        "flag_carrier": flag.get("carrier"),
        "flag": flag,
        "walls_total": len(fixed_walls) - len(_BORDER_WALLS),
        "built_walls": len(built_walls),
        "builds_left": builds_left,
        "frozen": frozen,
        "shots": shots,
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(
        _frame(
            len(frames),
            "finished",
            active_slots,
            fixed_walls,
            built_walls,
            positions,
            flag,
            captures,
            invalid,
            builds_left,
            frozen,
            [],
            shots,
            role_name,
            slot_scores,
        )
    )
    payload: dict[str, object] = {
        "status": "finished",
        "metrics": metrics,
        "frames": frames,
        "events": events,
        "scores": scores,
        "placements": placements,
    }
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


def _resolve_participants(ctx: dict[str, Any]) -> tuple[list[str], dict[str, str], dict[str, str], dict[str, str]]:
    participants = ctx.get("participants")
    if isinstance(participants, list) and len(participants) >= 2:
        active_slots = _slots_for_count(len(participants))
        role_code: dict[str, str] = {}
        role_team: dict[str, str] = {}
        role_name: dict[str, str] = {}
        for index, slot in enumerate(active_slots):
            participant = participants[index]
            codes = participant.get("codes_by_slot") if isinstance(participant, dict) else {}
            code = codes.get("player", "") if isinstance(codes, dict) else ""
            role_code[slot] = str(code) if code else ""
            team_id = str(participant.get("team_id", slot)) if isinstance(participant, dict) else slot
            role_team[slot] = team_id
            name = participant.get("display_name") or participant.get("captain_user_id") if isinstance(participant, dict) else None
            role_name[slot] = str(name) if name else team_id
        return active_slots, role_code, role_team, role_name

    codes = ctx.get("codes_by_slot")
    if isinstance(codes, dict):
        explicit_slots = [slot for slot in _SLOTS if isinstance(codes.get(slot), str)]
        active_slots = _slots_for_count(len(explicit_slots)) if len(explicit_slots) >= 2 else ["red", "blue"]
        role_code = {slot: str(codes.get(slot) or codes.get("player") or "") for slot in active_slots}
        role_team = {slot: f"team-{slot}" for slot in active_slots}
        return active_slots, role_code, role_team, dict(role_team)

    active_slots = ["red", "blue"]
    role_team = {slot: f"team-{slot}" for slot in active_slots}
    return active_slots, {slot: "" for slot in active_slots}, role_team, dict(role_team)


def _slots_for_count(count: int) -> list[str]:
    return list(_SLOTS[: max(2, min(4, count))])


def _map_seed(context: dict[str, Any], fallback: str) -> str:
    participants = context.get("participants")
    if isinstance(participants, list) and len(participants) >= 2:
        run_ids = [str(p.get("run_id", "")) for p in participants if isinstance(p, dict) and p.get("run_id")]
        seed = min(run_ids) if run_ids else context.get("run_id", fallback)
    else:
        seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = fallback
    return seed


def _build_fn(code: str, role: str, events: list[dict[str, object]], print_context: dict[str, int]):
    namespace = {"__builtins__": _builtins(role, events, print_context)}
    compile_error = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("make_move") or namespace.get("choose_move")
    return (fn if callable(fn) else _fallback_move), compile_error


def _build_walls(context: dict[str, Any], active_slots: list[str]) -> set[tuple[int, int]]:
    seed = _map_seed(context, "capture_flag_offline")
    rng = random.Random(seed)
    protected = set(_BASES.values()) | {_FLAG_HOME}
    for bx, by in list(protected):
        for dx, dy in _DELTAS.values():
            protected.add((bx + dx, by + dy))
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in protected
    ]
    required = [_BASES[slot] for slot in active_slots] + [_FLAG_HOME]
    for _attempt in range(700):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        reachable = _reachable_cells(required[0], walls, set())
        if all(cell in reachable for cell in required):
            return walls
    return set(_BORDER_WALLS)


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
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": bot_print,
        "range": range,
        "set": set,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], has_flag: bool, slot: str) -> object:
    for args in ((x, y, board, has_flag, slot), (x, y, board, has_flag), (x, y, board)):
        try:
            return fn(*args)
        except TypeError:
            continue
        except Exception:
            return None
    return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _has_flag: bool = False, _slot: str = "") -> str:
    return "stay"


def _board(
    fixed_walls: set[tuple[int, int]],
    built_walls: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    active_slots: list[str],
    viewer: str,
    flag: dict[str, object],
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in fixed_walls:
        board[x][y] = -1
    for x, y in built_walls:
        board[x][y] = -3
    for slot in active_slots:
        bx, by = _BASES[slot]
        board[bx][by] = 2 if slot == viewer else 3
    if flag.get("carrier") is None:
        fx, fy = _flag_position(flag)
        board[fx][fy] = 1
    for slot in active_slots:
        if slot == viewer:
            continue
        px, py = positions[slot]
        board[px][py] = -4 if flag.get("carrier") == slot else -2
    return board


def _apply_shot(
    slot: str,
    delta: tuple[int, int],
    active_slots: list[str],
    fixed_walls: set[tuple[int, int]],
    built_walls: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    flag: dict[str, object],
    frozen: dict[str, int],
) -> dict[str, object]:
    sx, sy = positions[slot]
    dx, dy = delta
    path: list[dict[str, int]] = []
    players_by_pos = {pos: other for other, pos in positions.items() if other != slot}
    for distance in range(1, _SHOT_RANGE + 1):
        cell = (sx + dx * distance, sy + dy * distance)
        path.append({"x": cell[0], "y": cell[1]})
        if cell in fixed_walls:
            return {"type": "shot_blocked", "slot": slot, "path": path, "x": cell[0], "y": cell[1]}
        if cell in built_walls:
            built_walls.remove(cell)
            return {"type": "wall_destroyed", "slot": slot, "path": path, "x": cell[0], "y": cell[1]}
        target = players_by_pos.get(cell)
        if target in active_slots:
            frozen[target] = max(frozen[target], _FREEZE_TURNS)
            result: dict[str, object] = {
                "type": "shot_hit",
                "slot": slot,
                "target": target,
                "path": path,
                "x": cell[0],
                "y": cell[1],
                "freeze": _FREEZE_TURNS,
            }
            if flag.get("carrier") == target:
                flag["carrier"] = None
                flag["x"] = cell[0]
                flag["y"] = cell[1]
                result["flag_dropped"] = True
            return result
    end = path[-1] if path else {"x": sx, "y": sy}
    return {"type": "shot_missed", "slot": slot, "path": path, "x": end["x"], "y": end["y"]}


def _apply_build(
    slot: str,
    delta: tuple[int, int],
    active_slots: list[str],
    fixed_walls: set[tuple[int, int]],
    built_walls: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    flag: dict[str, object],
    builds_left: dict[str, int],
    invalid: dict[str, int],
    events: list[dict[str, object]],
    turn: int,
) -> None:
    if builds_left[slot] <= 0:
        invalid[slot] += 1
        events.append({"type": "build_failed", "reason": "no_walls_left", "tick": turn, "slot": slot})
        return
    x, y = positions[slot]
    dx, dy = delta
    target = (x + dx, y + dy)
    blocked = set(_BASES[s] for s in active_slots) | set(positions.values())
    if flag.get("carrier") is None:
        blocked.add(_flag_position(flag))
    if target in fixed_walls or target in built_walls or target in blocked:
        invalid[slot] += 1
        events.append({"type": "build_failed", "reason": "blocked_cell", "tick": turn, "slot": slot, "x": target[0], "y": target[1]})
        return
    built_walls.add(target)
    builds_left[slot] -= 1
    events.append({"type": "wall_built", "tick": turn + 1, "slot": slot, "x": target[0], "y": target[1], "left": builds_left[slot]})


def _resolve_collisions(
    active_slots: list[str],
    positions: dict[str, tuple[int, int]],
    intents: dict[str, tuple[int, int]],
    flag: dict[str, object],
    events: list[dict[str, object]],
    turn: int,
    rng: random.Random,
) -> dict[str, tuple[int, int]]:
    result = dict(intents)
    flag_pos = _flag_position(flag) if flag.get("carrier") is None else None
    by_target: dict[tuple[int, int], list[str]] = {}
    for slot, target in intents.items():
        by_target.setdefault(target, []).append(slot)
    for target, contenders in by_target.items():
        if len(contenders) <= 1:
            continue
        incumbents = [slot for slot in contenders if positions[slot] == target]
        winner = rng.choice(incumbents or contenders)
        blocked = [candidate for candidate in contenders if candidate != winner]
        for slot in blocked:
            result[slot] = positions[slot]
        event_type = "flag_race" if flag_pos is not None and target == flag_pos else "collision_bounce"
        events.append({"type": event_type, "tick": turn + 1, "slots": contenders, "winner": winner, "blocked": blocked, "x": target[0], "y": target[1]})
    for i, first in enumerate(active_slots):
        for second in active_slots[i + 1 :]:
            if intents[first] == positions[second] and intents[second] == positions[first]:
                result[first] = positions[first]
                result[second] = positions[second]
                events.append({"type": "swap_blocked", "tick": turn + 1, "slots": [first, second]})
    return result


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _flag_position(flag: dict[str, object]) -> tuple[int, int]:
    x = flag.get("x")
    y = flag.get("y")
    return (int(x), int(y)) if isinstance(x, int) and isinstance(y, int) else _FLAG_HOME


def _reachable_cells(start: tuple[int, int], fixed_walls: set[tuple[int, int]], built_walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    walls = fixed_walls | built_walls
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
    fixed_walls: set[tuple[int, int]],
    built_walls: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    flag: dict[str, object],
    captures: dict[str, int],
    invalid: dict[str, int],
    builds_left: dict[str, int],
    frozen: dict[str, int],
    shots_this_turn: list[dict[str, object]],
    shots: dict[str, int],
    labels: dict[str, str] | None = None,
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    viewer = active_slots[0]
    frame: dict[str, object] = {
        "board": _board(fixed_walls, built_walls, positions, active_slots, viewer, flag),
        "boards": {slot: _board(fixed_walls, built_walls, positions, active_slots, slot, flag) for slot in active_slots},
        "width": _WIDTH,
        "height": _HEIGHT,
        "active_slots": active_slots,
        "labels": {slot: (labels or {}).get(slot, slot) for slot in active_slots},
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "bases": {slot: {"x": _BASES[slot][0], "y": _BASES[slot][1]} for slot in active_slots},
        "flag": dict(flag),
        "flag_home": {"x": _FLAG_HOME[0], "y": _FLAG_HOME[1]},
        "flag_carrier": flag.get("carrier"),
        "captures": dict(captures),
        "invalid_moves": dict(invalid),
        "builds_left": dict(builds_left),
        "built_walls": [{"x": x, "y": y} for x, y in sorted(built_walls)],
        "frozen": dict(frozen),
        "shots": dict(shots),
        "shots_this_turn": shots_this_turn,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
