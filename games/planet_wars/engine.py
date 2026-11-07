from __future__ import annotations

import copy
import json
import math
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


GAME_ID = "planet_wars_v1"
_MAX_TURNS = 300
_SPEED = 6


def travel_time(source, target):
    """Number of turns between two planet dictionaries."""
    return max(1, math.ceil(math.hypot(source["x"] - target["x"], source["y"] - target["y"]) / _SPEED))


def _make_planets(slots, rng):
    count = len(slots)
    patterns = [(30, -.28), (30, .28), (17, 0), (40, .58), (40, -.58), (14, 1.2)]
    neutral_count = {2: 6, 3: 4, 4: 3}[count]
    planets = []
    for orbit, (radius, offset) in enumerate([(40, 0), *patterns[:neutral_count]]):
        ships = 45 if orbit == 0 else rng.randint(8, 22)
        production = 3 if orbit == 0 else rng.randint(1, 4)
        for index, slot in enumerate(slots):
            angle = -3 * math.pi / 4 + index * 2 * math.pi / count + offset
            planets.append({"id": len(planets), "x": round(50 + radius * math.cos(angle), 2),
                            "y": round(50 + radius * math.sin(angle), 2),
                            "owner": slot if orbit == 0 else None,
                            "ships": ships, "production": production})
    return planets


def _launch(planets, fleets, actions, tick):
    by_id = {planet["id"]: planet for planet in planets}
    for slot, orders in actions.items():
        if not isinstance(orders, list):
            continue
        used = set()
        for order in orders[:len(planets)]:
            if not isinstance(order, dict):
                continue
            source_id, target_id, ships = order.get("from"), order.get("to"), order.get("ships")
            if not all(type(value) is int for value in (source_id, target_id, ships)):
                continue
            source, target = by_id.get(source_id), by_id.get(target_id)
            if (source is None or target is None or source is target or source_id in used
                    or source["owner"] != slot or not 0 < ships <= source["ships"]):
                continue
            used.add(source_id)
            source["ships"] -= ships
            duration = travel_time(source, target)
            fleets.append({"id": f"{tick}-{slot}-{source_id}", "owner": slot, "from": source_id,
                           "to": target_id, "ships": ships, "eta": duration, "duration": duration})


def _advance(planets, fleets):
    for planet in planets:
        if planet["owner"] is not None:
            planet["ships"] += planet["production"]
    arrivals = {}
    for fleet in fleets:
        fleet["eta"] -= 1
        if fleet["eta"] <= 0:
            forces = arrivals.setdefault(fleet["to"], {})
            forces[fleet["owner"]] = forces.get(fleet["owner"], 0) + fleet["ships"]
    for planet in planets:
        if planet["id"] not in arrivals:
            continue
        forces = arrivals[planet["id"]]
        forces[planet["owner"]] = forces.get(planet["owner"], 0) + planet["ships"]
        total = sum(forces.values())
        winner = next((owner for owner, strength in forces.items() if strength > total - strength), None)
        # A neutral garrison can also be the sole surviving side.
        strength = forces.get(winner, 0)
        planet["owner"] = winner
        planet["ships"] = max(0, 2 * strength - total)
    fleets[:] = [fleet for fleet in fleets if fleet["eta"] > 0]


def _totals(slots, planets, fleets):
    production = {s: sum(p["production"] for p in planets if p["owner"] == s) for s in slots}
    ships = {s: sum(p["ships"] for p in planets if p["owner"] == s)
             + sum(f["ships"] for f in fleets if f["owner"] == s) for s in slots}
    alive = [s for s in slots if any(p["owner"] == s for p in planets) or any(f["owner"] == s for f in fleets)]
    return production, ships, alive


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = _context(context)
    slots, teams, labels, sources, rng = _participants(ctx)
    events, clock = [], {"tick": 0}
    bots, errors = _build_bots(sources, events, clock, {"travel_time": travel_time})
    planets, fleets = _make_planets(slots, rng), []

    def state(tick):
        production, ships, alive = _totals(slots, planets, fleets)
        return {"kind": "planet_wars", "planets": planets, "fleets": fleets,
                "active_slots": slots, "alive": alive, "production": production, "ships": ships,
                "max_turns": _MAX_TURNS, "turns_left": _MAX_TURNS - tick, "speed": _SPEED}

    frames = [_snapshot(0, state(0), labels)]
    for tick in range(_MAX_TURNS):
        clock["tick"] = tick
        snapshot = state(tick)
        actions = {slot: _choose(bots, slot, {**snapshot, "tick": tick, "me": slot}, events)
                   for slot in snapshot["alive"]}
        _launch(planets, fleets, actions, tick)
        _advance(planets, fleets)
        snapshot = state(tick + 1)
        frames.append(_snapshot(tick + 1, snapshot, labels))
        if len(snapshot["alive"]) <= 1:
            break
    production, ships, alive = _totals(slots, planets, fleets)
    scores = {s: production[s] * 100000 + ships[s] for s in slots}
    return _result(slots, teams, labels, scores, frames, events, errors,
                   production=production, ships=ships, alive=alive)


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
