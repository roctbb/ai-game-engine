from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 100
_SLOTS = ("gold", "silver")
_STARTS = {"gold": (1, 1), "silver": (10, 10)}
_RANDOM_WALLS = 18
_COINS_TOTAL = 16
_TRAPS_TOTAL = 8
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
    role_code, role_team, role_name = _resolve_participants(ctx)
    bots = {role: _build_fn(role_code.get(role, ''), role, events, print_context) for role in _SLOTS}
    game_map = _build_map(ctx)
    walls = game_map["walls"]
    coins = game_map["coins"]
    traps = game_map["traps"]
    assert isinstance(walls, set) and isinstance(coins, set) and isinstance(traps, list)

    positions = dict(_STARTS)
    collected = {slot: 0 for slot in _SLOTS}
    trap_hits = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    turns = 0
    frames = [_frame(0, "running", positions, walls, coins, traps, collected, trap_hits, invalid, [], labels=role_name)]

    for turn in range(_MAX_TURNS):
        if not coins:
            break
        print_context["tick"] = turn
        intents: dict[str, tuple[int, int]] = {}
        for slot in _SLOTS:
            fn, _compile_error = bots[slot]
            x, y = positions[slot]
            board = _board(walls, coins, traps, positions, slot)
            action = _safe_call(fn, x, y, board, slot)
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

        if intents["gold"] == intents["silver"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "collision_bounce", "tick": turn + 1})
        elif intents["gold"] == positions["silver"] and intents["silver"] == positions["gold"]:
            intents = {slot: positions[slot] for slot in _SLOTS}
            events.append({"type": "swap_blocked", "tick": turn + 1})

        positions = intents
        for slot in _SLOTS:
            if positions[slot] in coins:
                coins.remove(positions[slot])
                collected[slot] += 1
                events.append({"type": "coin", "tick": turn + 1, "slot": slot})
            if positions[slot] in _trap_cells(traps):
                trap_hits[slot] += 1
                events.append({"type": "trap", "tick": turn + 1, "slot": slot, "phase": "before_traps_move"})
        trap_moves = _move_traps(traps, walls)
        trap_cells = _trap_cells(traps)
        for slot in _SLOTS:
            if positions[slot] in trap_cells:
                trap_hits[slot] += 1
                events.append({"type": "trap", "tick": turn + 1, "slot": slot, "phase": "after_traps_move"})
        turns = turn + 1
        frames.append(_frame(turns, "running", positions, walls, coins, traps, collected, trap_hits, invalid, trap_moves, labels=role_name))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    slot_scores = {slot: collected[slot] * 100 - trap_hits[slot] * 35 - invalid[slot] * 10 for slot in _SLOTS}
    scores = {role_team[slot]: max(0, slot_scores[slot]) for slot in _SLOTS}
    placements = _placements(role_team, slot_scores)
    winner_slot = max(_SLOTS, key=lambda slot: (slot_scores[slot], collected[slot]))
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": winner_slot,
        "winner_slots": _winner_slots(slot_scores),
        "is_tie": _is_tie(slot_scores),
        "coins_left": len(coins),
        "coins_total": _COINS_TOTAL,
        "traps_total": _TRAPS_TOTAL,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "collected": collected,
        "trap_hits": trap_hits,
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", positions, walls, coins, traps, collected, trap_hits, invalid, [], slot_scores, labels=role_name))
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
    seed = _map_seed(context, "trap_coin_duel_offline")
    rng = random.Random(seed)
    starts = set(_STARTS.values())
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in starts
    ]
    for _attempt in range(500):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        shared = sorted((_reachable_cells(_STARTS["gold"], walls) & _reachable_cells(_STARTS["silver"], walls)) - starts)
        if len(shared) < _COINS_TOTAL + _TRAPS_TOTAL + 8:
            continue
        rng.shuffle(shared)
        coins = set(shared[:_COINS_TOTAL])
        traps = _make_traps(shared[_COINS_TOTAL:_COINS_TOTAL + _TRAPS_TOTAL], walls, rng)
        return {"walls": walls, "coins": coins, "traps": traps}
    walls = set(_BORDER_WALLS)
    shared = sorted((_reachable_cells(_STARTS["gold"], walls) & _reachable_cells(_STARTS["silver"], walls)) - starts)
    rng.shuffle(shared)
    return {"walls": walls, "coins": set(shared[:_COINS_TOTAL]), "traps": _make_traps(shared[_COINS_TOTAL:_COINS_TOTAL + _TRAPS_TOTAL], walls, rng)}


def _make_traps(cells: list[tuple[int, int]], walls: set[tuple[int, int]], rng: random.Random) -> list[dict[str, int]]:
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    traps: list[dict[str, int]] = []
    occupied: set[tuple[int, int]] = set()
    for x, y in cells:
        rng.shuffle(directions)
        dx, dy = directions[0]
        for cand_dx, cand_dy in directions:
            if (x + cand_dx, y + cand_dy) not in walls:
                dx, dy = cand_dx, cand_dy
                break
        if (x, y) in occupied:
            continue
        occupied.add((x, y))
        traps.append({"x": x, "y": y, "dx": dx, "dy": dy})
    return traps


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


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], slot: str) -> object:
    try:
        return fn(x, y, board, slot)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _slot: str = "") -> str:
    return "stay"


def _board(
    walls: set[tuple[int, int]],
    coins: set[tuple[int, int]],
    traps: list[dict[str, int]],
    positions: dict[str, tuple[int, int]],
    viewer: str,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in _next_trap_cells(traps, walls):
        if board[x][y] == 0:
            board[x][y] = -4
    for x, y in _trap_cells(traps):
        board[x][y] = -3
    for x, y in coins:
        if board[x][y] == 0:
            board[x][y] = 1
    opponent = "silver" if viewer == "gold" else "gold"
    ox, oy = positions[opponent]
    board[ox][oy] = -2
    return board


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _trap_cells(traps: list[dict[str, int]]) -> set[tuple[int, int]]:
    return {(int(trap["x"]), int(trap["y"])) for trap in traps}


def _next_trap_cell(trap: dict[str, int], walls: set[tuple[int, int]]) -> tuple[int, int]:
    x, y = int(trap["x"]), int(trap["y"])
    dx, dy = int(trap["dx"]), int(trap["dy"])
    target = (x + dx, y + dy)
    if target in walls:
        target = (x - dx, y - dy)
        if target in walls:
            target = (x, y)
    return target


def _next_trap_cells(traps: list[dict[str, int]], walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return {_next_trap_cell(trap, walls) for trap in traps}


def _move_traps(traps: list[dict[str, int]], walls: set[tuple[int, int]]) -> list[dict[str, object]]:
    occupied = _trap_cells(traps)
    moves: list[dict[str, object]] = []
    for trap in traps:
        x, y = int(trap["x"]), int(trap["y"])
        old_dx, old_dy = int(trap["dx"]), int(trap["dy"])
        dx, dy = old_dx, old_dy
        target = (x + dx, y + dy)
        bounced = False
        if target in walls or target in occupied:
            dx, dy = -dx, -dy
            target = (x + dx, y + dy)
            bounced = True
        if target in walls or target in occupied:
            target = (x, y)
            dx, dy = old_dx, old_dy
        occupied.discard((x, y))
        occupied.add(target)
        trap["x"], trap["y"], trap["dx"], trap["dy"] = target[0], target[1], dx, dy
        moves.append(
            {
                "from": {"x": x, "y": y},
                "to": {"x": target[0], "y": target[1]},
                "dx": dx,
                "dy": dy,
                "bounced": bounced,
            }
        )
    return moves


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
    coins: set[tuple[int, int]],
    traps: list[dict[str, int]],
    collected: dict[str, int],
    trap_hits: dict[str, int],
    invalid: dict[str, int],
    trap_moves: list[dict[str, object]],
    slot_scores: dict[str, int] | None = None,
    labels: dict[str, str] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, coins, traps, positions, "gold"),
        "boards": {slot: _board(walls, coins, traps, positions, slot) for slot in _SLOTS},
        "width": _WIDTH,
        "height": _HEIGHT,
        "labels": {slot: (labels or {}).get(slot, slot) for slot in _SLOTS},
        "positions": {slot: {"x": pos[0], "y": pos[1]} for slot, pos in positions.items()},
        "traps": [{"x": int(trap["x"]), "y": int(trap["y"]), "dx": int(trap["dx"]), "dy": int(trap["dy"])} for trap in traps],
        "next_traps": [{"x": x, "y": y} for x, y in sorted(_next_trap_cells(traps, walls))],
        "trap_moves": trap_moves,
        "coins_left": len(coins),
        "collected": collected,
        "trap_hits": trap_hits,
        "invalid_moves": invalid,
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
