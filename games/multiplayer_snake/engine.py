from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 14
_HEIGHT = 14
_MAX_TURNS = 120
_SLOTS = ("snake_1", "snake_2", "snake_3", "snake_4")
_DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
_STARTS = {
    "snake_1": [(2, 2), (1, 2)],
    "snake_2": [(11, 2), (12, 2)],
    "snake_3": [(2, 11), (1, 11)],
    "snake_4": [(11, 11), (12, 11)],
}
_OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
_FOOD_LIMIT = 15


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    bots = {
        slot: _build_player_fn(ctx, slot, events, print_context)
        for slot in _SLOTS
    }
    rng = _rng(ctx)
    snakes = {slot: body[:] for slot, body in _STARTS.items()}
    alive = {slot: True for slot in _SLOTS}
    eaten = {slot: 0 for slot in _SLOTS}
    invalid = {slot: 0 for slot in _SLOTS}
    directions = {"snake_1": "right", "snake_2": "left", "snake_3": "right", "snake_4": "left"}
    food = _next_food(rng, snakes, alive)
    food_spawned = 1 if food is not None else 0
    turns = 0
    frames = [_frame(0, "running", snakes, alive, eaten, invalid, food, directions)]

    for turn in range(_MAX_TURNS):
        if sum(1 for value in alive.values() if value) <= 1 or food is None:
            break
        print_context["tick"] = turn
        board = _board(snakes, alive, food)
        intents: dict[str, tuple[int, int]] = {}
        for slot in _SLOTS:
            if not alive[slot]:
                continue
            fn, _compile_error = bots[slot]
            x, y = snakes[slot][0]
            action = _safe_call(fn, x, y, _copy_grid(board), slot)
            if action not in _DELTAS:
                invalid[slot] += 1
                action = directions[slot]
                events.append({"type": "invalid_action", "tick": turn, "slot": slot})
            if len(snakes[slot]) > 1 and action == _OPPOSITE[directions[slot]]:
                invalid[slot] += 1
                action = directions[slot]
                events.append({"type": "reverse_blocked", "tick": turn, "slot": slot})
            directions[slot] = str(action)
            dx, dy = _DELTAS[str(action)]
            intents[slot] = (x + dx, y + dy)

        occupied_now = set()
        for slot, body in snakes.items():
            if alive[slot]:
                occupied_now.update(body)
        target_counts: dict[tuple[int, int], int] = {}
        for target in intents.values():
            target_counts[target] = target_counts.get(target, 0) + 1

        crashed: set[str] = set()
        for slot, target in intents.items():
            own_tail = snakes[slot][-1]
            grows = target == food
            occupied = occupied_now if grows else occupied_now - {own_tail}
            if not _inside(target) or target in occupied or target_counts[target] > 1:
                crashed.add(slot)

        for slot in crashed:
            alive[slot] = False
            events.append({"type": "crash", "tick": turn + 1, "slot": slot})

        food_taken = False
        for slot, target in intents.items():
            if not alive[slot]:
                continue
            grows = target == food and not food_taken
            snakes[slot].insert(0, target)
            if grows:
                eaten[slot] += 1
                food_taken = True
                events.append({"type": "food", "tick": turn + 1, "slot": slot, "x": target[0], "y": target[1]})
            else:
                snakes[slot].pop()

        if food_taken:
            if food_spawned >= _FOOD_LIMIT:
                food = None
            else:
                food = _next_food(rng, snakes, alive)
                food_spawned += 1 if food is not None else 0

        turns = turn + 1
        frames.append(_frame(turns, "running", snakes, alive, eaten, invalid, food, directions))

    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    team_ids = _team_ids(ctx)
    slot_scores = {
        slot: eaten[slot] * 100 + len(snakes[slot]) * 5 + (30 if alive[slot] else 0) - invalid[slot] * 10
        for slot in _SLOTS
    }
    score = max(0, sum(slot_scores.values()))
    scores = {team_ids["snake_1"]: score}
    placements = {team_ids["snake_1"]: 1}
    winner_slot = max(_SLOTS, key=lambda slot: (slot_scores[slot], eaten[slot], int(alive[slot])))
    metrics: dict[str, object] = {
        "turns": turns,
        "winner_slot": winner_slot,
        "food_eaten": eaten,
        "alive": alive,
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
        "score": score,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", snakes, alive, eaten, invalid, food, directions, slot_scores))
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


def _rng(context: dict[str, Any]) -> random.Random:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "multiplayer_snake_offline"
    return random.Random(seed)


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


def _fallback_move(x: int, y: int, board: list[list[int]], _slot: str = "") -> str:
    food = _find_food(board)
    moves = [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)]
    if food:
        moves.sort(key=lambda move: abs(x + move[1] - food[0]) + abs(y + move[2] - food[1]))
    for action, dx, dy in moves:
        nx, ny = x + dx, y + dy
        if 0 <= ny < len(board) and 0 <= nx < len(board[ny]) and board[ny][nx] != -1:
            return action
    return "right"


def _board(snakes: dict[str, list[tuple[int, int]]], alive: dict[str, bool], food: tuple[int, int] | None) -> list[list[int]]:
    board = [[0 for _ in range(_WIDTH)] for _ in range(_HEIGHT)]
    for x in range(_WIDTH):
        board[0][x] = -1
        board[_HEIGHT - 1][x] = -1
    for y in range(_HEIGHT):
        board[y][0] = -1
        board[y][_WIDTH - 1] = -1
    for slot, body in snakes.items():
        if alive[slot]:
            for x, y in body:
                board[y][x] = -1
    if food is not None:
        board[food[1]][food[0]] = 1
    return board


def _find_food(board: list[list[int]]) -> tuple[int, int] | None:
    for y, row in enumerate(board):
        for x, value in enumerate(row):
            if value == 1:
                return x, y
    return None


def _next_food(
    rng: random.Random,
    snakes: dict[str, list[tuple[int, int]]],
    alive: dict[str, bool],
) -> tuple[int, int] | None:
    occupied: set[tuple[int, int]] = set()
    for slot, body in snakes.items():
        if alive[slot]:
            occupied.update(body)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in occupied
    ]
    return rng.choice(candidates) if candidates else None


def _inside(cell: tuple[int, int]) -> bool:
    x, y = cell
    return 1 <= x < _WIDTH - 1 and 1 <= y < _HEIGHT - 1


def _team_ids(ctx: dict[str, Any]) -> dict[str, str]:
    return {slot: f"team-{slot}" for slot in _SLOTS} | (
        {"snake_1": str(ctx["team_id"])} if isinstance(ctx.get("team_id"), str) and ctx.get("team_id") else {}
    )
def _frame(
    tick: int,
    phase: str,
    snakes: dict[str, list[tuple[int, int]]],
    alive: dict[str, bool],
    eaten: dict[str, int],
    invalid: dict[str, int],
    food: tuple[int, int] | None,
    directions: dict[str, str],
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(snakes, alive, food),
        "width": _WIDTH,
        "height": _HEIGHT,
        "food": {"x": food[0], "y": food[1]} if food else None,
        "snakes": {
            slot: {
                "body": [{"x": x, "y": y} for x, y in body],
                "alive": alive[slot],
                "food_eaten": eaten[slot],
                "invalid_moves": invalid[slot],
                "direction": directions[slot],
            }
            for slot, body in snakes.items()
        },
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


def _copy_grid(grid: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in grid]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
