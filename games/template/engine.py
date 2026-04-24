from __future__ import annotations

import json
import os
from typing import Any, Callable


_MAX_TURNS = 20


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    bot_fn, compile_error = _build_bot_fn(ctx=ctx, slot_key="bot")

    state: dict[str, Any] = {
        "turn": 0,
        "value": 0,
    }
    frames: list[dict[str, object]] = [
        {
            "tick": 0,
            "phase": "running",
            "frame": {"turn": 0, "value": 0, "action": "init"},
        }
    ]
    events: list[dict[str, object]] = []

    for turn in range(_MAX_TURNS):
        state["turn"] = turn
        action = _call_bot(bot_fn=bot_fn, state=state)
        if action == "inc":
            state["value"] += 1
        elif action == "dec":
            state["value"] -= 1
        elif action == "stop":
            events.append({"type": "stop", "turn": turn})
            frames.append(
                {
                    "tick": turn + 1,
                    "phase": "running",
                    "frame": {"turn": turn, "value": state["value"], "action": action},
                }
            )
            break
        events.append({"type": "action", "turn": turn, "action": action, "value": state["value"]})
        frames.append(
            {
                "tick": turn + 1,
                "phase": "running",
                "frame": {"turn": turn, "value": state["value"], "action": action},
            }
        )

    metrics: dict[str, object] = {
        "final_value": state["value"],
        "turns_played": int(state["turn"]) + 1,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    payload: dict[str, object] = {
        "status": "finished",
        "metrics": metrics,
    }

    run_kind = str(ctx.get("run_kind") or "single_task")
    if run_kind == "competition_match":
        payload["scores"] = {"team-player": int(state["value"]), "team-bot": 0}
        payload["placements"] = {"team-player": 1, "team-bot": 2}
    elif run_kind == "training_match":
        payload["scores"] = {"team-player": int(state["value"]), "team-bot": 0}
    else:
        payload["replay_ref"] = None

    frames.append(
        {
            "tick": len(frames),
            "phase": "finished",
            "frame": {
                "turn": state["turn"],
                "value": state["value"],
                "action": "finished",
            },
        }
    )
    payload["frames"] = frames
    payload["events"] = events

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


def _build_bot_fn(ctx: dict[str, Any], slot_key: str) -> tuple[Callable[..., object], str | None]:
    code = ""
    codes = ctx.get("codes_by_slot")
    if isinstance(codes, dict):
        raw = codes.get(slot_key)
        if isinstance(raw, str):
            code = raw

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
        except Exception as exc:  # pragma: no cover - runtime path
            compile_error = str(exc)

    fn = namespace.get("make_choice") or namespace.get("make_move")
    if callable(fn):
        return fn, compile_error
    return _fallback_bot, compile_error


def _call_bot(bot_fn: Callable[..., object], state: dict[str, Any]) -> str:
    try:
        candidate = bot_fn(state)
    except Exception:  # pragma: no cover - runtime path
        return "inc"
    if isinstance(candidate, str):
        action = candidate.strip().lower()
        if action in {"inc", "dec", "stay", "stop"}:
            return action
    return "inc"


def _fallback_bot(_state: dict[str, Any]) -> str:
    return "inc"


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
