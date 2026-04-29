from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 26
_HEIGHT = 26
_MAX_TURNS = 400
_TOTAL_AREA_LIMIT = 220
_ROLES = ("snake_1", "snake_2", "snake_3", "snake_4")
_DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
_OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
_HOLES = {
    "snake_1": {"x": 1, "y": 1, "direction": "right"},
    "snake_2": {"x": _WIDTH - 2, "y": 1, "direction": "left"},
    "snake_3": {"x": 1, "y": _HEIGHT - 2, "direction": "right"},
    "snake_4": {"x": _WIDTH - 2, "y": _HEIGHT - 2, "direction": "left"},
}
_STARTS = {
    "snake_1": [(2, 1), (1, 1)],
    "snake_2": [(_WIDTH - 3, 1), (_WIDTH - 2, 1)],
    "snake_3": [(2, _HEIGHT - 2), (1, _HEIGHT - 2)],
    "snake_4": [(_WIDTH - 3, _HEIGHT - 2), (_WIDTH - 2, _HEIGHT - 2)],
}
_INIT_DIR = {role: str(hole["direction"]) for role, hole in _HOLES.items()}
_INITIAL_FOOD = 8
_MIN_FOOD = 8
_MAX_FOOD = 36
_MAX_DROPPED_FOOD = 18
_RESPAWN_DELAY = 1


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}

    role_code, role_team, role_name = _resolve_participants(ctx)
    bots = {role: _build_fn(role_code.get(role, ""), role, events, print_context) for role in _ROLES}

    rng = _rng(ctx)
    snakes = {role: body[:] for role, body in _STARTS.items()}
    alive = {role: True for role in _ROLES}
    respawn_in = {role: 0 for role in _ROLES}
    eaten = {role: 0 for role in _ROLES}
    deaths = {role: 0 for role in _ROLES}
    respawns = {role: 0 for role in _ROLES}
    max_length = {role: len(_STARTS[role]) for role in _ROLES}
    invalid = {role: 0 for role in _ROLES}
    directions = dict(_INIT_DIR)
    foods: set[tuple[int, int]] = set()
    _ensure_food(rng, foods, snakes, alive, _INITIAL_FOOD)

    turns = 0
    frames = [_frame(0, "running", snakes, alive, eaten, invalid, foods, directions, role_team, role_name, deaths, respawn_in)]

    finish_reason = "turn_limit"
    for turn in range(_MAX_TURNS):
        print_context["tick"] = turn
        spawn_events = _try_respawns(rng, snakes, alive, respawn_in, directions, respawns, foods)
        for event in spawn_events:
            events.append({"type": "respawn", "tick": turn, **event})

        if _total_area(snakes, alive) >= _TOTAL_AREA_LIMIT:
            finish_reason = "area_limit"
            break

        board = _board(snakes, alive, foods)
        intents: dict[str, tuple[int, int]] = {}
        grows_by_role: dict[str, bool] = {}
        for role in _ROLES:
            if not alive[role]:
                continue
            fn, _ = bots[role]
            x, y = snakes[role][0]
            action = _safe_call(fn, x, y, _copy_grid(board), role)
            if action not in _DELTAS:
                invalid[role] += 1
                action = directions[role]
                events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": role})
            if len(snakes[role]) > 1 and action == _OPPOSITE[directions[role]]:
                invalid[role] += 1
                action = directions[role]
                events.append({"type": "reverse_blocked", "message": "Змейка не может развернуться в собственную шею.", "tick": turn, "slot": role})
            directions[role] = str(action)
            dx, dy = _DELTAS[str(action)]
            target = (x + dx, y + dy)
            intents[role] = target
            grows_by_role[role] = target in foods

        occupied_now = _occupied(snakes, alive)
        vacated_tails = {snakes[role][-1] for role in _ROLES if alive[role] and not grows_by_role.get(role, False)}
        occupied_after_tails = occupied_now - vacated_tails
        target_counts: dict[tuple[int, int], int] = {}
        for target in intents.values():
            target_counts[target] = target_counts.get(target, 0) + 1

        crashed: set[str] = set()
        for role, target in intents.items():
            if not _inside(target) or target in occupied_after_tails or target_counts[target] > 1:
                crashed.add(role)
        for role, target in intents.items():
            head = snakes[role][0]
            for other, other_target in intents.items():
                if role < other and target == snakes[other][0] and other_target == head:
                    crashed.add(role)
                    crashed.add(other)

        death_events: list[dict[str, object]] = []
        dropped_food: list[dict[str, int | str]] = []
        for role in sorted(crashed):
            alive[role] = False
            deaths[role] += 1
            respawn_in[role] = _RESPAWN_DELAY
            drops = _drop_food(rng, foods, snakes[role], occupied_now - set(snakes[role]))
            dropped_food.extend({"slot": role, "x": x, "y": y} for x, y in drops)
            death_events.append({"slot": role, "body": _points(snakes[role]), "dropped_food": _points(drops)})
            events.append({"type": "crash", "message": "Столкновение: змейка погибла, но матч продолжается.", "tick": turn + 1, "slot": role, "drops": len(drops)})

        claimed_food: set[tuple[int, int]] = set()
        for role, target in intents.items():
            if not alive[role]:
                continue
            grows = target in foods and target not in claimed_food
            snakes[role].insert(0, target)
            if grows:
                eaten[role] += 1
                claimed_food.add(target)
                events.append({"type": "food", "tick": turn + 1, "slot": role, "x": target[0], "y": target[1]})
            else:
                snakes[role].pop()
            max_length[role] = max(max_length[role], len(snakes[role]))
        foods.difference_update(claimed_food)
        _ensure_food(rng, foods, snakes, alive, _MIN_FOOD)

        turns = turn + 1
        frames.append(_frame(turns, "running", snakes, alive, eaten, invalid, foods, directions, role_team, role_name, deaths, respawn_in, death_events=death_events, dropped_food=dropped_food))
    else:
        finish_reason = "turn_limit"

    role_scores = {
        role: eaten[role] * 100 + len(snakes[role]) * 5 + max_length[role] * 3 - deaths[role] * 25 - invalid[role] * 10
        for role in _ROLES
    }
    scores = {role_team[role]: max(0, role_scores[role]) for role in _ROLES}
    placements = _placements(role_team, role_scores)
    best_score = max(role_scores.values())
    winner_roles = [role for role in _ROLES if role_scores[role] == best_score]
    winner_role = winner_roles[0]
    compile_errors = {role: err for role, (_fn, err) in bots.items() if err}
    metrics: dict[str, object] = {
        "turns": turns,
        "max_turns": _MAX_TURNS,
        "finish_reason": finish_reason,
        "area_limit": _TOTAL_AREA_LIMIT,
        "total_area": _total_area(snakes, alive),
        "winner_slot": winner_role,
        "winner_slots": winner_roles,
        "is_tie": len(winner_roles) > 1,
        "food_eaten": eaten,
        "deaths": deaths,
        "respawns": respawns,
        "alive": alive,
        "invalid_moves": invalid,
        "slot_scores": role_scores,
        "score": max(0, sum(role_scores.values())),
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for role, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": role, "message": message})

    frames.append(_frame(len(frames), "finished", snakes, alive, eaten, invalid, foods, directions, role_team, role_name, deaths, respawn_in, role_scores, finish_reason=finish_reason))
    return {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "scores": scores, "placements": placements}


def _resolve_participants(ctx: dict[str, Any]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    participants = ctx.get("participants")
    if isinstance(participants, list) and participants:
        role_code: dict[str, str] = {}
        role_team: dict[str, str] = {}
        role_name: dict[str, str] = {}
        for i, role in enumerate(_ROLES):
            p = participants[i] if i < len(participants) and isinstance(participants[i], dict) else {}
            codes = p.get("codes_by_slot") if isinstance(p, dict) else {}
            code = codes.get("player", "") if isinstance(codes, dict) else ""
            role_code[role] = str(code) if code else ""
            tid = str(p.get("team_id", role)) if isinstance(p, dict) else role
            role_team[role] = tid
            name = p.get("display_name") or p.get("captain_user_id") if isinstance(p, dict) else None
            role_name[role] = str(name) if name else tid
        return role_code, role_team, role_name

    codes = ctx.get("codes_by_slot")
    if isinstance(codes, dict):
        code = str(codes.get("player", ""))
        return {r: code for r in _ROLES}, {r: r for r in _ROLES}, {r: r for r in _ROLES}

    return {r: "" for r in _ROLES}, {r: r for r in _ROLES}, {r: r for r in _ROLES}


def _load_context() -> dict[str, Any]:
    raw = os.getenv("AGP_RUN_CONTEXT")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _rng(context: dict[str, Any]) -> random.Random:
    participants = context.get("participants")
    if isinstance(participants, list) and participants:
        run_ids = [str(p.get("run_id", "")) for p in participants if isinstance(p, dict) and p.get("run_id")]
        seed = min(run_ids) if run_ids else context.get("run_id", "multiplayer_snake_offline")
    else:
        seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "multiplayer_snake_offline"
    return random.Random(seed)


def _build_fn(code: str, role: str, events: list[dict[str, object]], print_context: dict[str, int]) -> tuple[Callable[..., object], str | None]:
    namespace = {"__builtins__": _builtins(role, events, print_context)}
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("make_move") or namespace.get("choose_move")
    return (fn if callable(fn) else _fallback_move), compile_error


def _builtins(role: str, events: list[dict[str, object]], print_context: dict[str, int]) -> dict[str, object]:
    def bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(v) for v in values)
        if end and end != "\n":
            message += end
        for line in message.splitlines() or [""]:
            events.append({"type": "bot_print", "tick": int(print_context.get("tick", 0)), "role": role, "message": line})

    return {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
        "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
        "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], role: str) -> object:
    try:
        return fn(x, y, board, role)
    except TypeError:
        try:
            return fn(x, y, board)
        except Exception:
            return None
    except Exception:
        return None


def _fallback_move(x: int, y: int, board: list[list[int]], _role: str = "") -> str:
    food = _find_food(board)
    moves = [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)]
    if food:
        moves.sort(key=lambda m: abs(x + m[1] - food[0]) + abs(y + m[2] - food[1]))
    for action, dx, dy in moves:
        nx, ny = x + dx, y + dy
        if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] >= 0:
            return action
    return "right"


def _board(snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool], foods: set[tuple[int, int]]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x in range(_WIDTH):
        board[x][0] = -1
        board[x][_HEIGHT - 1] = -1
    for y in range(_HEIGHT):
        board[0][y] = -1
        board[_WIDTH - 1][y] = -1
    for role, body in snakes.items():
        if alive[role]:
            for index, (x, y) in enumerate(body):
                if index == 0:
                    board[x][y] = -2
                elif index == len(body) - 1:
                    board[x][y] = -3
                else:
                    board[x][y] = -1
    for x, y in foods:
        board[x][y] = 1
    return board


def _find_food(board: list[list[int]]) -> tuple[int, int] | None:
    for x, column in enumerate(board):
        for y, value in enumerate(column):
            if value == 1:
                return x, y
    return None


def _ensure_food(rng: random.Random, foods: set[tuple[int, int]], snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool], target: int) -> None:
    while len(foods) < min(target, _MAX_FOOD):
        food = _next_food(rng, snakes, alive, foods)
        if food is None:
            return
        foods.add(food)


def _next_food(rng: random.Random, snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool], foods: set[tuple[int, int]]) -> tuple[int, int] | None:
    occupied = _occupied(snakes, alive) | foods
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) not in occupied]
    return rng.choice(candidates) if candidates else None


def _drop_food(rng: random.Random, foods: set[tuple[int, int]], body: list[tuple[int, int]], blocked: set[tuple[int, int]]) -> list[tuple[int, int]]:
    drops = [cell for cell in body if _inside(cell) and cell not in blocked]
    nearby: list[tuple[int, int]] = []
    occupied = blocked | foods | set(drops)
    for x, y in body:
        for dx, dy in _DELTAS.values():
            cell = (x + dx, y + dy)
            if _inside(cell) and cell not in occupied and cell not in nearby:
                nearby.append(cell)
    rng.shuffle(nearby)
    drops.extend(nearby[: max(0, min(_MAX_DROPPED_FOOD, len(body) + 6) - len(drops))])
    drops = drops[:_MAX_DROPPED_FOOD]
    foods.update(drops)
    return drops


def _try_respawns(
    rng: random.Random,
    snakes: dict[str, list[tuple[int, int]]],
    alive: dict[str, bool],
    respawn_in: dict[str, int],
    directions: dict[str, str],
    respawns: dict[str, int],
    foods: set[tuple[int, int]],
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for role in _ROLES:
        if alive[role] or respawn_in[role] <= 0:
            continue
        respawn_in[role] -= 1
        if respawn_in[role] > 0:
            continue
        body = _find_spawn_body(rng, role, snakes, alive, foods)
        if body is None:
            respawn_in[role] = 1
            continue
        snakes[role] = body
        alive[role] = True
        directions[role] = _spawn_direction(body)
        respawns[role] += 1
        events.append({"slot": role, "body": _points(body)})
    return events


def _find_spawn_body(rng: random.Random, role: str, snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool], foods: set[tuple[int, int]]) -> list[tuple[int, int]] | None:
    occupied = _occupied(snakes, alive) | foods
    preferred = _STARTS[role]
    if all(cell not in occupied and _inside(cell) for cell in preferred):
        return preferred[:]
    candidates = [(x, y) for y in range(2, _HEIGHT - 2) for x in range(2, _WIDTH - 2) if (x, y) not in occupied]
    rng.shuffle(candidates)
    for head in candidates:
        for direction, (dx, dy) in _DELTAS.items():
            tail = (head[0] - dx, head[1] - dy)
            if _inside(tail) and tail not in occupied:
                return [head, tail]
    return None


def _spawn_direction(body: list[tuple[int, int]]) -> str:
    if len(body) < 2:
        return "right"
    head, neck = body[0], body[1]
    dx, dy = head[0] - neck[0], head[1] - neck[1]
    for direction, delta in _DELTAS.items():
        if delta == (dx, dy):
            return direction
    return "right"


def _inside(cell: tuple[int, int]) -> bool:
    x, y = cell
    return 1 <= x < _WIDTH - 1 and 1 <= y < _HEIGHT - 1


def _occupied(snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool]) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for role, body in snakes.items():
        if alive[role]:
            occupied.update(body)
    return occupied


def _total_area(snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool]) -> int:
    return sum(len(body) for role, body in snakes.items() if alive[role])


def _placements(role_team: dict[str, str], role_scores: dict[str, int]) -> dict[str, int]:
    ordered = sorted(_ROLES, key=lambda r: role_scores[r], reverse=True)
    result: dict[str, int] = {}
    last_score: int | None = None
    last_place = 0
    for i, role in enumerate(ordered, start=1):
        score = role_scores[role]
        if score != last_score:
            last_place = i
            last_score = score
        result[role_team[role]] = last_place
    return result


def _frame(
    tick: int,
    phase: str,
    snakes: dict[str, list[tuple[int, int]]],
    alive: dict[str, bool],
    eaten: dict[str, int],
    invalid: dict[str, int],
    foods: set[tuple[int, int]],
    directions: dict[str, str],
    role_team: dict[str, str] | None = None,
    role_name: dict[str, str] | None = None,
    deaths: dict[str, int] | None = None,
    respawn_in: dict[str, int] | None = None,
    slot_scores: dict[str, int] | None = None,
    finish_reason: str | None = None,
    death_events: list[dict[str, object]] | None = None,
    dropped_food: list[dict[str, int | str]] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(snakes, alive, foods),
        "width": _WIDTH,
        "height": _HEIGHT,
        "foods": _points(sorted(foods)),
        "food": _point(next(iter(foods))) if foods else None,
        "holes": {role: dict(hole) for role, hole in _HOLES.items()},
        "total_area": _total_area(snakes, alive),
        "area_limit": _TOTAL_AREA_LIMIT,
        "snakes": {
            role: {
                "body": _points(body),
                "alive": alive[role],
                "food_eaten": eaten[role],
                "deaths": (deaths or {}).get(role, 0),
                "respawn_in": (respawn_in or {}).get(role, 0),
                "invalid_moves": invalid[role],
                "direction": directions[role],
                "team_id": (role_team or {}).get(role, role),
                "name": (role_name or role_team or {}).get(role, role),
                "score": (slot_scores or {}).get(role, eaten[role] * 100),
            }
            for role, body in snakes.items()
        },
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    if finish_reason is not None:
        frame["finish_reason"] = finish_reason
    if death_events:
        frame["death_events"] = death_events
    if dropped_food:
        frame["dropped_food"] = dropped_food
    return {"tick": tick, "phase": phase, "frame": frame}


def _point(cell: tuple[int, int]) -> dict[str, int]:
    return {"x": cell[0], "y": cell[1]}


def _points(cells: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> list[dict[str, int]]:
    return [_point(cell) for cell in cells]


def _copy_grid(grid: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in grid]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
