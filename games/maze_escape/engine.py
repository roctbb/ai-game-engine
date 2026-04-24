import json
import os
import random
from typing import Any


_DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
_MAX_STEPS = 64
_WIDTH = 7
_HEIGHT = 7
_WALLS = {(1, 1), (1, 2), (3, 3), (4, 3), (5, 3), (2, 5)}
_START = (0, 0)
_EXIT = (6, 6)


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    move_fn, compile_error = _build_player_fn(ctx, slot_key="agent")
    maze = _build_maze(ctx)
    position = _START
    invalid_moves = 0
    steps = 0
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
            },
        }
    ]
    events: list[dict[str, object]] = []

    for step in range(_MAX_STEPS):
        if position == _EXIT:
            break
        action = move_fn(_build_state(position=position, step=step, maze=maze))
        delta = _DIRECTIONS.get(action)
        if delta is None:
            invalid_moves += 1
            events.append({"type": "invalid_action", "tick": step, "action": action})
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
                    },
                }
            )
            continue
        target = (position[0] + delta[0], position[1] + delta[1])
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
                    },
                }
            )
            continue
        position = target
        steps += 1
        reached_step_exit = position == _EXIT
        if reached_step_exit:
            events.append({"type": "exit_reached", "tick": step + 1})
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
                },
            }
        )

    reached_exit = position == _EXIT
    score = max(0, (100 if reached_exit else 0) - invalid_moves * 2 - steps)
    metrics: dict[str, object] = {
        "steps": steps,
        "invalid_moves": invalid_moves,
        "reached_exit": reached_exit,
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
            "print": print,
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


def _build_maze(context: dict[str, Any]) -> dict[str, object]:
    run_id = context.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return {
            "width": _WIDTH,
            "height": _HEIGHT,
            "start": _START,
            "exit": _EXIT,
            "walls": set(_WALLS),
        }

    rng = random.Random(run_id)
    path = _random_main_path(rng)
    walls: set[tuple[int, int]] = set()
    for y in range(_HEIGHT):
        for x in range(_WIDTH):
            cell = (x, y)
            if cell in path or cell in {_START, _EXIT}:
                continue
            if rng.random() < 0.28:
                walls.add(cell)

    # Add a few guaranteed side openings so the maze feels varied but never impossible.
    for _ in range(5):
        walls.discard((rng.randrange(_WIDTH), rng.randrange(_HEIGHT)))

    return {
        "width": _WIDTH,
        "height": _HEIGHT,
        "start": _START,
        "exit": _EXIT,
        "walls": walls,
    }


def _random_main_path(rng: random.Random) -> set[tuple[int, int]]:
    moves = ["right"] * (_WIDTH - 1) + ["down"] * (_HEIGHT - 1)
    rng.shuffle(moves)
    x, y = _START
    path = {(x, y)}
    for move in moves:
        if move == "right":
            x += 1
        else:
            y += 1
        path.add((x, y))
    return path


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
