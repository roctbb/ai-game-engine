from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 100
_BATTERY_MAX = 24
_SLOTS = ("solar", "lunar")
_STARTS = {"solar": (1, 1), "lunar": (10, 10)}
_RANDOM_WALLS = 18
_ENERGY_TOTAL = 14
_CHARGERS_TOTAL = 4
_DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "stay": (0, 0)}
_BORDER_WALLS = {
    *{(x, 0) for x in range(_WIDTH)}, *{(x, _HEIGHT - 1) for x in range(_WIDTH)},
    *{(0, y) for y in range(_HEIGHT)}, *{(_WIDTH - 1, y) for y in range(_HEIGHT)},
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    bots = {slot: _build_player_fn(ctx, slot, events, print_context) for slot in _SLOTS}
    game_map = _build_map(ctx)
    walls = game_map["walls"]
    energy = game_map["energy"]
    chargers = game_map["chargers"]
    assert isinstance(walls, set) and isinstance(energy, set) and isinstance(chargers, set)

    positions = dict(_STARTS)
    batteries = {slot: _BATTERY_MAX for slot in _SLOTS}
    collected = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    turns = 0
    frames = [_frame(0, "running", positions, walls, energy, chargers, batteries, collected, invalid)]

    for turn in range(_MAX_TURNS):
        if not energy:
            break
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        for slot in _SLOTS:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            action = _safe_call(fn, x, y, _board(walls, energy, chargers, positions, slot), batteries[slot], slot)
            if action not in _DELTAS or batteries[slot] <= 0:
                invalid[slot] += 1
                action = "stay"
            target = _move((x, y), str(action))
            if target in walls:
                invalid[slot] += 1
                target = (x, y)
            intents[slot] = target

        if intents["solar"] == intents["lunar"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "collision_bounce", "tick": turn + 1})
        elif intents["solar"] == positions["lunar"] and intents["lunar"] == positions["solar"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "swap_blocked", "tick": turn + 1})

        positions = intents
        for slot in _SLOTS:
            if positions[slot] in chargers:
                batteries[slot] = _BATTERY_MAX
                events.append({"type": "charge", "tick": turn + 1, "slot": slot})
            elif batteries[slot] > 0:
                batteries[slot] -= 1
            if positions[slot] in energy:
                energy.remove(positions[slot])
                collected[slot] += 1
                events.append({"type": "energy", "tick": turn + 1, "slot": slot})

        turns = turn + 1
        frames.append(_frame(turns, "running", positions, walls, energy, chargers, batteries, collected, invalid))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: collected[slot] * 100 + batteries[slot] - invalid[slot] * 10 for slot in _SLOTS}
    team_ids = _team_ids(ctx)
    scores = {team_ids[slot]: max(0, slot_scores[slot]) for slot in _SLOTS}
    placements = _placements(team_ids, slot_scores)
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": max(_SLOTS, key=lambda slot: (slot_scores[slot], collected[slot])),
        "winner_slots": _winner_slots(slot_scores),
        "is_tie": _is_tie(slot_scores),
        "collected": collected,
        "energy_total": _ENERGY_TOTAL,
        "energy_left": len(energy),
        "chargers_total": _CHARGERS_TOTAL,
        "batteries": batteries,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})
    frames.append(_frame(len(frames), "finished", positions, walls, energy, chargers, batteries, collected, invalid, slot_scores))
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


def _build_map(context: dict[str, Any]) -> dict[str, object]:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "energy_race_offline"
    rng = random.Random(seed)
    starts = set(_STARTS.values())
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) not in starts]
    for _attempt in range(500):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        shared = sorted((_reachable_cells(_STARTS["solar"], walls) & _reachable_cells(_STARTS["lunar"], walls)) - starts)
        if len(shared) < _ENERGY_TOTAL + _CHARGERS_TOTAL + 8:
            continue
        rng.shuffle(shared)
        return {"walls": walls, "energy": set(shared[:_ENERGY_TOTAL]), "chargers": set(shared[_ENERGY_TOTAL:_ENERGY_TOTAL + _CHARGERS_TOTAL])}
    walls = set(_BORDER_WALLS)
    shared = sorted((_reachable_cells(_STARTS["solar"], walls) & _reachable_cells(_STARTS["lunar"], walls)) - starts)
    rng.shuffle(shared)
    return {"walls": walls, "energy": set(shared[:_ENERGY_TOTAL]), "chargers": set(shared[_ENERGY_TOTAL:_ENERGY_TOTAL + _CHARGERS_TOTAL])}


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], battery: int, slot: str) -> object:
    try:
        return fn(x, y, board, battery, slot)
    except TypeError:
        try:
            return fn(x, y, board, battery)
        except TypeError:
            try:
                return fn(x, y, board)
            except Exception:
                return None
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _battery: int = 0, _slot: str = "") -> str:
    return "stay"


def _board(walls: set[tuple[int, int]], energy: set[tuple[int, int]], chargers: set[tuple[int, int]], positions: dict[str, tuple[int, int]], viewer: str) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in energy:
        board[x][y] = 1
    for x, y in chargers:
        board[x][y] = 2
    opponent = "lunar" if viewer == "solar" else "solar"
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


def _team_ids(ctx: dict[str, Any]) -> dict[str, str]:
    team_id = ctx.get("team_id")
    return {"solar": str(team_id) if isinstance(team_id, str) and team_id else "team-solar", "lunar": "team-lunar"}



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


def _frame(tick: int, phase: str, positions: dict[str, tuple[int, int]], walls: set[tuple[int, int]], energy: set[tuple[int, int]], chargers: set[tuple[int, int]], batteries: dict[str, int], collected: dict[str, int], invalid: dict[str, int], slot_scores: dict[str, int] | None = None) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, energy, chargers, positions, "solar"),
        "boards": {slot: _board(walls, energy, chargers, positions, slot) for slot in _SLOTS},
        "width": _WIDTH,
        "height": _HEIGHT,
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "batteries": batteries,
        "collected": collected,
        "energy_left": len(energy),
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
