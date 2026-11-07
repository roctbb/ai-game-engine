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


GAME_ID = "bomb_arena_v1"
_SIZE = 15
_MAX_TURNS = 180
_FUSE = 5
_SHRINK_START = 100
_SHRINK_INTERVAL = 10
_STARTS = ((1, 1), (13, 13), (13, 1), (1, 13))


def _make_board(rng):
    board = [[0 for _ in range(_SIZE)] for _ in range(_SIZE)]
    hidden = {}
    safe = set()
    for x, y in _STARTS:
        for dx, dy in _DELTAS.values():
            safe.add((x + dx, y + dy))
    for x in range((_SIZE + 1) // 2):
        for y in range((_SIZE + 1) // 2):
            cells = {(x, y), (_SIZE - 1 - x, y), (x, _SIZE - 1 - y), (_SIZE - 1 - x, _SIZE - 1 - y)}
            wall = x == 0 or y == 0 or (x % 2 == 0 and y % 2 == 0)
            crate = not wall and not (cells & safe) and rng.random() < .65
            bonus = rng.choice(("capacity", "range")) if crate and rng.random() < .35 else None
            for cx, cy in cells:
                board[cx][cy] = -1 if wall else 1 if crate else 0
                if bonus:
                    hidden[(cx, cy)] = bonus
    return board, hidden


def _blast(board, bombs, tick):
    """Resolve a whole chain against one immutable obstacle layout."""
    by_cell = {(b["x"], b["y"]): index for index, b in enumerate(bombs)}
    queue = [index for index, bomb in enumerate(bombs) if bomb["explode_at"] <= tick]
    exploded, fire, crates = set(), set(), set()
    head = 0
    while head < len(queue):
        index = queue[head]
        head += 1
        if index in exploded:
            continue
        exploded.add(index)
        bomb = bombs[index]
        fire.add((bomb["x"], bomb["y"]))
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            for distance in range(1, bomb["range"] + 1):
                x, y = bomb["x"] + dx * distance, bomb["y"] + dy * distance
                if not (0 <= x < _SIZE and 0 <= y < _SIZE) or board[x][y] in (-1, -2):
                    break
                fire.add((x, y))
                if board[x][y] == 1:
                    crates.add((x, y))
                    break
                other = by_cell.get((x, y))
                if other is not None and other not in exploded:
                    queue.append(other)
    return fire, crates, exploded


def blast_times(state, all_phases=False):
    """Known explosion ticks, including chains; optionally keep every phase."""
    board, bombs = copy.deepcopy(state["board"]), copy.deepcopy(state["bombs"])
    times = [[[] for _ in range(_SIZE)] for _ in range(_SIZE)]
    for cell in state.get("fire", []):
        times[cell[0]][cell[1]].append(state["tick"])
    schedule = state.get("shrink", {})
    start = schedule.get("start", _SHRINK_START)
    interval = schedule.get("interval", _SHRINK_INTERVAL)
    last_tick = state["tick"]
    while bombs:
        tick = min(b["explode_at"] for b in bombs)
        for shrink_tick in range(last_tick + 1, tick + 1):
            if shrink_tick >= start and (shrink_tick - start) % interval == 0:
                ring = 1 + (shrink_tick - start) // interval
                for x, y in _ring_cells(ring):
                    board[x][y] = -2
        bombs = [b for b in bombs if board[b["x"]][b["y"]] != -2]
        fire, crates, exploded = _blast(board, bombs, tick)
        for x, y in fire:
            times[x][y].append(tick)
        for x, y in crates:
            board[x][y] = 0
        bombs = [b for index, b in enumerate(bombs) if index not in exploded]
        last_tick = tick
    if all_phases:
        return times
    return [[min(values) if values else None for values in column] for column in times]


def _ring_cells(ring):
    return {(x, y) for x in range(_SIZE) for y in range(_SIZE)
            if min(x, y, _SIZE - 1 - x, _SIZE - 1 - y) == ring}


def _step(board, hidden, players, bombs, powerups, actions, tick):
    positions = {s: (p["x"], p["y"]) for s, p in players.items() if p["alive"]}
    occupied = {(b["x"], b["y"]) for b in bombs}
    for slot, (x, y) in positions.items():
        action = actions.get(slot)
        player = players[slot]
        if (isinstance(action, dict) and action.get("bomb") is True and (x, y) not in occupied
                and sum(b["owner"] == slot for b in bombs) < player["capacity"]):
            bombs.append({"owner": slot, "x": x, "y": y, "range": player["range"],
                          "explode_at": tick + _FUSE})
            occupied.add((x, y))
    intents = {}
    for slot, (x, y) in positions.items():
        action = actions.get(slot)
        move = action.get("move", "stay") if isinstance(action, dict) else action
        dx, dy = _DELTAS.get(move, (0, 0)) if isinstance(move, str) else (0, 0)
        target = (x + dx, y + dy)
        valid = (0 <= target[0] < _SIZE and 0 <= target[1] < _SIZE
                 and board[target[0]][target[1]] == 0
                 and (target not in occupied or target == (x, y)))
        intents[slot] = target if valid else (x, y)
    moves = _resolve_moves(positions, intents)
    for slot, (x, y) in moves.items():
        players[slot]["x"], players[slot]["y"] = x, y
        bonus = powerups.pop((x, y), None)
        if bonus:
            players[slot][bonus] += 1
    next_tick = tick + 1
    if next_tick >= _SHRINK_START and (next_tick - _SHRINK_START) % _SHRINK_INTERVAL == 0:
        ring = 1 + (next_tick - _SHRINK_START) // _SHRINK_INTERVAL
        for x, y in _ring_cells(ring):
            board[x][y] = -2
            powerups.pop((x, y), None)
            hidden.pop((x, y), None)
    bombs[:] = [b for b in bombs if board[b["x"]][b["y"]] != -2]
    fire, crates, exploded = _blast(board, bombs, next_tick)
    for cell in fire:
        powerups.pop(cell, None)
    revealed = []
    for x, y in sorted(crates):
        board[x][y] = 0
        bonus = hidden.pop((x, y), None)
        if bonus:
            revealed.append(((x, y), bonus))
    bombs[:] = [b for index, b in enumerate(bombs) if index not in exploded]
    killed = []
    for slot, (x, y) in moves.items():
        if (x, y) in fire or board[x][y] == -2:
            players[slot]["alive"] = False
            players[slot]["eliminated_at"] = next_tick
            killed.append(slot)
    return fire, revealed, killed


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    slots, teams, labels, sources, rng = _participants(_context(context))
    events, clock = [], {"tick": 0}
    bots, errors = _build_bots(sources, events, clock, {"blast_times": blast_times})
    board, hidden = _make_board(rng)
    players = {s: {"x": pos[0], "y": pos[1], "alive": True, "capacity": 1, "range": 2,
                   "eliminated_at": None} for s, pos in zip(slots, _STARTS)}
    bombs, powerups, fire, pending = [], {}, set(), []

    def state(tick):
        return {"kind": "bomb_arena", "active_slots": slots, "board": board, "players": players,
                "bombs": bombs, "fire": [list(cell) for cell in sorted(fire)],
                "powerups": [{"x": x, "y": y, "type": kind} for (x, y), kind in sorted(powerups.items())],
                "shrink": {"start": _SHRINK_START, "interval": _SHRINK_INTERVAL},
                "fuse": _FUSE, "width": _SIZE, "height": _SIZE,
                "max_turns": _MAX_TURNS, "turns_left": _MAX_TURNS - tick}

    frames = [_snapshot(0, state(0), labels)]
    for tick in range(_MAX_TURNS):
        clock["tick"] = tick
        snapshot = state(tick)
        actions = {s: _choose(bots, s, {**snapshot, "tick": tick, "me": s}, events)
                   for s in slots if players[s]["alive"]}
        # Fire lasts for one replay frame. Bonuses appear after that fire disappears.
        powerups.update(pending)
        fire, pending, killed = _step(board, hidden, players, bombs, powerups, actions, tick)
        for slot in killed:
            events.append({"type": "eliminated", "tick": tick + 1, "slot": slot})
        frames.append(_snapshot(tick + 1, state(tick + 1), labels))
        if sum(p["alive"] for p in players.values()) <= 1:
            break
    scores = {s: _MAX_TURNS + 1 if p["alive"] else p["eliminated_at"] for s, p in players.items()}
    return _result(slots, teams, labels, scores, frames, events, errors,
                   alive=[s for s in slots if players[s]["alive"]])


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
