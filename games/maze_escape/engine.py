import json
import os
from collections import deque
import random
from typing import Any


_DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
_MAX_STEPS = 2600
_WIDTH = 31
_HEIGHT = 31
_START = (1, 1)


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

    maze = _build_maze(ctx)
    exit_cell = maze["exit"]
    assert isinstance(exit_cell, tuple)
    start_cell = maze["start"]
    assert isinstance(start_cell, tuple)
    optimal_steps = int(maze.get("optimal_steps", 0))

    position = start_cell
    invalid_moves = 0
    steps = 0
    reached_exit = False
    direction = "right"
    frames: list[dict[str, object]] = [
        {
            "tick": 0,
            "phase": "running",
            "frame": {
                "position": {"x": position[0], "y": position[1]},
                **_maze_frame_payload(maze),
                "invalid_moves": invalid_moves,
                "steps": steps,
                "reached_exit": False,
                "optimal_steps": optimal_steps,
                "steps_over_optimal": None,
                "direction": direction,
            },
        }
    ]

    for step in range(_MAX_STEPS):
        if position == exit_cell:
            reached_exit = True
            break

        print_context["tick"] = step
        action = move_fn(_build_state(position=position, step=step, maze=maze))
        delta = _DIRECTIONS.get(action)
        if delta is None:
            invalid_moves += 1
            events.append({"type": "invalid_action", "tick": step, "action": action})
            direction = _normalize_direction(direction=direction, action=action)
            frames.append(
                {
                    "tick": step + 1,
                    "phase": "running",
                    "frame": {
                        "position": {"x": position[0], "y": position[1]},
                        **_maze_frame_payload(maze),
                        "invalid_moves": invalid_moves,
                        "steps": steps,
                        "reached_exit": False,
                        "optimal_steps": optimal_steps,
                        "steps_over_optimal": None,
                        "direction": direction,
                    },
                }
            )
            continue

        target = (position[0] + delta[0], position[1] + delta[1])
        direction = action
        if not _can_enter(target, maze):
            invalid_moves += 1
            events.append({"type": "blocked_move", "tick": step, "action": action, "target": {"x": target[0], "y": target[1]}})
            frames.append(
                {
                    "tick": step + 1,
                    "phase": "running",
                    "frame": {
                        "position": {"x": position[0], "y": position[1]},
                        **_maze_frame_payload(maze),
                        "invalid_moves": invalid_moves,
                        "steps": steps,
                        "reached_exit": False,
                        "optimal_steps": optimal_steps,
                        "steps_over_optimal": None,
                        "direction": direction,
                    },
                }
            )
            continue

        position = target
        steps += 1
        reached_step_exit = position == exit_cell
        if reached_step_exit:
            events.append({"type": "exit_reached", "tick": step + 1})
            reached_exit = True

        frames.append(
            {
                "tick": step + 1,
                "phase": "running",
                "frame": {
                    "position": {"x": position[0], "y": position[1]},
                    **_maze_frame_payload(maze),
                    "invalid_moves": invalid_moves,
                    "steps": steps,
                    "reached_exit": reached_step_exit,
                    "optimal_steps": optimal_steps,
                    "steps_over_optimal": max(0, steps - optimal_steps) if optimal_steps > 0 else None,
                    "direction": direction,
                },
            }
        )

        if reached_exit:
            break

    termination_reason = "reached_exit" if reached_exit else "max_steps_exceeded"
    if optimal_steps > 0:
        steps_over_optimal = max(0, steps - optimal_steps)
        speed_ratio = round(100 * optimal_steps / max(1, steps), 2)
    else:
        steps_over_optimal = None
        speed_ratio = None

    if reached_exit and optimal_steps > 0:
        score = max(0, 2000 - (steps_over_optimal * 5) - invalid_moves * 15)
    else:
        score = 0

    metrics: dict[str, object] = {
        "steps": steps,
        "invalid_moves": invalid_moves,
        "reached_exit": reached_exit,
        "optimal_steps": optimal_steps,
        "steps_over_optimal": steps_over_optimal,
        "speed_ratio": speed_ratio,
        "termination_reason": termination_reason,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(
        {
            "tick": len(frames),
            "phase": "finished",
            "frame": {
                "position": {"x": position[0], "y": position[1]},
                **_maze_frame_payload(maze),
                "invalid_moves": invalid_moves,
                "steps": steps,
                "reached_exit": reached_exit,
                "score": score,
                "optimal_steps": optimal_steps,
                "steps_over_optimal": steps_over_optimal,
                "speed_ratio": speed_ratio,
                "direction": direction,
            },
        }
    )

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
        except Exception as exc:  # pragma: no cover - guarded by integration behavior
            compile_error = str(exc)

    fn = namespace.get("make_move") or namespace.get("choose_move")
    if not callable(fn):
        def _fallback(_state: dict[str, object]) -> str:
            return "right"

        return _fallback, compile_error
    return fn, compile_error


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


def _build_maze(context: dict[str, Any]) -> dict[str, object]:
    run_id = context.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        run_id = "maze_escape_offline"
    return _build_random_maze(seed_source=run_id)


def _build_random_maze(seed_source: str) -> dict[str, object]:
    rng = random.Random(seed_source)
    open_cells = _generate_real_maze(rng=rng, width=_WIDTH, height=_HEIGHT)
    start_cell = _pick_start_cell(rng=rng, cells=open_cells, preferred=_START, width=_WIDTH, height=_HEIGHT)
    distances = _shortest_path_distances(
        cells=open_cells,
        width=_WIDTH,
        height=_HEIGHT,
        start=start_cell,
    )
    if len(distances) < len(open_cells):
        # As a defensive fallback, keep the reachable component only.
        open_cells = set(distances.keys())
        start_cell = _pick_start_cell(
            rng=rng,
            cells=open_cells,
            preferred=start_cell,
            width=_WIDTH,
            height=_HEIGHT,
        )
        distances = _shortest_path_distances(
            cells=open_cells,
            width=_WIDTH,
            height=_HEIGHT,
            start=start_cell,
        )
    exit_cell = _pick_random_exit(
        rng=rng,
        cells=open_cells,
        distances=distances,
        start=start_cell,
    )
    optimal_steps = distances.get(exit_cell, -1)
    if optimal_steps < 0:
        optimal_steps = _shortest_path_length(
            cells=open_cells,
            width=_WIDTH,
            height=_HEIGHT,
            start=start_cell,
            goal=exit_cell,
        )
    if optimal_steps <= 0:
        # safety fallback, should not happen for connected maze
        optimal_steps = 1

    walls: set[tuple[int, int]] = set()
    for y in range(_HEIGHT):
        for x in range(_WIDTH):
            if (x, y) not in open_cells:
                walls.add((x, y))

    return {
        "width": _WIDTH,
        "height": _HEIGHT,
        "start": start_cell,
        "exit": exit_cell,
        "walls": walls,
        "optimal_steps": optimal_steps,
    }


def _pick_random_exit(
    *,
    rng: Any,
    cells: set[tuple[int, int]],
    distances: dict[tuple[int, int], int],
    start: tuple[int, int],
) -> tuple[int, int]:
    if not cells:
        return start
    if not distances:
        candidates = [cell for cell in cells if cell != start]
        return rng.choice(candidates or [start])

    far_threshold = max(distances.values(), default=0) * 0.75
    far_cells = [cell for cell, distance in distances.items() if cell != start and distance >= far_threshold]
    candidates = far_cells or [cell for cell in cells if cell != start]
    return rng.choice(candidates)


def _pick_start_cell(
    *,
    rng: Any,
    cells: set[tuple[int, int]],
    preferred: tuple[int, int],
    width: int,
    height: int,
) -> tuple[int, int]:
    if not cells:
        return preferred

    safe_cells = [cell for cell in cells if 0 < cell[0] < width - 1 and 0 < cell[1] < height - 1]
    if preferred in safe_cells:
        return preferred
    if safe_cells:
        return rng.choice(safe_cells)
    return rng.choice(list(cells))


def _shortest_path_distances(
    *,
    cells: set[tuple[int, int]],
    width: int,
    height: int,
    start: tuple[int, int],
) -> dict[tuple[int, int], int]:
    if start not in cells:
        return {}
    queue: deque[tuple[int, int]] = deque([start])
    distances = {start: 0}

    while queue:
        x, y = queue.popleft()
        distance = distances[(x, y)] + 1
        for dx, dy in _DIRECTIONS.values():
            candidate = (x + dx, y + dy)
            if not (0 <= candidate[0] < width and 0 <= candidate[1] < height):
                continue
            if candidate not in cells or candidate in distances:
                continue
            distances[candidate] = distance
            queue.append(candidate)

    return distances


def _shortest_path_length(
    *,
    cells: set[tuple[int, int]],
    width: int,
    height: int,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> int:
    if start == goal:
        return 0
    distances = _shortest_path_distances(
        cells=cells,
        width=width,
        height=height,
        start=start,
    )
    return distances.get(goal, -1)


def _normalize_direction(*, direction: str, action: object) -> str:
    if isinstance(action, str) and action in _DIRECTIONS:
        return action
    return direction


def _generate_real_maze(rng: Any, width: int, height: int) -> set[tuple[int, int]]:
    open_cells = {_START}
    stack = [_START]
    visited = {_START}

    while stack:
        current = stack[-1]
        neighbors = _collect_two_step_neighbors(current=current, width=width, height=height, visited=visited)
        if not neighbors:
            stack.pop()
            continue
        next_cell = rng.choice(neighbors)
        wall = ((current[0] + next_cell[0]) // 2, (current[1] + next_cell[1]) // 2)
        open_cells.add(wall)
        open_cells.add(next_cell)
        visited.add(next_cell)
        stack.append(next_cell)

    return open_cells


def _collect_two_step_neighbors(
    *,
    current: tuple[int, int],
    width: int,
    height: int,
    visited: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    x, y = current
    moves = (
        (2, 0),
        (-2, 0),
        (0, 2),
        (0, -2),
    )
    neighbors: list[tuple[int, int]] = []
    for dx, dy in moves:
        cell = (x + dx, y + dy)
        if not (1 <= cell[0] < width - 1 and 1 <= cell[1] < height - 1):
            continue
        if cell in visited:
            continue
        neighbors.append(cell)
    return neighbors


def _maze_frame_payload(maze: dict[str, object]) -> dict[str, object]:
    exit_cell = maze["exit"]
    assert isinstance(exit_cell, tuple)
    walls = maze["walls"]
    assert isinstance(walls, set)
    return {
        "size": {"width": maze["width"], "height": maze["height"]},
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "walls": [{"x": x, "y": y} for x, y in sorted(walls)],
    }


def _build_state(position: tuple[int, int], step: int, maze: dict[str, object]) -> dict[str, object]:
    exit_cell = maze["exit"]
    assert isinstance(exit_cell, tuple)
    walls = maze["walls"]
    assert isinstance(walls, set)
    return {
        "position": {"x": position[0], "y": position[1]},
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "step": step,
        "size": {"width": maze["width"], "height": maze["height"]},
        "walls": [{"x": x, "y": y} for x, y in sorted(walls)],
    }


def _can_enter(position: tuple[int, int], maze: dict[str, object]) -> bool:
    x, y = position
    width = maze["width"]
    height = maze["height"]
    walls = maze["walls"]
    assert isinstance(width, int)
    assert isinstance(height, int)
    assert isinstance(walls, set)
    if x < 0 or y < 0 or x >= width or y >= height:
        return False
    return position not in walls


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
