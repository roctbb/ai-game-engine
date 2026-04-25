from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 110
_SLOTS = ("amber", "violet")
_BASES = {"amber": (1, 1), "violet": (10, 10)}
_STARTS = {"amber": (1, 2), "violet": (10, 9)}
_RANDOM_WALLS = 18
_RELICS_TOTAL = 10
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
    bots = {slot: _build_player_fn(ctx, slot, events, print_context) for slot in _SLOTS}
    game_map = _build_map(ctx)
    walls = game_map["walls"]
    relics = game_map["relics"]
    assert isinstance(walls, set) and isinstance(relics, set)

    positions = dict(_STARTS)
    carrying = {slot: False for slot in _SLOTS}
    delivered = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    turns = 0
    frames = [_frame(0, "running", walls, relics, positions, carrying, delivered, invalid)]

    for turn in range(_MAX_TURNS):
        if not relics and not any(carrying.values()):
            break
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        for slot in _SLOTS:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(walls, relics, positions, slot)
            action = _safe_call(fn, x, y, board, carrying[slot], slot)
            if action not in _DELTAS:
                invalid[slot] += 1
                action = "stay"
                events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": slot})
            target = _move((x, y), str(action))
            if target in walls:
                invalid[slot] += 1
                target = (x, y)
                events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "slot": slot})
            intents[slot] = target

        if intents["amber"] == intents["violet"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "collision_bounce", "tick": turn + 1})
        elif intents["amber"] == positions["violet"] and intents["violet"] == positions["amber"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "swap_blocked", "tick": turn + 1})

        positions = intents
        turns = turn + 1
        for slot in _SLOTS:
            if not carrying[slot] and positions[slot] in relics:
                relics.remove(positions[slot])
                carrying[slot] = True
                events.append({"type": "relic_taken", "tick": turns, "slot": slot})
            if carrying[slot] and positions[slot] == _BASES[slot]:
                carrying[slot] = False
                delivered[slot] += 1
                events.append({"type": "delivered", "tick": turns, "slot": slot, "count": delivered[slot]})
        frames.append(_frame(turns, "running", walls, relics, positions, carrying, delivered, invalid))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: delivered[slot] * 150 + (50 if carrying[slot] else 0) - invalid[slot] * 10 for slot in _SLOTS}
    team_ids = _team_ids(ctx)
    scores = {team_ids[slot]: max(0, slot_scores[slot]) for slot in _SLOTS}
    placements = _placements(team_ids, slot_scores)
    winner_slot = max(_SLOTS, key=lambda slot: (slot_scores[slot], delivered[slot]))
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": winner_slot,
        "winner_slots": _winner_slots(slot_scores),
        "is_tie": _is_tie(slot_scores),
        "delivered": delivered,
        "carrying": carrying,
        "relics_left": len(relics),
        "relics_total": _RELICS_TOTAL,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", walls, relics, positions, carrying, delivered, invalid, slot_scores))
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
        seed = "relic_delivery_duel_offline"
    rng = random.Random(seed)
    blocked = set(_STARTS.values()) | set(_BASES.values())
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in blocked
    ]
    for _attempt in range(500):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        shared = sorted((_reachable_cells(_BASES["amber"], walls) & _reachable_cells(_BASES["violet"], walls)) - blocked)
        if len(shared) < _RELICS_TOTAL + 8:
            continue
        rng.shuffle(shared)
        return {"walls": walls, "relics": set(shared[:_RELICS_TOTAL])}
    walls = set(_BORDER_WALLS)
    shared = sorted((_reachable_cells(_BASES["amber"], walls) & _reachable_cells(_BASES["violet"], walls)) - blocked)
    rng.shuffle(shared)
    return {"walls": walls, "relics": set(shared[:_RELICS_TOTAL])}


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], carrying: bool, slot: str) -> object:
    try:
        return fn(x, y, board, carrying, slot)
    except TypeError:
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


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _carrying: bool = False, _slot: str = "") -> str:
    return "stay"


def _board(
    walls: set[tuple[int, int]],
    relics: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    viewer: str,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in relics:
        board[x][y] = 1
    bx, by = _BASES[viewer]
    board[bx][by] = 2
    opponent = "violet" if viewer == "amber" else "amber"
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
    return {
        "amber": str(team_id) if isinstance(team_id, str) and team_id else "team-amber",
        "violet": "team-violet",
    }



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


def _frame(
    tick: int,
    phase: str,
    walls: set[tuple[int, int]],
    relics: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    carrying: dict[str, bool],
    delivered: dict[str, int],
    invalid: dict[str, int],
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, relics, positions, "amber"),
        "boards": {slot: _board(walls, relics, positions, slot) for slot in _SLOTS},
        "width": _WIDTH,
        "height": _HEIGHT,
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "bases": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in _BASES.items()},
        "carrying": carrying,
        "delivered": delivered,
        "relics_left": len(relics),
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
