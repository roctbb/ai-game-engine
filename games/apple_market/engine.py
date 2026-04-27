from __future__ import annotations

import json
import os
import random
import inspect
from typing import Any, Callable


_WIDTH = 15
_HEIGHT = 15
_MAX_TURNS = 1200
_CAPACITY = 3
_APPLES_PER_JUICE = 4
_JUICE_TO_WIN = 3
_SLOTS = ("north_west", "north_east", "south_west", "south_east")
_BASES = {
    "north_west": (1, 1),
    "north_east": (13, 1),
    "south_west": (1, 13),
    "south_east": (13, 13),
}
_STARTS = dict(_BASES)
_TREE = (7, 7)
_RANDOM_WALLS = 28
_INITIAL_APPLES = 12
_SPAWN_INTERVAL = 5
_SPAWN_BATCH = 3
_MAX_APPLES_ON_BOARD = 18
_FREEZE_TURNS = 3
_DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "stay": (0, 0)}
_THROWS = {"throw_up": "up", "throw_down": "down", "throw_left": "left", "throw_right": "right"}
_BORDER_WALLS = {
    *{(x, 0) for x in range(_WIDTH)}, *{(x, _HEIGHT - 1) for x in range(_WIDTH)},
    *{(0, y) for y in range(_HEIGHT)}, *{(_WIDTH - 1, y) for y in range(_HEIGHT)},
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    active_slots, role_code, role_team, role_name = _resolve_participants(ctx)
    bots = {role: _build_fn(role_code.get(role, ''), role, events, print_context) for role in active_slots}
    game_map = _build_map(ctx, active_slots)
    walls = game_map["walls"]
    apples = game_map["apples"]
    spawn_cells = game_map["spawn_cells"]
    assert isinstance(walls, set) and isinstance(apples, set) and isinstance(spawn_cells, list)
    spawn_rng = random.Random(_map_seed(ctx, "apple_market_offline") + ":spawns")
    collision_rng = random.Random(_map_seed(ctx, "apple_market_offline") + ":collisions")

    positions = {slot: _STARTS[slot] for slot in active_slots}
    carrying = {slot: 0 for slot in active_slots}
    delivered = {slot: 0 for slot in active_slots}
    base_apples = {slot: 0 for slot in active_slots}
    juice = {slot: 0 for slot in active_slots}
    invalid = {slot: 0 for slot in active_slots}
    frozen = {slot: 0 for slot in active_slots}
    throws = {slot: 0 for slot in active_slots}
    turns = 0
    winner_slot: str | None = None
    apples_spawned_total = len(apples)
    frames = [_frame(0, "running", active_slots, positions, walls, apples, carrying, delivered, base_apples, juice, invalid, frozen, throws, apples_spawned_total, labels=role_name)]

    for turn in range(_MAX_TURNS):
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        throw_events: list[dict[str, object]] = []
        pending_freezes: dict[str, int] = {}
        for slot in active_slots:
            if frozen[slot] > 0:
                intents[slot] = positions[slot]
                frozen[slot] -= 1
                events.append({"type": "frozen_skip", "tick": turn + 1, "slot": slot, "left": frozen[slot]})
                continue
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            action = _safe_call(
                fn,
                x,
                y,
                _board(walls, apples, positions, active_slots, slot),
                carrying[slot],
                slot,
                _players(active_slots, positions, carrying, frozen, delivered, role_name, slot),
                _bases(active_slots, base_apples, juice, role_name, slot),
            )
            if action in _THROWS:
                if carrying[slot] <= 0:
                    invalid[slot] += 1
                    events.append({"type": "invalid_throw", "tick": turn + 1, "slot": slot, "reason": "empty_hands"})
                    intents[slot] = (x, y)
                    continue
                carrying[slot] -= 1
                throws[slot] += 1
                hit, path = _throw_apple(slot, positions, active_slots, walls, _THROWS[str(action)])
                throw_event = {
                    "type": "throw",
                    "tick": turn + 1,
                    "slot": slot,
                    "direction": _THROWS[str(action)],
                    "start": {"x": x, "y": y},
                    "path": path,
                    "hit": hit,
                    "spent_apple": True,
                    "carrying_after": carrying[slot],
                }
                throw_events.append(throw_event)
                events.append(throw_event)
                if hit is not None:
                    pending_freezes[hit] = max(pending_freezes.get(hit, 0), frozen.get(hit, 0), _FREEZE_TURNS)
                    events.append({"type": "freeze", "tick": turn + 1, "slot": hit, "by": slot, "turns": _FREEZE_TURNS})
                intents[slot] = (x, y)
                continue
            if action not in _DELTAS:
                invalid[slot] += 1
                action = "stay"
            target = _move((x, y), str(action))
            if target in walls or target == _TREE:
                invalid[slot] += 1
                target = (x, y)
            intents[slot] = target

        intents = _resolve_random_cell_collisions(active_slots, positions, intents, events, turn, collision_rng)

        positions = intents
        for slot in active_slots:
            if positions[slot] in apples and carrying[slot] < _CAPACITY:
                apples.remove(positions[slot])
                carrying[slot] += 1
                events.append({"type": "apple", "tick": turn + 1, "slot": slot})
            if positions[slot] == _BASES[slot] and carrying[slot]:
                amount = carrying[slot]
                base_apples[slot] += amount
                delivered[slot] += carrying[slot]
                carrying[slot] = 0
                events.append({"type": "delivered", "tick": turn + 1, "slot": slot, "amount": amount, "base_apples": base_apples[slot]})
                made = base_apples[slot] // _APPLES_PER_JUICE
                if made:
                    base_apples[slot] %= _APPLES_PER_JUICE
                    juice[slot] += made
                    events.append({"type": "juice_made", "tick": turn + 1, "slot": slot, "liters": made, "juice": juice[slot], "base_apples": base_apples[slot]})
                    if juice[slot] >= _JUICE_TO_WIN and winner_slot is None:
                        winner_slot = slot
                        events.append({"type": "juice_win", "tick": turn + 1, "slot": slot, "juice": juice[slot]})
            robbed_base = _base_owner_at(positions[slot], active_slots)
            if robbed_base is not None and robbed_base != slot and carrying[slot] < _CAPACITY and base_apples[robbed_base] > 0:
                stolen = min(_CAPACITY - carrying[slot], base_apples[robbed_base])
                base_apples[robbed_base] -= stolen
                carrying[slot] += stolen
                events.append({"type": "stolen", "tick": turn + 1, "slot": slot, "from": robbed_base, "amount": stolen, "base_apples": base_apples[robbed_base]})
        for slot, turns_to_freeze in pending_freezes.items():
            frozen[slot] = max(frozen.get(slot, 0), turns_to_freeze)
        spawned_apples: list[tuple[int, int]] = []
        if (turn + 1) % _SPAWN_INTERVAL == 0:
            spawned_apples = _spawn_apples(apples, walls, positions, active_slots, spawn_cells, spawn_rng)
            apples_spawned_total += len(spawned_apples)
            if spawned_apples:
                events.append({
                    "type": "apple_spawn",
                    "tick": turn + 1,
                    "cells": [{"x": x, "y": y} for x, y in spawned_apples],
                })
        turns = turn + 1
        frames.append(_frame(turns, "finished" if winner_slot else "running", active_slots, positions, walls, apples, carrying, delivered, base_apples, juice, invalid, frozen, throws, apples_spawned_total, labels=role_name, projectiles=throw_events, spawned_apples=spawned_apples, winner_slot=winner_slot))
        if winner_slot is not None:
            break

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: juice[slot] * 1000 + base_apples[slot] * 120 + delivered[slot] * 10 + carrying[slot] * 30 + throws[slot] * 5 - invalid[slot] * 10 for slot in active_slots}
    scores = {role_team[slot]: max(0, slot_scores[slot]) for slot in active_slots}
    placements = _placements(active_slots, role_team, slot_scores)
    best_slot = winner_slot or max(active_slots, key=lambda slot: (slot_scores[slot], juice[slot], base_apples[slot], delivered[slot]))
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": best_slot,
        "winner_slots": [winner_slot] if winner_slot else _winner_slots(active_slots, slot_scores),
        "is_tie": False if winner_slot else _is_tie(slot_scores),
        "won_by_juice": winner_slot is not None,
        "delivered": delivered,
        "carrying": carrying,
        "base_apples": base_apples,
        "juice": juice,
        "apples_left": len(apples),
        "initial_apples": _INITIAL_APPLES,
        "apples_total": apples_spawned_total,
        "apples_spawned_total": apples_spawned_total,
        "turn_limit": _MAX_TURNS,
        "spawn_interval": _SPAWN_INTERVAL,
        "spawn_batch": _SPAWN_BATCH,
        "max_apples_on_board": _MAX_APPLES_ON_BOARD,
        "tree": {"x": _TREE[0], "y": _TREE[1]},
        "capacity": _CAPACITY,
        "apples_per_juice": _APPLES_PER_JUICE,
        "juice_to_win": _JUICE_TO_WIN,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid,
        "frozen": frozen,
        "throws": throws,
        "slot_scores": slot_scores,
        "active_slots": active_slots,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})
    frames.append(_frame(len(frames), "finished", active_slots, positions, walls, apples, carrying, delivered, base_apples, juice, invalid, frozen, throws, apples_spawned_total, slot_scores, labels=role_name, winner_slot=winner_slot))
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
            active_slots = list(_SLOTS)
        role_code = {r: str(codes.get(r) or codes.get('player') or '') for r in active_slots}
        role_team = {r: f'team-{r}' for r in active_slots}
        return active_slots, role_code, role_team, dict(role_team)
    active_slots = list(_SLOTS)
    role_team = {r: f'team-{r}' for r in active_slots}
    return active_slots, {r: '' for r in active_slots}, role_team, dict(role_team)


def _slots_for_count(count: int) -> list[str]:
    if count <= 2:
        return ["north_west", "south_east"]
    if count == 3:
        return ["north_west", "north_east", "south_west"]
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

def _build_map(context: dict[str, Any], active_slots: list[str]) -> dict[str, object]:
    seed = _map_seed(context, "apple_market_offline")
    rng = random.Random(seed)
    blocked = set(_STARTS.values()) | set(_BASES.values()) | {_TREE}
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) not in blocked]
    for _attempt in range(500):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        reachable = [_reachable_cells(_BASES[slot], walls | {_TREE}) for slot in active_slots]
        shared = sorted(set.intersection(*reachable) - blocked)
        if len(shared) < _INITIAL_APPLES + 12:
            continue
        apples = _choose_initial_apples(shared, rng)
        return {"walls": walls, "apples": apples, "spawn_cells": shared}
    walls = set(_BORDER_WALLS)
    reachable = [_reachable_cells(_BASES[slot], walls | {_TREE}) for slot in active_slots]
    shared = sorted(set.intersection(*reachable) - blocked)
    return {"walls": walls, "apples": _choose_initial_apples(shared, rng), "spawn_cells": shared}


def _choose_initial_apples(shared: list[tuple[int, int]], rng: random.Random) -> set[tuple[int, int]]:
    near_tree = [cell for cell in shared if _tree_distance(cell) <= 4]
    far = [cell for cell in shared if cell not in set(near_tree)]
    rng.shuffle(near_tree)
    rng.shuffle(far)
    return set((near_tree + far)[:_INITIAL_APPLES])


def _tree_distance(cell: tuple[int, int]) -> int:
    return abs(cell[0] - _TREE[0]) + abs(cell[1] - _TREE[1])


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
    return {"abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate, "float": float, "int": int, "len": len, "list": list, "max": max, "min": min, "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip}


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], carrying: int, slot: str, players: list[dict[str, object]], bases: list[dict[str, object]]) -> object:
    try:
        return fn(x, y, board, carrying, players, bases, slot)
    except TypeError:
        sixth_arg = slot if _prefers_slot_arg(fn, 5) else bases
        fallback_sixth_arg = bases if sixth_arg == slot else slot
        try:
            return fn(x, y, board, carrying, players, sixth_arg)
        except TypeError:
            try:
                return fn(x, y, board, carrying, players, fallback_sixth_arg)
            except TypeError:
                pass
            except Exception:
                return None
        except Exception:
            return None
        if _prefers_bases_as_fifth_arg(fn):
            fifth_arg = bases
        elif _prefers_slot_arg(fn, 4):
            fifth_arg = slot
        else:
            fifth_arg = players
        fallback_fifth_args = [arg for arg in (players, bases, slot) if arg is not fifth_arg]
        try:
            return fn(x, y, board, carrying, fifth_arg)
        except TypeError:
            pass
        except Exception:
            return None
        for arg in fallback_fifth_args:
            try:
                return fn(x, y, board, carrying, arg)
            except TypeError:
                continue
            except Exception:
                return None
        try:
            return fn(x, y, board, carrying)
        except TypeError:
            try:
                return fn(x, y, board)
            except Exception:
                return None
        except Exception:
            return None
    except Exception:
        return None


def _prefers_slot_arg(fn: Callable[..., object], index: int) -> bool:
    try:
        parameters = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    if len(parameters) <= index:
        return False
    return parameters[index].name in {"slot", "role", "player_slot"}


def _prefers_bases_as_fifth_arg(fn: Callable[..., object]) -> bool:
    try:
        parameters = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    if len(parameters) < 5:
        return False
    return parameters[4].name in {"base", "bases", "base_info"}


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _carrying: int = 0, *_args: object) -> str:
    return "stay"


def _board(walls: set[tuple[int, int]], apples: set[tuple[int, int]], positions: dict[str, tuple[int, int]], active_slots: list[str], viewer: str) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in apples:
        board[x][y] = 1
    tx, ty = _TREE
    board[tx][ty] = 3
    bx, by = _BASES[viewer]
    board[bx][by] = 2
    for slot in active_slots:
        if slot == viewer:
            continue
        ox, oy = positions[slot]
        board[ox][oy] = -2
    return board


def _base_owner_at(position: tuple[int, int], active_slots: list[str]) -> str | None:
    for slot in active_slots:
        if position == _BASES[slot]:
            return slot
    return None


def _bases(active_slots: list[str], base_apples: dict[str, int], juice: dict[str, int], labels: dict[str, str], viewer: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for slot in active_slots:
        x, y = _BASES[slot]
        result.append(
            {
                "slot": slot,
                "name": labels.get(slot, slot),
                "x": x,
                "y": y,
                "apples": int(base_apples.get(slot, 0)),
                "juice": int(juice.get(slot, 0)),
                "is_me": slot == viewer,
            }
        )
    return result


def _players(active_slots: list[str], positions: dict[str, tuple[int, int]], carrying: dict[str, int], frozen: dict[str, int], delivered: dict[str, int], labels: dict[str, str], viewer: str) -> list[dict[str, object]]:
    players: list[dict[str, object]] = []
    for slot in active_slots:
        x, y = positions[slot]
        players.append(
            {
                "slot": slot,
                "name": labels.get(slot, slot),
                "x": x,
                "y": y,
                "carrying": int(carrying.get(slot, 0)),
                "frozen": int(frozen.get(slot, 0)),
                "delivered": int(delivered.get(slot, 0)),
                "is_me": slot == viewer,
            }
        )
    return players


def _throw_apple(slot: str, positions: dict[str, tuple[int, int]], active_slots: list[str], walls: set[tuple[int, int]], direction: str) -> tuple[str | None, list[dict[str, int]]]:
    dx, dy = _DELTAS[direction]
    x, y = positions[slot]
    path: list[dict[str, int]] = []
    for _ in range(5):
        x += dx
        y += dy
        if (x, y) in walls or (x, y) == _TREE:
            break
        path.append({"x": x, "y": y})
        for target_slot in active_slots:
            if target_slot != slot and positions[target_slot] == (x, y):
                return target_slot, path
    return None, path


def _spawn_apples(apples: set[tuple[int, int]], walls: set[tuple[int, int]], positions: dict[str, tuple[int, int]], active_slots: list[str], spawn_cells: list[tuple[int, int]], rng: random.Random) -> list[tuple[int, int]]:
    if len(apples) >= _MAX_APPLES_ON_BOARD:
        return []
    blocked = set(walls) | set(apples) | {_TREE}
    blocked.update(_BASES[slot] for slot in active_slots)
    blocked.update(positions.values())
    candidates: list[tuple[int, int]] = []
    for radius in (2, 3, 4, 6, 99):
        candidates = [cell for cell in spawn_cells if cell not in blocked and _tree_distance(cell) <= radius]
        if candidates:
            break
    rng.shuffle(candidates)
    limit = min(_SPAWN_BATCH, _MAX_APPLES_ON_BOARD - len(apples), len(candidates))
    spawned = candidates[:limit]
    apples.update(spawned)
    return spawned


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


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

def _is_tie(slot_scores: dict[str, int]) -> bool:
    best = max(slot_scores.values()) if slot_scores else 0
    return sum(1 for score in slot_scores.values() if score == best) > 1

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


def _frame(tick: int, phase: str, active_slots: list[str], positions: dict[str, tuple[int, int]], walls: set[tuple[int, int]], apples: set[tuple[int, int]], carrying: dict[str, int], delivered: dict[str, int], base_apples: dict[str, int], juice: dict[str, int], invalid: dict[str, int], frozen: dict[str, int], throws: dict[str, int], apples_spawned_total: int, slot_scores: dict[str, int] | None = None, labels: dict[str, str] | None = None, projectiles: list[dict[str, object]] | None = None, spawned_apples: list[tuple[int, int]] | None = None, winner_slot: str | None = None) -> dict[str, object]:
    slots_snapshot = list(active_slots)
    label_snapshot = labels or {}
    frame: dict[str, object] = {
        "board": _board(walls, apples, positions, slots_snapshot, slots_snapshot[0]),
        "boards": {slot: _board(walls, apples, positions, slots_snapshot, slot) for slot in slots_snapshot},
        "width": _WIDTH,
        "height": _HEIGHT,
        "turn": tick,
        "turn_limit": _MAX_TURNS,
        "turns_left": max(0, _MAX_TURNS - tick),
        "spawn_interval": _SPAWN_INTERVAL,
        "next_spawn_in": 0 if tick >= _MAX_TURNS else (_SPAWN_INTERVAL - tick % _SPAWN_INTERVAL),
        "active_slots": slots_snapshot,
        "labels": {slot: label_snapshot.get(slot, slot) for slot in slots_snapshot},
        "bases": {
            slot: {
                "x": _BASES[slot][0],
                "y": _BASES[slot][1],
                "apples": int(base_apples.get(slot, 0)),
                "juice": int(juice.get(slot, 0)),
            }
            for slot in slots_snapshot
        },
        "base_info": _bases(slots_snapshot, base_apples, juice, label_snapshot, ""),
        "tree": {"x": _TREE[0], "y": _TREE[1]},
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "carrying": {slot: int(carrying.get(slot, 0)) for slot in slots_snapshot},
        "delivered": {slot: int(delivered.get(slot, 0)) for slot in slots_snapshot},
        "base_apples": {slot: int(base_apples.get(slot, 0)) for slot in slots_snapshot},
        "juice": {slot: int(juice.get(slot, 0)) for slot in slots_snapshot},
        "players": _players(slots_snapshot, positions, carrying, frozen, delivered, label_snapshot, ""),
        "apples_left": len(apples),
        "apples_spawned_total": apples_spawned_total,
        "apples_per_juice": _APPLES_PER_JUICE,
        "juice_to_win": _JUICE_TO_WIN,
        "winner_slot": winner_slot,
        "spawned_apples": [{"x": x, "y": y} for x, y in spawned_apples or []],
        "invalid_moves": {slot: int(invalid.get(slot, 0)) for slot in slots_snapshot},
        "frozen": {slot: int(frozen.get(slot, 0)) for slot in slots_snapshot},
        "throws": {slot: int(throws.get(slot, 0)) for slot in slots_snapshot},
        "projectiles": projectiles or [],
    }
    if slot_scores is not None:
        frame["slot_scores"] = {slot: int(slot_scores.get(slot, 0)) for slot in slots_snapshot}
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
