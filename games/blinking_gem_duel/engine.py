from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 90
_SLOTS = ("sun", "moon")
_STARTS = {"sun": (1, 1), "moon": (10, 10)}
_RANDOM_WALLS = 16
_BRIDGES_TOTAL = 20
_GEMS_TOTAL = 14
_DELTAS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0), "stay": (0, 0)}
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
    bridges = game_map["bridges"]
    gems = game_map["gems"]
    assert isinstance(walls, set) and isinstance(bridges, dict) and isinstance(gems, set)

    positions = dict(_STARTS)
    collected = {slot: 0 for slot in _SLOTS}
    bridge_steps = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    turns = 0
    frames = [_frame(0, "running", positions, walls, bridges, gems, collected, bridge_steps, invalid)]

    for turn in range(_MAX_TURNS):
        if not gems:
            break
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        for slot in _SLOTS:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(walls, bridges, gems, positions, slot, turn)
            action = _safe_call(fn, x, y, board, collected[slot], slot)
            if action not in _DELTAS:
                invalid[slot] += 1
                action = "stay"
                events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": slot})
            target = _move((x, y), str(action))
            blocked = set(positions.values()) | walls
            if not _inside(target) or target in blocked or _closed_bridge(target, bridges, turn):
                invalid[slot] += 1
                target = (x, y)
                events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "slot": slot})
            intents[slot] = target

        if intents["sun"] == intents["moon"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "collision_bounce", "tick": turn + 1})
        elif intents["sun"] == positions["moon"] and intents["moon"] == positions["sun"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "swap_blocked", "tick": turn + 1})

        positions = intents
        for slot in _SLOTS:
            if positions[slot] in bridges:
                bridge_steps[slot] += 1
            if positions[slot] in gems:
                gems.remove(positions[slot])
                collected[slot] += 1
                events.append({"type": "gem", "tick": turn + 1, "slot": slot})
        turns = turn + 1
        frames.append(_frame(turns, "running", positions, walls, bridges, gems, collected, bridge_steps, invalid))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: collected[slot] * 100 + bridge_steps[slot] * 3 - invalid[slot] * 10 for slot in _SLOTS}
    team_ids = _team_ids(ctx)
    scores = {team_ids[slot]: max(0, slot_scores[slot]) for slot in _SLOTS}
    placements = _placements(team_ids, slot_scores)
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": max(_SLOTS, key=lambda slot: (slot_scores[slot], collected[slot])),
        "winner_slots": _winner_slots(slot_scores),
        "is_tie": _is_tie(slot_scores),
        "gems_left": len(gems),
        "gems_total": _GEMS_TOTAL,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "bridges_total": len(bridges),
        "collected": collected,
        "bridge_steps": bridge_steps,
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", positions, walls, bridges, gems, collected, bridge_steps, invalid, slot_scores))
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
        seed = "blinking_gem_duel_offline"
    rng = random.Random(seed)
    starts = set(_STARTS.values())
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) not in starts]
    for _attempt in range(900):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        bridge_cells = [cell for cell in candidates[_RANDOM_WALLS:_RANDOM_WALLS + _BRIDGES_TOTAL] if cell not in walls]
        bridges = {cell: rng.randrange(2) for cell in bridge_cells}
        shared = (
            _reachable_cells(_STARTS["sun"], walls, bridges)
            & _reachable_cells(_STARTS["moon"], walls, bridges)
        ) - starts - set(bridges)
        shared_list = sorted(shared)
        if len(shared_list) < _GEMS_TOTAL + 4:
            continue
        rng.shuffle(shared_list)
        return {"walls": walls, "bridges": bridges, "gems": set(shared_list[:_GEMS_TOTAL])}
    walls = set(_BORDER_WALLS)
    bridges = {(3, 1): 0, (5, 1): 1, (5, 3): 0, (7, 3): 1, (7, 6): 0, (9, 6): 1}
    gems = {(2, 3), (3, 8), (4, 4), (6, 2), (7, 7), (9, 3), (2, 9), (9, 8), (6, 9), (3, 5), (8, 2), (5, 7), (7, 4), (4, 9)}
    return {"walls": walls, "bridges": bridges, "gems": gems}


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


def _board(
    walls: set[tuple[int, int]],
    bridges: dict[tuple[int, int], int],
    gems: set[tuple[int, int]],
    positions: dict[str, tuple[int, int]],
    viewer: str,
    tick: int,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for (x, y), phase in bridges.items():
        board[x][y] = 2 if _bridge_open(phase, tick) else -2
    for x, y in gems:
        board[x][y] = 1
    opponent = "moon" if viewer == "sun" else "sun"
    ox, oy = positions[opponent]
    board[ox][oy] = -3
    return board


def _bridge_open(phase: int, tick: int) -> bool:
    return (phase + tick) % 2 == 0


def _closed_bridge(position: tuple[int, int], bridges: dict[tuple[int, int], int], tick: int) -> bool:
    phase = bridges.get(position)
    return phase is not None and not _bridge_open(phase, tick)


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]], bridges: dict[tuple[int, int], int]) -> set[tuple[int, int]]:
    queue = [(start, 0)]
    seen = {(start, 0)}
    cells = {start}
    head = 0
    while head < len(queue):
        current, parity = queue[head]
        head += 1
        for action in ("up", "right", "down", "left", "stay"):
            nxt = _move(current, action)
            if not _inside(nxt) or nxt in walls or _closed_bridge(nxt, bridges, parity):
                continue
            state = (nxt, 1 - parity)
            if state in seen:
                continue
            seen.add(state)
            cells.add(nxt)
            queue.append(state)
    return cells


def _team_ids(ctx: dict[str, Any]) -> dict[str, str]:
    team_id = ctx.get("team_id")
    return {"sun": str(team_id) if isinstance(team_id, str) and team_id else "team-sun", "moon": "team-moon"}



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
    positions: dict[str, tuple[int, int]],
    walls: set[tuple[int, int]],
    bridges: dict[tuple[int, int], int],
    gems: set[tuple[int, int]],
    collected: dict[str, int],
    bridge_steps: dict[str, int],
    invalid: dict[str, int],
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, bridges, gems, positions, "sun", tick),
        "boards": {slot: _board(walls, bridges, gems, positions, slot, tick) for slot in _SLOTS},
        "width": _WIDTH,
        "height": _HEIGHT,
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "collected": collected,
        "gems_left": len(gems),
        "bridge_steps": bridge_steps,
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
