from __future__ import annotations

import copy
import json
import os
import random
from typing import Any


_SLOTS = ("red", "blue", "green", "yellow")
_DELTAS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0), "stay": (0, 0)}


def _context(context):
    if context is not None:
        return context
    try:
        value = json.loads(os.getenv("AGP_RUN_CONTEXT", "{}"))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _participants(ctx, maximum=4):
    participants = ctx.get("participants")
    codes = ctx.get("codes_by_slot", {})
    codes = codes if isinstance(codes, dict) else {}
    if isinstance(participants, list) and participants:
        if not 2 <= len(participants) <= maximum:
            raise ValueError(f"Для матча нужно от 2 до {maximum} команд")
        slots = list(_SLOTS[:len(participants)])
        teams, labels, sources = {}, {}, {}
        for slot, participant in zip(slots, participants):
            team = str(participant.get("team_id", slot))
            teams[slot] = team
            labels[slot] = str(participant.get("display_name") or team)
            sources[slot] = participant.get("codes_by_slot", {}).get("player", "")
        seeds = [str(p["run_id"]) for p in participants if p.get("run_id")]
        seed = min(seeds) if seeds else str(ctx.get("run_id") or GAME_ID)
    else:
        explicit = [slot for slot in _SLOTS if slot in codes]
        if len(explicit) > maximum:
            raise ValueError(f"В этой игре не больше {maximum} команд")
        slots = explicit if len(explicit) >= 2 else list(_SLOTS[:2])
        teams = {slot: f"team-{slot}" for slot in slots}
        labels = {slot: f"Команда {i + 1}" for i, slot in enumerate(slots)}
        sources = {slot: codes.get(slot, codes.get("player", "")) for slot in slots}
        seed = str(ctx.get("run_id") or GAME_ID)
    return slots, teams, labels, sources, random.Random(seed)


def _build_bots(sources, events, clock, helpers=None):
    bots, errors = {}, {}
    for slot, source in sources.items():
        def bot_print(*values, sep=" ", end="\n", _slot=slot, **kwargs):
            if len(events) < 2000:
                events.append({"type": "bot_print", "tick": clock["tick"], "role": _slot,
                               "message": sep.join(str(v) for v in values)[:1000]})

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level or name not in {"math", "collections", "heapq", "itertools", "copy"}:
                raise ImportError(f"Importing module {name!r} is forbidden")
            return __import__(name, globals, locals, fromlist, level)

        builtins = {"abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
                    "enumerate": enumerate, "float": float, "int": int, "len": len,
                    "list": list, "max": max, "min": min, "range": range, "set": set,
                    "str": str, "sum": sum, "tuple": tuple, "zip": zip, "sorted": sorted,
                    "reversed": reversed, "round": round, "isinstance": isinstance,
                    "next": next, "Exception": Exception, "ValueError": ValueError,
                    "TypeError": TypeError, "print": bot_print, "__import__": safe_import}
        namespace = {"__builtins__": builtins, **(helpers or {})}
        try:
            if source:
                exec(str(source), namespace, namespace)
            fn = namespace.get("make_move")
            if source and not callable(fn):
                raise ValueError("Определите функцию make_move(state)")
            bots[slot] = fn if callable(fn) else lambda state: None
        except Exception as exc:
            errors[slot] = str(exc)
            events.append({"type": "compile_error", "tick": 0, "slot": slot, "message": str(exc)})
            bots[slot] = lambda state: None
    return bots, errors


def _choose(bots, slot, state, events):
    try:
        return bots[slot](copy.deepcopy(state))
    except Exception as exc:
        if len(events) < 2000:
            events.append({"type": "bot_error", "tick": state["tick"], "slot": slot,
                           "message": str(exc)[:1000]})
        return None


def _snapshot(tick, state, labels, finished=False):
    return {"tick": tick, "phase": "finished" if finished else "running",
            "frame": copy.deepcopy({**state, "tick": tick, "labels": labels})}


def _result(slots, teams, labels, scores, frames, events, errors, **metrics):
    best = max(scores.values())
    winners = [slot for slot in slots if scores[slot] == best]
    placements = {teams[slot]: 1 + sum(value > scores[slot] for value in scores.values())
                  for slot in slots}
    metrics.update({"turns": frames[-1]["tick"], "active_slots": slots,
                    "slot_scores": scores, "winner_slots": winners,
                    "winner_slot": winners[0] if len(winners) == 1 else None,
                    "is_tie": len(winners) > 1})
    if errors:
        metrics["compile_errors"] = errors
    frames[-1]["phase"] = "finished"
    frames[-1]["frame"].update({"finished": True, "winner_slots": winners, "slot_scores": scores})
    return {"status": "finished", "scores": {teams[s]: scores[s] for s in slots},
            "placements": placements, "metrics": metrics, "frames": frames,
            "events": events, "replay_ref": None}


def _resolve_moves(positions, intents, block_swaps=False):
    # Recheck after every bounce: a blocked player also blocks incoming players.
    result = dict(intents)
    while True:
        blocked = set()
        for first in positions:
            for second in positions:
                if first == second:
                    continue
                if result[first] == result[second]:
                    blocked.update((first, second))
                if (block_swaps and result[first] == positions[second]
                        and result[second] == positions[first]):
                    blocked.update((first, second))
        changed = False
        for slot in blocked:
            if result[slot] != positions[slot]:
                result[slot] = positions[slot]
                changed = True
        if not changed:
            return result


GAME_ID = "territory_capture_v1"
_SIZE = 30
_MAX_TURNS = 240
_STARTS = ((3, 3), (26, 26), (26, 3), (3, 26))


def capture_area(territory, me, trail):
    """Cells captured by a closed trail. Coordinates use territory[x][y]."""
    width, height = len(territory), len(territory[0])
    barrier = {(x, y) for x in range(width) for y in range(height) if territory[x][y] == me}
    barrier.update(tuple(cell) for cell in trail)
    exterior = set()
    queue = []
    for x in range(width):
        for y in range(height):
            if (x in (0, width - 1) or y in (0, height - 1)) and (x, y) not in barrier:
                exterior.add((x, y))
                queue.append((x, y))
    head = 0
    while head < len(queue):
        x, y = queue[head]
        head += 1
        for dx, dy in _DELTAS.values():
            cell = (x + dx, y + dy)
            if (0 <= cell[0] < width and 0 <= cell[1] < height
                    and cell not in barrier and cell not in exterior):
                exterior.add(cell)
                queue.append(cell)
    return [(x, y) for x in range(width) for y in range(height)
            if (x, y) not in exterior and territory[x][y] != me]


def _step(territory, players, actions):
    positions = {s: (p["x"], p["y"]) for s, p in players.items() if p["alive"]}
    intents = {}
    for slot, (x, y) in positions.items():
        action = actions.get(slot)
        dx, dy = _DELTAS.get(action, (0, 0)) if isinstance(action, str) else (0, 0)
        nx, ny = x + dx, y + dy
        intents[slot] = (nx, ny) if 0 <= nx < _SIZE and 0 <= ny < _SIZE else (x, y)
    moves = _resolve_moves(positions, intents, block_swaps=True)
    old_trails = {s: set(tuple(cell) for cell in players[s]["trail"]) for s in positions}
    killed = set()
    for slot, target in moves.items():
        if target == positions[slot]:
            continue
        for owner, trail in old_trails.items():
            if target in trail:
                killed.add(owner)
    proposals = {}
    for slot, (x, y) in moves.items():
        player = players[slot]
        player["x"], player["y"] = x, y
        if slot in killed:
            continue
        if territory[x][y] == slot:
            if player["trail"]:
                for cell in capture_area(territory, slot, player["trail"]):
                    proposals.setdefault(cell, []).append(slot)
                player["trail"] = []
        elif (x, y) != positions[slot]:
            player["trail"].append([x, y])
    # All proposals were calculated against the same pre-capture board.
    for (x, y), owners in proposals.items():
        if len(owners) == 1:
            territory[x][y] = owners[0]
    for slot in positions:
        if not any(slot in column for column in territory):
            killed.add(slot)
    for slot in killed:
        players[slot]["alive"] = False
        players[slot]["trail"] = []
    for column in territory:
        for y, owner in enumerate(column):
            if owner in killed:
                column[y] = None
    return killed


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    slots, teams, labels, sources, _rng = _participants(_context(context))
    events, clock = [], {"tick": 0}
    bots, errors = _build_bots(sources, events, clock, {"capture_area": capture_area})
    territory = [[None for _ in range(_SIZE)] for _ in range(_SIZE)]
    players = {}
    for slot, (x, y) in zip(slots, _STARTS):
        players[slot] = {"x": x, "y": y, "alive": True, "trail": []}
        for tx in range(x - 1, x + 2):
            for ty in range(y - 1, y + 2):
                territory[tx][ty] = slot

    def state(tick):
        return {"kind": "territory_capture", "active_slots": slots, "territory": territory,
                "players": players, "width": _SIZE, "height": _SIZE, "max_turns": _MAX_TURNS,
                "turns_left": _MAX_TURNS - tick,
                "areas": {s: sum(column.count(s) for column in territory) for s in slots}}

    frames = [_snapshot(0, state(0), labels)]
    for tick in range(_MAX_TURNS):
        clock["tick"] = tick
        snapshot = state(tick)
        actions = {s: _choose(bots, s, {**snapshot, "tick": tick, "me": s}, events)
                   for s in slots if players[s]["alive"]}
        killed = _step(territory, players, actions)
        for slot in sorted(killed):
            events.append({"type": "eliminated", "tick": tick + 1, "slot": slot})
        frames.append(_snapshot(tick + 1, state(tick + 1), labels))
        if sum(p["alive"] for p in players.values()) <= 1:
            break
    areas = state(frames[-1]["tick"])["areas"]
    return _result(slots, teams, labels, areas, frames, events, errors, areas=areas)


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
