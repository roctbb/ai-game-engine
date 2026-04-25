import json
import os
import random
from typing import Any


_MAX_STEPS = 60
_WIDTH = 10
_HEIGHT = 10
_GOAL = (_WIDTH - 1, _HEIGHT - 1)
_COINS_TOTAL = 10
_DEAD_ENDS_MIN = 5
_DELTAS = {
    "right": (1, 0),
    "down": (0, 1),
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    move_fn, compile_error = _build_player_fn(
        ctx,
        slot_key="agent",
        events=events,
        print_context=print_context,
    )

    game_map = _build_map(ctx)
    coins = game_map["coins"]
    walls = game_map["walls"]
    assert isinstance(coins, set) and isinstance(walls, set)

    position = (0, 0)
    collected = 0
    invalid_moves = 0
    steps = 0
    coins_left = set(coins)
    if position in coins_left:
        coins_left.remove(position)
        collected += 1
    frames: list[dict[str, object]] = [_frame(0, "running", position, coins_left, walls, collected, invalid_moves, False)]

    for step in range(_MAX_STEPS):
        if position == _GOAL:
            break
        print_context["tick"] = step
        board = _board(coins_left=coins_left, walls=walls)
        action = _safe_call(
            move_fn,
            position=position,
            board=board,
            step=step,
            coins_left=coins_left,
            walls=walls,
        )
        delta = _DELTAS.get(action)
        if delta is None:
            invalid_moves += 1
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": step, "action": action})
            frames.append(_frame(step + 1, "running", position, coins_left, walls, collected, invalid_moves, False))
            continue
        target = (position[0] + delta[0], position[1] + delta[1])
        if not _can_enter(target, walls):
            invalid_moves += 1
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": step, "action": action, "target": {"x": target[0], "y": target[1]}})
            frames.append(_frame(step + 1, "running", position, coins_left, walls, collected, invalid_moves, False))
            continue
        position = target
        steps += 1
        if position in coins_left:
            coins_left.remove(position)
            collected += 1
            events.append({"type": "coin_collected", "tick": step + 1, "position": {"x": position[0], "y": position[1]}})
        reached_goal_now = position == _GOAL
        if reached_goal_now:
            events.append({"type": "goal_reached", "tick": step + 1})
        frames.append(_frame(step + 1, "running", position, coins_left, walls, collected, invalid_moves, reached_goal_now))

    reached_goal = position == _GOAL
    score = max(0, collected * 10 + (50 if reached_goal else 0) - invalid_moves)
    metrics: dict[str, object] = {
        "steps": steps,
        "coins_collected": collected,
        "coins_total": len(coins),
        "walls_total": len(walls),
        "dead_ends_total": len(_dead_end_cells(walls)),
        "invalid_moves": invalid_moves,
        "reached_goal": reached_goal,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, coins_left, walls, collected, invalid_moves, reached_goal, score))

    return {
        "status": "finished",
        "metrics": metrics,
        "frames": frames,
        "events": events,
        "replay_ref": None,
    }


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
        seed = "coins_right_down_offline"
    rng = random.Random(seed)

    for _attempt in range(200):
        guaranteed_path = _random_monotonic_path(rng)
        path_cells = set(guaranteed_path)
        open_cells = path_cells | _build_dead_end_branches(rng=rng, path=guaranteed_path)
        walls = {
            (x, y)
            for y in range(_HEIGHT)
            for x in range(_WIDTH)
            if (x, y) not in open_cells
        }
        if len(_dead_end_cells(walls)) >= _DEAD_ENDS_MIN:
            break
    else:
        guaranteed_path = _fallback_path()
        open_cells = set(guaranteed_path) | {
            (1, 1), (1, 2),
            (3, 1),
            (5, 1), (5, 2),
            (7, 1),
        }
        walls = {
            (x, y)
            for y in range(_HEIGHT)
            for x in range(_WIDTH)
            if (x, y) not in open_cells
        }

    coin_candidates = [cell for cell in guaranteed_path[1:-1] if cell not in walls]
    rng.shuffle(coin_candidates)
    coins = set(coin_candidates[:_COINS_TOTAL])

    return {"walls": walls, "coins": coins}


def _build_dead_end_branches(rng: random.Random, path: list[tuple[int, int]]) -> set[tuple[int, int]]:
    path_cells = set(path)
    branches: set[tuple[int, int]] = set()
    branch_roots = list(range(1, len(path) - 2))
    rng.shuffle(branch_roots)

    for index in branch_roots:
        if len(_dead_end_candidates(path_cells | branches)) >= _DEAD_ENDS_MIN:
            break
        start = path[index]
        next_on_path = path[index + 1]
        options = []
        for _action, (dx, dy) in _DELTAS.items():
            candidate = (start[0] + dx, start[1] + dy)
            if candidate != next_on_path and _is_inside(candidate) and candidate not in path_cells and candidate not in branches:
                options.append(candidate)
        rng.shuffle(options)
        for first_cell in options:
            candidate_branch = _grow_branch(rng=rng, first_cell=first_cell, blocked=path_cells | branches)
            if candidate_branch and _is_isolated_dead_branch(candidate_branch, path_cells | branches):
                branches.update(candidate_branch)
                break

    return branches


def _grow_branch(
    rng: random.Random,
    first_cell: tuple[int, int],
    blocked: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    branch = [first_cell]
    current = first_cell
    for _ in range(rng.randint(0, 2)):
        options = []
        for dx, dy in _DELTAS.values():
            nxt = (current[0] + dx, current[1] + dy)
            if _is_inside(nxt) and nxt not in blocked and nxt not in branch:
                options.append(nxt)
        if not options:
            break
        rng.shuffle(options)
        current = options[0]
        branch.append(current)
    return branch


def _is_isolated_dead_branch(branch: list[tuple[int, int]], existing_open: set[tuple[int, int]]) -> bool:
    branch_set = set(branch)
    for index, cell in enumerate(branch):
        allowed_next = branch[index + 1] if index + 1 < len(branch) else None
        for dx, dy in _DELTAS.values():
            nxt = (cell[0] + dx, cell[1] + dy)
            if nxt == allowed_next:
                continue
            if nxt in existing_open or nxt in branch_set:
                return False
    return True


def _dead_end_candidates(open_cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    walls = {
        (x, y)
        for y in range(_HEIGHT)
        for x in range(_WIDTH)
        if (x, y) not in open_cells
    }
    return _dead_end_cells(walls)


def _dead_end_cells(walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    reachable = _reachable_cells(start=(0, 0), walls=walls)
    can_reach_goal = _cells_that_can_reach_goal(walls)
    return reachable - can_reach_goal


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    if start in walls:
        return set()
    seen = {start}
    queue = [start]
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for dx, dy in _DELTAS.values():
            nxt = (current[0] + dx, current[1] + dy)
            if _can_enter(nxt, walls) and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _cells_that_can_reach_goal(walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    if _GOAL in walls:
        return set()
    seen = {_GOAL}
    queue = [_GOAL]
    head = 0
    reverse_deltas = [(-dx, -dy) for dx, dy in _DELTAS.values()]
    while head < len(queue):
        current = queue[head]
        head += 1
        for dx, dy in reverse_deltas:
            previous = (current[0] + dx, current[1] + dy)
            if _can_enter(previous, walls) and previous not in seen:
                seen.add(previous)
                queue.append(previous)
    return seen


def _fallback_path() -> list[tuple[int, int]]:
    return [(x, 0) for x in range(_WIDTH)] + [(_WIDTH - 1, y) for y in range(1, _HEIGHT)]


def _random_monotonic_path(rng: random.Random) -> list[tuple[int, int]]:
    x, y = 0, 0
    path = [(x, y)]
    rights = _WIDTH - 1
    downs = _HEIGHT - 1
    moves = ["right"] * rights + ["down"] * downs
    rng.shuffle(moves)
    for move in moves:
        if move == "right":
            x += 1
        else:
            y += 1
        path.append((x, y))
    return path


def _build_player_fn(
    context: dict[str, Any],
    slot_key: str,
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[callable, str | None]:
    code = ""
    codes = context.get("codes_by_slot")
    if isinstance(codes, dict):
        raw_code = codes.get(slot_key)
        if isinstance(raw_code, str):
            code = raw_code

    namespace: dict[str, Any] = {
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "print": _make_bot_print(events=events, role=slot_key, print_context=print_context),
            "range": range,
            "set": set,
            "str": str,
            "sum": sum,
            "tuple": tuple,
        }
    }
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:  # pragma: no cover - runtime integration path
            compile_error = str(exc)

    fn = namespace.get("make_move") or namespace.get("choose_move")
    if not callable(fn):
        def _fallback(x: int, y: int, board: list[list[int]]) -> str:
            if x + 1 < _WIDTH and board[x + 1][y] != -1:
                return "right"
            return "down"

        return _fallback, compile_error
    return fn, compile_error


def _safe_call(
    fn: callable,
    position: tuple[int, int],
    board: list[list[int]],
    step: int,
    coins_left: set[tuple[int, int]],
    walls: set[tuple[int, int]],
) -> object:
    try:
        return fn(position[0], position[1], board)
    except TypeError:
        try:
            return fn(_build_state(position=position, step=step, coins_left=coins_left, walls=walls))
        except Exception:
            return None
    except Exception:
        return None


def _make_bot_print(
    events: list[dict[str, object]],
    role: str,
    print_context: dict[str, int],
) -> callable:
    def _bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message = f"{message}{end}"
        lines = message.splitlines() or [""]
        for line in lines:
            events.append(
                {
                    "type": "bot_print",
                    "tick": int(print_context.get("tick", 0)),
                    "role": role,
                    "message": line,
                }
            )

    return _bot_print


def _build_state(
    position: tuple[int, int],
    step: int,
    coins_left: set[tuple[int, int]],
    walls: set[tuple[int, int]],
) -> dict[str, object]:
    return {
        "position": {"x": position[0], "y": position[1]},
        "step": step,
        "goal": {"x": _GOAL[0], "y": _GOAL[1]},
        "size": {"width": _WIDTH, "height": _HEIGHT},
        "coins": [{"x": x, "y": y} for x, y in sorted(coins_left)],
        "walls": [{"x": x, "y": y} for x, y in sorted(walls)],
        "board": _board(coins_left=coins_left, walls=walls),
    }


def _is_inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _can_enter(position: tuple[int, int], walls: set[tuple[int, int]]) -> bool:
    return _is_inside(position) and position not in walls


def _board(coins_left: set[tuple[int, int]], walls: set[tuple[int, int]]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in coins_left:
        board[x][y] = 1
    board[_GOAL[0]][_GOAL[1]] = 2
    return board


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    coins_left: set[tuple[int, int]],
    walls: set[tuple[int, int]],
    collected: int,
    invalid_moves: int,
    reached_goal: bool,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "position": {"x": position[0], "y": position[1]},
        "goal": {"x": _GOAL[0], "y": _GOAL[1]},
        "size": {"width": _WIDTH, "height": _HEIGHT},
        "board": _board(coins_left=coins_left, walls=walls),
        "coins": [{"x": x, "y": y} for x, y in sorted(coins_left)],
        "walls": [{"x": x, "y": y} for x, y in sorted(walls)],
        "coins_left": len(coins_left),
        "coins_collected": collected,
        "invalid_moves": invalid_moves,
        "reached_goal": reached_goal,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
