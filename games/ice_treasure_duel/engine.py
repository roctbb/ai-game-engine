from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 80
_SLOTS = ("ruby", "sapphire")
_STARTS = {"ruby": (1, 1), "sapphire": (10, 10)}
_RANDOM_WALLS = 24
_CRYSTALS_TOTAL = 12
_DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "stay": (0, 0)}
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
    crystals = game_map["crystals"]
    assert isinstance(walls, set) and isinstance(crystals, set)

    positions = dict(_STARTS)
    collected = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    turns = 0
    frames = [_frame(0, "running", positions, walls, crystals, collected, invalid, labels=role_name)]

    for turn in range(_MAX_TURNS):
        if not crystals:
            break
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        for slot in _SLOTS:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(walls, crystals, positions, slot)
            action = _safe_call(fn, x, y, board, collected[slot], slot)
            if action not in _DELTAS:
                invalid[slot] += 1
                action = "stay"
                events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": slot})
            intents[slot] = _slide((x, y), str(action), walls, set(positions.values()) - {positions[slot]})

        if intents["ruby"] == intents["sapphire"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "collision_bounce", "tick": turn + 1})
        positions = intents

        for slot in _SLOTS:
            if positions[slot] in crystals:
                crystals.remove(positions[slot])
                collected[slot] += 1
                events.append({"type": "crystal", "tick": turn + 1, "slot": slot})
        turns = turn + 1
        frames.append(_frame(turns, "running", positions, walls, crystals, collected, invalid, labels=role_name))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: collected[slot] * 100 - invalid[slot] * 10 for slot in _SLOTS}
    scores = {role_team[slot]: max(0, slot_scores[slot]) for slot in _SLOTS}
    placements = _placements(role_team, slot_scores)
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": max(_SLOTS, key=lambda slot: (slot_scores[slot], collected[slot])),
        "winner_slots": _winner_slots(slot_scores),
        "is_tie": _is_tie(slot_scores),
        "crystals_left": len(crystals),
        "crystals_total": _CRYSTALS_TOTAL,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "collected": collected,
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", positions, walls, crystals, collected, invalid, slot_scores, labels=role_name))
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
        role_code = {r: str(codes.get(r) or codes.get('player') or '') for r in _SLOTS}
        role_team = {r: f'team-{r}' for r in _SLOTS}
        return role_code, role_team, dict(role_team)
    role_team = {r: f'team-{r}' for r in _SLOTS}
    return {r: '' for r in _SLOTS}, role_team, dict(role_team)



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
    seed = _map_seed(context, "ice_treasure_duel_offline")
    rng = random.Random(seed)
    starts = set(_STARTS.values())
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) not in starts]
    for _attempt in range(700):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        ruby_reachable = _slide_reachable(_STARTS["ruby"], walls)
        sapphire_reachable = _slide_reachable(_STARTS["sapphire"], walls)
        shared = sorted((ruby_reachable | sapphire_reachable) - starts - walls)
        if len(shared) < _CRYSTALS_TOTAL + 6:
            continue
        rng.shuffle(shared)
        return {"walls": walls, "crystals": set(shared[:_CRYSTALS_TOTAL])}
    walls = set(_BORDER_WALLS) | {(5, y) for y in range(2, 10)} | {(x, 6) for x in range(2, 10)}
    crystals = {(1, 5), (4, 1), (4, 5), (6, 2), (10, 6), (6, 10), (8, 8), (2, 8), (8, 2), (10, 3), (3, 10), (6, 6)}
    return {"walls": walls - crystals - starts, "crystals": crystals}


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


def _board(walls: set[tuple[int, int]], crystals: set[tuple[int, int]], positions: dict[str, tuple[int, int]], viewer: str) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in crystals:
        board[x][y] = 1
    opponent = "sapphire" if viewer == "ruby" else "ruby"
    ox, oy = positions[opponent]
    board[ox][oy] = -2
    return board


def _slide(position: tuple[int, int], action: str, walls: set[tuple[int, int]], blockers: set[tuple[int, int]] | None = None) -> tuple[int, int]:
    if action == "stay":
        return position
    blockers = blockers or set()
    dx, dy = _DELTAS[action]
    x, y = position
    while True:
        nxt = (x + dx, y + dy)
        if nxt in walls or nxt in blockers:
            return (x, y)
        x, y = nxt


def _slide_reachable(start: tuple[int, int], walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "down", "left", "right"):
            nxt = _slide(current, action, walls)
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
    crystals: set[tuple[int, int]],
    collected: dict[str, int],
    invalid: dict[str, int],
    slot_scores: dict[str, int] | None = None,
    labels: dict[str, str] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, crystals, positions, "ruby"),
        "boards": {slot: _board(walls, crystals, positions, slot) for slot in _SLOTS},
        "width": _WIDTH,
        "height": _HEIGHT,
        "labels": {slot: (labels or {}).get(slot, slot) for slot in _SLOTS},
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "collected": collected,
        "crystals_left": len(crystals),
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
