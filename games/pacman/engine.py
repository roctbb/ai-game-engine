from __future__ import annotations

import json
import os
import random
from collections import deque
from typing import Any, Callable


_WIDTH = 15
_HEIGHT = 15
_MAX_TURNS = 260
_PACMAN_START = (1, 1)
_GHOST_STARTS = [(13, 13), (13, 1)]
_RANDOM_WALLS = 18
_GHOST_VISION = 6
_DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    "stay": (0, 0),
}
_BASE_WALLS = {
    (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (8, 0), (9, 0), (10, 0), (11, 0), (12, 0), (13, 0), (14, 0),
    (0, 14), (1, 14), (2, 14), (3, 14), (4, 14), (5, 14), (6, 14), (7, 14), (8, 14), (9, 14), (10, 14), (11, 14), (12, 14), (13, 14), (14, 14),
    (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10), (0, 11), (0, 12), (0, 13),
    (14, 1), (14, 2), (14, 3), (14, 4), (14, 5), (14, 6), (14, 7), (14, 8), (14, 9), (14, 10), (14, 11), (14, 12), (14, 13),
    (3, 2), (4, 2), (10, 2), (11, 2),
    (2, 4), (3, 4), (5, 4), (6, 4), (8, 4), (9, 4), (11, 4), (12, 4),
    (5, 6), (6, 6), (8, 6), (9, 6),
    (2, 7), (3, 7), (11, 7), (12, 7),
    (5, 8), (6, 8), (8, 8), (9, 8),
    (2, 10), (3, 10), (5, 10), (6, 10), (8, 10), (9, 10), (11, 10), (12, 10),
    (3, 12), (4, 12), (10, 12), (11, 12),
}
_POWER_DOTS = {(1, 13), (13, 1), (13, 13)}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    move_fn, compile_error = _build_player_fn(ctx, events, print_context)
    rng = _rng(ctx)
    walls = _build_walls(ctx)

    pacman = _PACMAN_START
    ghosts = list(_GHOST_STARTS)
    dots = _initial_dots(walls)
    power_dots = set(_POWER_DOTS)
    score = 0
    turns = 0
    invalid_moves = 0
    powered_turns = 0
    alive = True
    ghost_states = _ghost_states(ghosts, pacman, walls, powered_turns > 0, ghost_turn=True)
    frames = [_frame(0, "running", pacman, ghosts, dots, power_dots, walls, score, alive, powered_turns, invalid_moves, ghost_states)]

    for turn in range(_MAX_TURNS):
        if not alive or (not dots and not power_dots):
            break
        print_context["tick"] = turn
        board = _board(pacman, ghosts, dots, power_dots, walls)
        action = _safe_call(move_fn, pacman[0], pacman[1], board)
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(pacman, str(action))
        if target in walls:
            invalid_moves += 1
            target = pacman
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        pacman = target

        if pacman in dots:
            dots.remove(pacman)
            score += 10
            events.append({"type": "dot", "tick": turn + 1, "x": pacman[0], "y": pacman[1]})
        if pacman in power_dots:
            power_dots.remove(pacman)
            powered_turns = 18
            score += 50
            events.append({"type": "power_dot", "tick": turn + 1, "x": pacman[0], "y": pacman[1]})

        if pacman in ghosts:
            if powered_turns > 0:
                ghosts = [_respawn_ghost(ghosts, rng) if ghost == pacman else ghost for ghost in ghosts]
                score += 200
                events.append({"type": "ghost_eaten", "tick": turn + 1})
            else:
                alive = False
                events.append({"type": "caught", "message": "Пакмена поймал призрак.", "tick": turn + 1})

        ghost_turn = turn % 3 != 2
        ghost_states = _ghost_states(ghosts, pacman, walls, powered_turns > 0, ghost_turn=ghost_turn)
        if alive and ghost_turn:
            ghosts = _move_ghosts(ghosts=ghosts, pacman=pacman, powered=powered_turns > 0, walls=walls, rng=rng, states=ghost_states)
            if pacman in ghosts:
                if powered_turns > 0:
                    ghosts = [_respawn_ghost(ghosts, rng) if ghost == pacman else ghost for ghost in ghosts]
                    score += 200
                    events.append({"type": "ghost_eaten", "tick": turn + 1})
                else:
                    alive = False
                    events.append({"type": "caught", "message": "Пакмена поймал призрак.", "tick": turn + 1})

        if powered_turns > 0:
            powered_turns -= 1

        turns = turn + 1
        ghost_states = _ghost_states(ghosts, pacman, walls, powered_turns > 0, ghost_turn=(turn + 1) % 3 != 2)
        frames.append(_frame(turns, "running", pacman, ghosts, dots, power_dots, walls, score, alive, powered_turns, invalid_moves, ghost_states))

    won = alive and not dots and not power_dots
    final_score = max(0, score + (300 if won else 0) - invalid_moves * 5)
    metrics: dict[str, object] = {
        "turns": turns,
        "score": final_score,
        "raw_score": score,
        "dots_collected": len(_initial_dots(walls)) - len(dots),
        "dots_total": len(_initial_dots(walls)),
        "power_dots_left": len(power_dots),
        "walls_total": len(walls) - len(_BASE_WALLS),
        "invalid_moves": invalid_moves,
        "alive": alive,
        "won": won,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", pacman, ghosts, dots, power_dots, walls, final_score, alive, powered_turns, invalid_moves, _ghost_states(ghosts, pacman, walls, powered_turns > 0, ghost_turn=False)))
    return {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "replay_ref": None}


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
        seed = "pacman_offline"
    return random.Random(seed)


def _build_walls(context: dict[str, Any]) -> set[tuple[int, int]]:
    rng = _rng(context)
    fixed = set(_BASE_WALLS) | {_PACMAN_START} | set(_GHOST_STARTS) | set(_POWER_DOTS)
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in fixed
    ]
    for _attempt in range(500):
        rng.shuffle(candidates)
        walls = set(_BASE_WALLS) | set(candidates[:_RANDOM_WALLS])
        open_cells = {
            (x, y)
            for y in range(_HEIGHT)
            for x in range(_WIDTH)
            if (x, y) not in walls
        }
        reachable = _reachable_cells(_PACMAN_START, walls)
        if open_cells <= reachable:
            return walls
    return set(_BASE_WALLS)


def _build_player_fn(
    context: dict[str, Any],
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[Callable[..., object], str | None]:
    code = ""
    codes = context.get("codes_by_slot")
    if isinstance(codes, dict) and isinstance(codes.get("agent"), str):
        code = str(codes["agent"])
    namespace = {"__builtins__": _builtins(events, print_context)}
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("make_move") or namespace.get("choose_move")
    return (fn if callable(fn) else _fallback_move), compile_error


def _builtins(events: list[dict[str, object]], print_context: dict[str, int]) -> dict[str, object]:
    def bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message += end
        for line in message.splitlines() or [""]:
            events.append({"type": "bot_print", "tick": int(print_context.get("tick", 0)), "role": "agent", "message": line})

    return {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
        "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
        "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]]) -> object:
    try:
        return fn(x, y, board)
    except Exception:
        return None


def _fallback_move(x: int, y: int, board: list[list[int]]) -> str:
    for action, dx, dy in (("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] != -1:
            return action
    return "stay"


def _initial_dots(walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    blocked = set(walls) | {_PACMAN_START} | set(_GHOST_STARTS) | set(_POWER_DOTS)
    return {
        (x, y)
        for y in range(_HEIGHT)
        for x in range(_WIDTH)
        if (x, y) not in blocked
    }


def _board(
    pacman: tuple[int, int],
    ghosts: list[tuple[int, int]],
    dots: set[tuple[int, int]],
    power_dots: set[tuple[int, int]],
    walls: set[tuple[int, int]],
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in dots:
        board[x][y] = 1
    for x, y in power_dots:
        board[x][y] = 2
    for x, y in ghosts:
        board[x][y] = -2
    return board


def _move(cell: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return cell[0] + dx, cell[1] + dy


def _move_ghosts(
    *,
    ghosts: list[tuple[int, int]],
    pacman: tuple[int, int],
    powered: bool,
    walls: set[tuple[int, int]],
    rng: random.Random,
    states: list[dict[str, object]],
) -> list[tuple[int, int]]:
    moved = []
    occupied: set[tuple[int, int]] = set()
    for index, ghost in enumerate(ghosts):
        candidates = [
            _move(ghost, action)
            for action in ("up", "down", "left", "right")
            if _move(ghost, action) not in walls
        ]
        candidates = [cell for cell in candidates if cell not in occupied] or candidates
        if not candidates:
            moved.append(ghost)
            occupied.add(ghost)
            continue
        active = bool(states[index].get("active")) if index < len(states) else False
        if not active:
            choices = candidates + [ghost]
        elif powered:
            best_distance = max(_distance(cell, pacman, walls) for cell in candidates)
            choices = [cell for cell in candidates if _distance(cell, pacman, walls) == best_distance]
        else:
            best_distance = min(_distance(cell, pacman, walls) for cell in candidates)
            choices = [cell for cell in candidates if _distance(cell, pacman, walls) == best_distance]
        chosen = rng.choice(choices)
        moved.append(chosen)
        occupied.add(chosen)
    return moved


def _ghost_states(
    ghosts: list[tuple[int, int]],
    pacman: tuple[int, int],
    walls: set[tuple[int, int]],
    powered: bool,
    ghost_turn: bool,
) -> list[dict[str, object]]:
    states = []
    for x, y in ghosts:
        distance = _distance((x, y), pacman, walls)
        sees_pacman = distance <= _GHOST_VISION
        states.append({
            "x": x,
            "y": y,
            "distance": distance if sees_pacman else None,
            "active": ghost_turn and sees_pacman,
            "resting": not ghost_turn,
            "frightened": powered,
        })
    return states


def _distance(start: tuple[int, int], goal: tuple[int, int], walls: set[tuple[int, int]]) -> int:
    if start == goal:
        return 0
    queue: deque[tuple[int, int]] = deque([start])
    dist = {start: 0}
    while queue:
        cell = queue.popleft()
        for action in ("up", "down", "left", "right"):
            nxt = _move(cell, action)
            if nxt in walls or nxt in dist:
                continue
            dist[nxt] = dist[cell] + 1
            if nxt == goal:
                return dist[nxt]
            queue.append(nxt)
    return 999


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue: deque[tuple[int, int]] = deque([start])
    seen = {start}
    while queue:
        cell = queue.popleft()
        for action in ("up", "down", "left", "right"):
            nxt = _move(cell, action)
            if nxt in walls or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _respawn_ghost(ghosts: list[tuple[int, int]], rng: random.Random) -> tuple[int, int]:
    candidates = [cell for cell in _GHOST_STARTS if cell not in ghosts]
    return rng.choice(candidates or _GHOST_STARTS)


def _frame(
    tick: int,
    phase: str,
    pacman: tuple[int, int],
    ghosts: list[tuple[int, int]],
    dots: set[tuple[int, int]],
    power_dots: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    score: int,
    alive: bool,
    powered_turns: int,
    invalid_moves: int,
    ghost_states: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "tick": tick,
        "phase": phase,
        "frame": {
            "board": _board(pacman, ghosts, dots, power_dots, walls),
            "width": _WIDTH,
            "height": _HEIGHT,
            "pacman": {"x": pacman[0], "y": pacman[1]},
            "ghosts": [{"x": x, "y": y} for x, y in ghosts],
            "ghost_states": ghost_states,
            "ghost_vision": _GHOST_VISION,
            "dots_left": len(dots),
            "power_dots_left": len(power_dots),
            "score": score,
            "alive": alive,
            "powered_turns": powered_turns,
            "invalid_moves": invalid_moves,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
