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
_MAX_STEPS = 1200
_WIDTH = 21
_HEIGHT = 21


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
        try:
            action = move_fn(_build_state(position=position, step=step, maze=maze))
        except Exception as exc:
            action = None
            error_msg = f"{type(exc).__name__}: {exc}"
            if not hasattr(move_fn, "_err_count"):
                move_fn._err_count = 0
            move_fn._err_count += 1
            if move_fn._err_count <= 3:
                events.append({"type": "bot_print", "tick": step, "role": "agent", "message": f"[ERROR] {error_msg}"})
            if move_fn._err_count == 1:
                events.append({"type": "runtime_error", "tick": step, "message": error_msg})
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


# ---------------------------------------------------------------------------
# Context helpers
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
            "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
            "enumerate": enumerate, "float": float, "int": int, "len": len,
            "list": list, "max": max, "min": min,
            "print": _make_bot_print(events=events, role=slot_key, print_context=print_context),
            "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple,
            "hasattr": hasattr, "getattr": getattr, "setattr": setattr,
        }
    }
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
            events.append({"type": "bot_print", "tick": 0, "role": slot_key, "message": f"[COMPILE ERROR] {compile_error}"})

    fn = namespace.get("make_move") or namespace.get("choose_move")
    if not callable(fn):
        return (lambda _s: "right"), compile_error
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
        for line in (message.splitlines() or [""]):
            events.append({"type": "bot_print", "tick": int(print_context.get("tick", 0)), "role": role, "message": line})
    return _bot_print


# ---------------------------------------------------------------------------
# Maze generation — recursive backtracker, 1-cell-wide corridors
# ---------------------------------------------------------------------------

def _build_maze(context: dict[str, Any]) -> dict[str, object]:
    run_id = context.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        run_id = "maze_escape_offline"
    return _build_random_maze(seed_source=run_id)


def _build_random_maze(seed_source: str) -> dict[str, object]:
    rng = random.Random(seed_source)
    w, h = _WIDTH, _HEIGHT

    # Generate perfect maze, then punch extra passages
    open_cells = _generate_maze(rng=rng, width=w, height=h)
    _add_extra_passages(rng=rng, open_cells=open_cells, width=w, height=h, ratio=0.08)

    # Pick start: random open interior cell
    interior = [c for c in open_cells if 1 <= c[0] < w - 1 and 1 <= c[1] < h - 1]
    start_cell = rng.choice(interior) if interior else (1, 1)

    # BFS distances from start
    distances = _bfs_distances(cells=open_cells, start=start_cell)

    # Keep only reachable component
    if len(distances) < len(open_cells):
        open_cells = set(distances.keys())
        interior = [c for c in open_cells if 1 <= c[0] < w - 1 and 1 <= c[1] < h - 1]
        if start_cell not in open_cells:
            start_cell = rng.choice(interior) if interior else rng.choice(list(open_cells))
        distances = _bfs_distances(cells=open_cells, start=start_cell)

    # Pick exit: far from start, surrounded by walls on 3 sides (dead-end)
    exit_cell = _pick_walled_exit(rng=rng, open_cells=open_cells, distances=distances, start=start_cell, w=w, h=h)

    optimal = distances.get(exit_cell, 1)
    if optimal <= 0:
        optimal = 1

    walls: set[tuple[int, int]] = set()
    for y in range(h):
        for x in range(w):
            if (x, y) not in open_cells:
                walls.add((x, y))

    return {
        "width": w,
        "height": h,
        "start": start_cell,
        "exit": exit_cell,
        "walls": walls,
        "optimal_steps": optimal,
    }


def _generate_maze(rng: Any, width: int, height: int) -> set[tuple[int, int]]:
    """Recursive backtracker on odd-coordinate grid → perfect maze with 1-cell corridors."""
    start = (1, 1)
    open_cells = {start}
    stack = [start]
    visited = {start}

    while stack:
        current = stack[-1]
        neighbors = []
        cx, cy = current
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nx, ny = cx + dx, cy + dy
            if 1 <= nx < width - 1 and 1 <= ny < height - 1 and (nx, ny) not in visited:
                neighbors.append((nx, ny))
        if not neighbors:
            stack.pop()
            continue
        nxt = rng.choice(neighbors)
        wall = ((current[0] + nxt[0]) // 2, (current[1] + nxt[1]) // 2)
        open_cells.add(wall)
        open_cells.add(nxt)
        visited.add(nxt)
        stack.append(nxt)

    return open_cells


def _add_extra_passages(rng: Any, open_cells: set[tuple[int, int]], width: int, height: int, ratio: float) -> None:
    """Remove random interior wall cells that border ≥2 open cells, creating loops."""
    candidates = []
    for y in range(2, height - 2):
        for x in range(2, width - 2):
            if (x, y) in open_cells:
                continue
            adj_open = sum(1 for dx, dy in _DIRECTIONS.values() if (x + dx, y + dy) in open_cells)
            if adj_open >= 2:
                candidates.append((x, y))
    rng.shuffle(candidates)
    for cell in candidates[:max(1, int(len(candidates) * ratio))]:
        open_cells.add(cell)


def _bfs_distances(cells: set[tuple[int, int]], start: tuple[int, int]) -> dict[tuple[int, int], int]:
    if start not in cells:
        return {}
    queue: deque[tuple[int, int]] = deque([start])
    dist = {start: 0}
    while queue:
        x, y = queue.popleft()
        d = dist[(x, y)] + 1
        for dx, dy in _DIRECTIONS.values():
            nb = (x + dx, y + dy)
            if nb in cells and nb not in dist:
                dist[nb] = d
                queue.append(nb)
    return dist


def _pick_walled_exit(
    *,
    rng: Any,
    open_cells: set[tuple[int, int]],
    distances: dict[tuple[int, int], int],
    start: tuple[int, int],
    w: int,
    h: int,
) -> tuple[int, int]:
    """Pick exit that is far from start and surrounded by walls on ≥3 sides (dead-end)."""
    if not distances:
        return start

    max_dist = max(distances.values())
    far_threshold = max_dist * 0.6

    # Find dead-ends: open cells with exactly 1 open neighbor
    dead_ends: list[tuple[int, int]] = []
    for cell in open_cells:
        if cell == start:
            continue
        if distances.get(cell, 0) < far_threshold:
            continue
        open_neighbors = sum(
            1 for dx, dy in _DIRECTIONS.values()
            if (cell[0] + dx, cell[1] + dy) in open_cells
        )
        if open_neighbors == 1:
            dead_ends.append(cell)

    if dead_ends:
        # Pick the farthest dead-end
        dead_ends.sort(key=lambda c: distances.get(c, 0), reverse=True)
        top = dead_ends[:max(1, len(dead_ends) // 3)]
        return rng.choice(top)

    # Fallback: farthest reachable cell
    far_cells = [c for c, d in distances.items() if c != start and d >= far_threshold]
    return rng.choice(far_cells) if far_cells else start


# ---------------------------------------------------------------------------
# State / frame helpers
# ---------------------------------------------------------------------------

def _maze_frame_payload(maze: dict[str, object]) -> dict[str, object]:
    exit_cell = maze["exit"]
    assert isinstance(exit_cell, tuple)
    walls = maze["walls"]
    assert isinstance(walls, set)
    return {
        "size": {"width": maze["width"], "height": maze["height"]},
        "exit": {"x": exit_cell[0], "y": exit_cell[1]},
        "maze": _maze_grid(maze),
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
        "maze": _maze_grid(maze),
        "walls": [{"x": x, "y": y} for x, y in sorted(walls)],
    }


def _maze_grid(maze: dict[str, object]) -> list[list[int]]:
    width = maze["width"]
    height = maze["height"]
    walls = maze["walls"]
    exit_cell = maze["exit"]
    assert isinstance(width, int) and isinstance(height, int)
    assert isinstance(walls, set) and isinstance(exit_cell, tuple)

    grid: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        for x in range(width):
            if (x, y) == exit_cell:
                row.append(1)
            elif (x, y) in walls:
                row.append(-1)
            else:
                row.append(0)
        grid.append(row)
    return grid


def _can_enter(position: tuple[int, int], maze: dict[str, object]) -> bool:
    x, y = position
    width = maze["width"]
    height = maze["height"]
    walls = maze["walls"]
    assert isinstance(width, int) and isinstance(height, int) and isinstance(walls, set)
    if x < 0 or y < 0 or x >= width or y >= height:
        return False
    return position not in walls


def _normalize_direction(*, direction: str, action: object) -> str:
    if isinstance(action, str) and action in _DIRECTIONS:
        return action
    return direction


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
