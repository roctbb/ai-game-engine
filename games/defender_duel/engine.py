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


GAME_ID = "defender_duel_v1"
_MAX_TURNS = 300
_PATH = [(0, 2), (3, 2), (3, 6), (8, 6), (8, 2), (12, 2)]
_PADS = [(2, 3), (4, 3), (2, 5), (4, 5), (6, 5), (7, 3), (9, 3), (10, 1)]
_TOWERS = {
    "arrow": {"cost": 30, "damage": 6, "range": 3.2},
    "blast": {"cost": 45, "damage": 4, "range": 2.8, "splash": 1.4},
    "slow": {"cost": 35, "damage": 1, "range": 3.0},
}
_UNITS = {
    "scout": {"cost": 16, "count": 2, "hp": 9, "speed": 1.1, "armor": 0, "damage": 1},
    "swarm": {"cost": 26, "count": 6, "hp": 5, "speed": .7, "armor": 0, "damage": 1},
    "armored": {"cost": 42, "count": 1, "hp": 65, "speed": .45, "armor": 2, "damage": 5},
}
_PATH_LENGTH = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(_PATH, _PATH[1:]))


def _point(distance):
    for start, end in zip(_PATH, _PATH[1:]):
        length = abs(end[0] - start[0]) + abs(end[1] - start[1])
        if distance <= length:
            return (start[0] + (end[0] - start[0]) * distance / length,
                    start[1] + (end[1] - start[1]) * distance / length)
        distance -= length
    return _PATH[-1]


def _buy(player, action, target, enemies):
    if not isinstance(action, dict):
        return
    kind = action.get("action")
    if kind == "build":
        pad, name = action.get("pad"), action.get("tower")
        if type(pad) is not int or not isinstance(name, str) or name not in _TOWERS:
            return
        cost = _TOWERS[name]["cost"]
        if (0 <= pad < len(_PADS) and all(t["pad"] != pad for t in player["towers"])
                and player["money"] >= cost):
            player["money"] -= cost
            player["towers"].append({"pad": pad, "type": name, "level": 1})
    elif kind == "upgrade":
        pad = action.get("pad")
        tower = next((t for t in player["towers"] if t["pad"] == pad), None)
        if tower and tower["level"] < 3:
            cost = _TOWERS[tower["type"]]["cost"] * tower["level"]
            if player["money"] >= cost:
                player["money"] -= cost
                tower["level"] += 1
    elif kind == "income":
        cost = 40 + player["income_upgrades"] * 20
        if player["money"] >= cost:
            player["money"] -= cost
            player["income"] += 4
            player["income_upgrades"] += 1
    elif kind == "send":
        name = action.get("unit")
        if isinstance(name, str) and name in _UNITS and player["money"] >= _UNITS[name]["cost"]:
            player["money"] -= _UNITS[name]["cost"]
            _spawn(enemies, target, name)


def _spawn(enemies, target, name, wave=0):
    unit = _UNITS[name]
    for index in range(unit["count"]):
        enemies.append({"target": target, "type": name, "hp": unit["hp"] + wave * 3,
                        "max_hp": unit["hp"] + wave * 3, "distance": -index * .65,
                        "speed": unit["speed"], "armor": unit["armor"], "damage": unit["damage"]})


def _fight(players, enemies):
    slowed = set()
    for slot, player in players.items():
        for tower in sorted(player["towers"], key=lambda t: t["pad"]):
            config = _TOWERS[tower["type"]]
            px, py = _PADS[tower["pad"]]
            candidates = [e for e in enemies if e["target"] == slot and e["hp"] > 0 and e["distance"] >= 0
                          and math.dist((px, py), _point(e["distance"])) <= config["range"]]
            if not candidates:
                continue
            target = max(candidates, key=lambda e: e["distance"])
            affected = [target]
            if tower["type"] == "blast":
                affected = [e for e in enemies if e["target"] == slot and e["hp"] > 0 and e["distance"] >= 0
                            and math.dist(_point(e["distance"]), _point(target["distance"])) <= config["splash"]]
            for enemy in affected:
                enemy["hp"] -= max(1, config["damage"] * tower["level"] - enemy["armor"])
                if tower["type"] == "slow":
                    slowed.add(id(enemy))
    remaining = []
    for enemy in enemies:
        if enemy["hp"] <= 0:
            continue
        enemy["distance"] += enemy["speed"] * (.45 if id(enemy) in slowed else 1)
        if enemy["distance"] >= _PATH_LENGTH:
            players[enemy["target"]]["hp"] = max(0, players[enemy["target"]]["hp"] - enemy["damage"])
        else:
            remaining.append(enemy)
    enemies[:] = remaining


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    slots, teams, labels, sources, _rng = _participants(_context(context), maximum=2)
    events, clock = [], {"tick": 0}
    bots, errors = _build_bots(sources, events, clock)
    players = {slot: {"hp": 50, "money": 70, "income": 12, "income_upgrades": 0, "towers": []} for slot in slots}
    enemies = []

    def state(tick):
        return {"kind": "defender_duel", "active_slots": slots, "players": players, "enemies": enemies,
                "path": _PATH, "pads": _PADS, "tower_types": _TOWERS, "unit_types": _UNITS,
                "next_wave": (tick // 20 + 1) * 20, "wave_interval": 20,
                "next_wave_type": "armored" if (tick // 20 + 1) % 3 == 0 else "swarm",
                "income_interval": 5, "max_turns": _MAX_TURNS, "turns_left": _MAX_TURNS - tick}

    frames = [_snapshot(0, state(0), labels)]
    for tick in range(_MAX_TURNS):
        clock["tick"] = tick
        snapshot = state(tick)
        actions = {s: _choose(bots, s, {**snapshot, "tick": tick, "me": s}, events) for s in slots}
        for index, slot in enumerate(slots):
            _buy(players[slot], actions[slot], slots[1 - index], enemies)
        next_tick = tick + 1
        if next_tick % 5 == 0:
            for player in players.values():
                player["money"] += player["income"]
        if next_tick % 20 == 0:
            wave = next_tick // 20
            for slot in slots:
                _spawn(enemies, slot, "armored" if wave % 3 == 0 else "swarm", wave)
        _fight(players, enemies)
        frames.append(_snapshot(next_tick, state(next_tick), labels))
        if any(player["hp"] <= 0 for player in players.values()):
            break
    scores = {s: players[s]["hp"] for s in slots}
    return _result(slots, teams, labels, scores, frames, events, errors,
                   base_hp=scores, money={s: players[s]["money"] for s in slots})


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
