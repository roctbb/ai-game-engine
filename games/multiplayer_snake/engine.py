from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 14
_HEIGHT = 14
_MAX_TURNS = 120
_ROLES = ("snake_1", "snake_2")
_DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
_STARTS = {
    "snake_1": [(2, 2), (1, 2)],
    "snake_2": [(11, 11), (12, 11)],
}
_INIT_DIR = {"snake_1": "right", "snake_2": "left"}
_OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
_FOOD_LIMIT = 15


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}

    role_code, role_team, role_name = _resolve_participants(ctx)
    bots = {
        role: _build_fn(role_code.get(role, ""), role, events, print_context)
        for role in _ROLES
    }

    rng = _rng(ctx)
    snakes = {role: body[:] for role, body in _STARTS.items()}
    alive = {role: True for role in _ROLES}
    eaten = {role: 0 for role in _ROLES}
    invalid = {role: 0 for role in _ROLES}
    directions = dict(_INIT_DIR)
    food = _next_food(rng, snakes, alive)
    food_spawned = 1 if food is not None else 0
    turns = 0
    frames = [_frame(0, "running", snakes, alive, eaten, invalid, food, directions, role_team, role_name)]

    for turn in range(_MAX_TURNS):
        if sum(1 for v in alive.values() if v) <= 1 or food is None:
            break
        print_context["tick"] = turn
        board = _board(snakes, alive, food)
        intents: dict[str, tuple[int, int]] = {}
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
            intents[role] = (x + dx, y + dy)

        occupied_now = set()
        for role, body in snakes.items():
            if alive[role]:
                occupied_now.update(body)
        target_counts: dict[tuple[int, int], int] = {}
        for target in intents.values():
            target_counts[target] = target_counts.get(target, 0) + 1

        crashed: set[str] = set()
        for role, target in intents.items():
            own_tail = snakes[role][-1]
            grows = target == food
            occupied = occupied_now if grows else occupied_now - {own_tail}
            if not _inside(target) or target in occupied or target_counts[target] > 1:
                crashed.add(role)

        for role in crashed:
            alive[role] = False
            events.append({"type": "crash", "message": "Столкновение: змейка врезалась в стену, препятствие или себя.", "tick": turn + 1, "slot": role})

        food_taken = False
        for role, target in intents.items():
            if not alive[role]:
                continue
            grows = target == food and not food_taken
            snakes[role].insert(0, target)
            if grows:
                eaten[role] += 1
                food_taken = True
                events.append({"type": "food", "tick": turn + 1, "slot": role, "x": target[0], "y": target[1]})
            else:
                snakes[role].pop()

        if food_taken:
            if food_spawned >= _FOOD_LIMIT:
                food = None
            else:
                food = _next_food(rng, snakes, alive)
                food_spawned += 1 if food is not None else 0

        turns = turn + 1
        frames.append(_frame(turns, "running", snakes, alive, eaten, invalid, food, directions, role_team, role_name))

    compile_errors = {role: err for role, (_fn, err) in bots.items() if err}
    role_scores = {
        role: eaten[role] * 100 + len(snakes[role]) * 5 + (30 if alive[role] else 0) - invalid[role] * 10
        for role in _ROLES
    }
    scores = {role_team[role]: max(0, role_scores[role]) for role in _ROLES}
    placements = _placements(role_team, role_scores)
    winner_role = max(_ROLES, key=lambda r: (role_scores[r], eaten[r], int(alive[r])))
    winner_roles = [r for r in _ROLES if role_scores[r] == max(role_scores.values())]
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": winner_role,
        "winner_slots": winner_roles,
        "is_tie": len(winner_roles) > 1,
        "food_eaten": eaten,
        "alive": alive,
        "invalid_moves": invalid,
        "slot_scores": role_scores,
        "score": max(0, sum(role_scores.values())),
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for role, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": role, "message": message})

    frames.append(_frame(len(frames), "finished", snakes, alive, eaten, invalid, food, directions, role_team, role_name, role_scores))
    payload: dict[str, object] = {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "scores": scores}
    payload["placements"] = placements
    return payload


# ---------------------------------------------------------------------------
# Participant resolution: map each role to a player's code and team_id
# ---------------------------------------------------------------------------

def _resolve_participants(ctx: dict[str, Any]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return (role->code, role->team_id, role->display_name)."""
    participants = ctx.get("participants")
    if isinstance(participants, list) and len(participants) >= 2:
        role_code: dict[str, str] = {}
        role_team: dict[str, str] = {}
        role_name: dict[str, str] = {}
        for i, role in enumerate(_ROLES):
            p = participants[i]
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    # Both runs in a pair see the same participants list, so min(run_id) is stable
    participants = context.get("participants")
    if isinstance(participants, list) and len(participants) >= 2:
        run_ids = [str(p.get("run_id", "")) for p in participants if isinstance(p, dict) and p.get("run_id")]
        seed = min(run_ids) if run_ids else context.get("run_id", "multiplayer_snake_offline")
    else:
        seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "multiplayer_snake_offline"
    return random.Random(seed)


def _build_fn(
    code: str,
    role: str,
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[Callable[..., object], str | None]:
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
        if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] != -1:
            return action
    return "right"


def _board(snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool], food: tuple[int, int] | None) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x in range(_WIDTH):
        board[x][0] = -1
        board[x][_HEIGHT - 1] = -1
    for y in range(_HEIGHT):
        board[0][y] = -1
        board[_WIDTH - 1][y] = -1
    for role, body in snakes.items():
        if alive[role]:
            for x, y in body:
                board[x][y] = -1
    if food is not None:
        board[food[0]][food[1]] = 1
    return board


def _find_food(board: list[list[int]]) -> tuple[int, int] | None:
    for y, row in enumerate(board):
        for x, value in enumerate(row):
            if value == 1:
                return x, y
    return None


def _next_food(rng: random.Random, snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool]) -> tuple[int, int] | None:
    occupied: set[tuple[int, int]] = set()
    for role, body in snakes.items():
        if alive[role]:
            occupied.update(body)
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) not in occupied]
    return rng.choice(candidates) if candidates else None


def _inside(cell: tuple[int, int]) -> bool:
    x, y = cell
    return 1 <= x < _WIDTH - 1 and 1 <= y < _HEIGHT - 1


def _placements(role_team: dict[str, str], role_scores: dict[str, int]) -> dict[str, int]:
    ordered = sorted(_ROLES, key=lambda r: role_scores[r], reverse=True)
    result: dict[str, int] = {}
    last_score: int | None = None
    last_place = 0
    for i, role in enumerate(ordered, start=1):
        s = role_scores[role]
        if s != last_score:
            last_place = i
            last_score = s
        result[role_team[role]] = last_place
    return result


def _frame(
    tick: int, phase: str,
    snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool],
    eaten: dict[str, int], invalid: dict[str, int],
    food: tuple[int, int] | None, directions: dict[str, str],
    role_team: dict[str, str] | None = None,
    role_name: dict[str, str] | None = None,
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(snakes, alive, food),
        "width": _WIDTH,
        "height": _HEIGHT,
        "food": {"x": food[0], "y": food[1]} if food else None,
        "snakes": {
            role: {
                "body": [{"x": x, "y": y} for x, y in body],
                "alive": alive[role],
                "food_eaten": eaten[role],
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
    return {"tick": tick, "phase": phase, "frame": frame}


def _copy_grid(grid: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in grid]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
