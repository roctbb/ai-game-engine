from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 11
_HEIGHT = 11
_MAX_TURNS = 95
_SLOTS = ("red", "blue")
_STARTS = {"red": (2, 10), "blue": (8, 10)}
_LANES = tuple(range(1, 10))
_CARS_PER_LANE = 2
_STARS_TOTAL = 14
_DELTAS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0), "stay": (0, 0)}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    role_code, role_team, role_name = _resolve_participants(ctx)
    bots = {role: _build_fn(role_code.get(role, ''), role, events, print_context) for role in _SLOTS}
    cars, stars = _build_map(ctx)
    positions = dict(_STARTS)
    collected = {slot: 0 for slot in _SLOTS}
    car_hits = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    turns = 0
    frames = [_frame(0, "running", positions, cars, stars, collected, car_hits, invalid)]

    for turn in range(_MAX_TURNS):
        if not stars:
            break
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        for slot in _SLOTS:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(cars, stars, positions, slot)
            action = _safe_call(fn, x, y, board, collected[slot], slot)
            if action not in _DELTAS:
                invalid[slot] += 1
                action = "stay"
                events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": slot})
            target = _move((x, y), str(action))
            blocked = set(positions.values()) | cars
            if not _inside(target) or target in blocked:
                invalid[slot] += 1
                target = (x, y)
                events.append({"type": "blocked_step", "tick": turn, "slot": slot})
            intents[slot] = target

        if intents["red"] == intents["blue"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "collision_bounce", "tick": turn + 1})
        elif intents["red"] == positions["blue"] and intents["blue"] == positions["red"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "swap_blocked", "tick": turn + 1})

        cars = _advance_cars(cars)
        positions = intents
        for slot in _SLOTS:
            if positions[slot] in cars:
                car_hits[slot] += 1
                positions[slot] = _STARTS[slot]
                events.append({"type": "car_hit", "tick": turn + 1, "slot": slot})
            if positions[slot] in stars:
                stars.remove(positions[slot])
                collected[slot] += 1
                events.append({"type": "star", "tick": turn + 1, "slot": slot})
        turns = turn + 1
        frames.append(_frame(turns, "running", positions, cars, stars, collected, car_hits, invalid))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: collected[slot] * 100 - car_hits[slot] * 35 - invalid[slot] * 8 for slot in _SLOTS}
    scores = {role_team[slot]: max(0, slot_scores[slot]) for slot in _SLOTS}
    placements = _placements(role_team, slot_scores)
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": max(_SLOTS, key=lambda slot: (slot_scores[slot], collected[slot])),
        "winner_slots": _winner_slots(slot_scores),
        "is_tie": _is_tie(slot_scores),
        "stars_left": len(stars),
        "stars_total": _STARS_TOTAL,
        "cars_total": len(cars),
        "collected": collected,
        "car_hits": car_hits,
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", positions, cars, stars, collected, car_hits, invalid, slot_scores))
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

def _build_map(context: dict[str, Any]) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    seed = _map_seed(context, "road_star_duel_offline")
    rng = random.Random(seed)
    cars: set[tuple[int, int]] = set()
    for y in _LANES:
        start = rng.randrange(_WIDTH)
        gap = rng.randrange(4, 7)
        for index in range(_CARS_PER_LANE):
            cars.add(((start + index * gap) % _WIDTH, y))
    candidates = [(x, y) for y in range(1, 10) for x in range(_WIDTH) if (x, y) not in cars]
    rng.shuffle(candidates)
    return cars, set(candidates[:_STARS_TOTAL])


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
        "float": float, "frozenset": frozenset, "int": int, "len": len, "list": list, "max": max, "min": min,
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
    return "up"


def _board(cars: set[tuple[int, int]], stars: set[tuple[int, int]], positions: dict[str, tuple[int, int]], viewer: str) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in stars:
        board[x][y] = 1
    for x, y in cars:
        board[x][y] = -1
    opponent = "blue" if viewer == "red" else "red"
    ox, oy = positions[opponent]
    board[ox][oy] = -2
    return board


def _advance_cars(cars: set[tuple[int, int]]) -> set[tuple[int, int]]:
    moved = set()
    for x, y in cars:
        dx = 1 if y % 2 == 1 else -1
        moved.add(((x + dx) % _WIDTH, y))
    return moved


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT




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
    cars: set[tuple[int, int]],
    stars: set[tuple[int, int]],
    collected: dict[str, int],
    car_hits: dict[str, int],
    invalid: dict[str, int],
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(cars, stars, positions, "red"),
        "boards": {slot: _board(cars, stars, positions, slot) for slot in _SLOTS},
        "width": _WIDTH,
        "height": _HEIGHT,
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "collected": collected,
        "stars_left": len(stars),
        "car_hits": car_hits,
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
