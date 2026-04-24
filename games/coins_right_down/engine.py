import json
import os
from typing import Any


_MAX_STEPS = 24
_WIDTH = 6
_HEIGHT = 6
_GOAL = (_WIDTH - 1, _HEIGHT - 1)
_COINS = {(1, 0), (2, 0), (2, 1), (3, 2), (4, 4), (5, 4)}
_DELTAS = {
    "right": (1, 0),
    "down": (0, 1),
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    move_fn, compile_error = _build_player_fn(ctx, slot_key="agent")

    position = (0, 0)
    collected = 0
    invalid_moves = 0
    steps = 0
    coins_left = set(_COINS)
    if position in coins_left:
        coins_left.remove(position)
        collected += 1
    frames: list[dict[str, object]] = [
        {
            "tick": 0,
            "phase": "running",
            "frame": {
                "position": {"x": position[0], "y": position[1]},
                "coins_left": len(coins_left),
                "coins_collected": collected,
                "invalid_moves": invalid_moves,
                "reached_goal": False,
            },
        }
    ]
    events: list[dict[str, object]] = []

    for step in range(_MAX_STEPS):
        if position == _GOAL:
            break
        action = move_fn(_build_state(position=position, step=step, coins_left=coins_left))
        delta = _DELTAS.get(action)
        if delta is None:
            invalid_moves += 1
            events.append({"type": "invalid_action", "tick": step, "action": action})
            frames.append(
                {
                    "tick": step + 1,
                    "phase": "running",
                    "frame": {
                        "position": {"x": position[0], "y": position[1]},
                        "coins_left": len(coins_left),
                        "coins_collected": collected,
                        "invalid_moves": invalid_moves,
                        "reached_goal": False,
                    },
                }
            )
            continue
        target = (position[0] + delta[0], position[1] + delta[1])
        if not _is_inside(target):
            invalid_moves += 1
            events.append({"type": "blocked_move", "tick": step, "action": action, "target": {"x": target[0], "y": target[1]}})
            frames.append(
                {
                    "tick": step + 1,
                    "phase": "running",
                    "frame": {
                        "position": {"x": position[0], "y": position[1]},
                        "coins_left": len(coins_left),
                        "coins_collected": collected,
                        "invalid_moves": invalid_moves,
                        "reached_goal": False,
                    },
                }
            )
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
        frames.append(
            {
                "tick": step + 1,
                "phase": "running",
                "frame": {
                    "position": {"x": position[0], "y": position[1]},
                    "coins_left": len(coins_left),
                    "coins_collected": collected,
                    "invalid_moves": invalid_moves,
                    "reached_goal": reached_goal_now,
                },
            }
        )

    reached_goal = position == _GOAL
    score = max(0, collected * 10 + (50 if reached_goal else 0) - invalid_moves)
    metrics: dict[str, object] = {
        "steps": steps,
        "coins_collected": collected,
        "coins_total": len(_COINS),
        "invalid_moves": invalid_moves,
        "reached_goal": reached_goal,
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
                "coins_left": len(coins_left),
                "coins_collected": collected,
                "invalid_moves": invalid_moves,
                "reached_goal": reached_goal,
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
        except Exception as exc:  # pragma: no cover - runtime integration path
            compile_error = str(exc)

    fn = namespace.get("make_move") or namespace.get("choose_move")
    if not callable(fn):
        def _fallback(state: dict[str, object]) -> str:
            pos = state["position"]
            if isinstance(pos, dict) and pos.get("x", 0) < _GOAL[0]:
                return "right"
            return "down"

        return _fallback, compile_error
    return fn, compile_error


def _build_state(
    position: tuple[int, int],
    step: int,
    coins_left: set[tuple[int, int]],
) -> dict[str, object]:
    return {
        "position": {"x": position[0], "y": position[1]},
        "step": step,
        "goal": {"x": _GOAL[0], "y": _GOAL[1]},
        "size": {"width": _WIDTH, "height": _HEIGHT},
        "coins": [{"x": x, "y": y} for x, y in sorted(coins_left)],
    }


def _is_inside(position: tuple[int, int]) -> bool:
    x, y = position
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
