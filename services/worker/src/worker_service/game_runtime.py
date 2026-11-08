"""Optional, bounded bot diagnostics around an unchanged engine entrypoint.

This file is also included in isolated game archives; it only needs the stdlib.
Player code keeps its existing signature, globals and restricted builtins.
"""
from __future__ import annotations

import builtins
from contextlib import redirect_stdout
import io
from itertools import islice
import json
import math
import os
from pathlib import Path
import runpy
import sys
import types


def preview(value: object, depth: int = 0) -> object:
    kind = type(value)
    if value is None or kind is bool:
        return value
    if kind is int:
        return value if value.bit_length() < 128 else "большое число"
    if kind is float:
        return value if math.isfinite(value) else str(value)
    if kind is str:
        return value[:240] + ("…" if len(value) > 240 else "")
    if depth >= 3:
        return "…"
    if kind in (list, tuple, set, frozenset):
        values = list(islice(value, 16))
        result = [preview(item, depth + 1) for item in values]
        if len(value) > 16:
            result.append(f"… ещё {len(value) - 16}")
        return result
    if kind is dict:
        return {str(key)[:80]: preview(item, depth + 1) for key, item in islice(value.items(), 16)
                if type(key) in (str, int, float, bool)}
    return f"<{kind.__name__}>"


def execute(entrypoint: str) -> None:
    context = json.loads(os.environ.get("AGP_RUN_CONTEXT", "{}"))
    if context.get("run_kind") != "single_task":
        runpy.run_path(entrypoint, run_name="__main__")
        return
    sources = context.get("codes_by_slot", {})
    source_slots = {source.strip(): str(slot) for slot, source in sources.items() if isinstance(source, str)}
    debug = context.get("debug_trace") is True
    events: list[dict[str, object]] = []
    calls: dict[int, dict[str, object]] = {}
    errors: set[tuple[str, object, str]] = set()
    error_objects: list[BaseException] = []
    debug_count = 0
    debug_bytes = 0
    limited = False
    original_exec = builtins.exec

    def add_error(slot: str, tick: int, exc: BaseException, line: int | None) -> None:
        key = (slot, line, type(exc).__name__)
        if any(exc is previous for previous in error_objects) or key in errors or len(errors) >= 32:
            return
        if line is None and any(role == slot and name == type(exc).__name__ for role, _, name in errors):
            return
        error_objects.append(exc)
        errors.add(key)
        events.append({"type": "bot_error", "tick": tick, "role": slot, "line": line,
                       "message": f"{type(exc).__name__}: {str(exc)[:800]}"})

    def instrumented_exec(source, globals=None, locals=None, **kwargs):
        caller = sys._getframe(1)
        if globals is None:
            globals, locals = caller.f_globals, caller.f_locals if locals is None else locals
        elif locals is None:
            locals = globals
        slot = source_slots.get(source.strip()) if isinstance(source, str) else None
        if slot is not None:
            try:
                source = compile(source, f"<bot:{slot}>", "exec")
            except SyntaxError as exc:
                add_error(slot, 0, exc, exc.lineno)
                raise
        return original_exec(source, globals, locals, **kwargs)

    def tick_for(frame) -> int:
        parent = frame.f_back
        for _ in range(12):
            if parent is None:
                break
            values = parent.f_locals
            pc = values.get("print_context")
            if type(pc) is dict and type(pc.get("tick")) is int:
                return max(0, pc["tick"])
            for key in ("turn", "tick", "turn_index"):
                if type(values.get(key)) is int and not parent.f_code.co_filename.startswith("<bot:"):
                    return max(0, values[key])
            parent = parent.f_back
        return 0

    def trace(frame, event, arg):
        nonlocal debug_count, debug_bytes, limited
        filename = frame.f_code.co_filename
        bot = filename.startswith("<bot:")
        fn = frame.f_locals.get("fn") if frame.f_code.co_name == "_safe_call" else None
        safe_call = isinstance(fn, types.FunctionType) and fn.__code__.co_filename.startswith("<bot:")
        if not bot and not safe_call:
            return None
        frame.f_trace_lines = False
        frame.f_trace_opcodes = False
        key = id(frame)
        if event == "call":
            if frame.f_code.co_name == "<module>":
                return trace
            parent_bot = frame.f_back is not None and frame.f_back.f_code.co_filename.startswith("<bot:")
            slot = filename[5:-1] if bot else fn.__code__.co_filename[5:-1]
            names = frame.f_code.co_varnames[:frame.f_code.co_argcount + frame.f_code.co_kwonlyargcount]
            calls[key] = {"slot": slot, "tick": tick_for(frame), "top": bot and not parent_bot,
                          "arguments": {name: preview(frame.f_locals.get(name)) for name in names} if debug and bot and not parent_bot else {}}
        elif event == "exception":
            call = calls.get(key)
            if call is not None:
                call["exception"] = (arg[1], frame.f_lineno if bot else None)
        elif event == "return":
            call = calls.pop(key, None)
            if call is None:
                return trace
            if arg is None and "exception" in call:
                exc, line = call["exception"]
                add_error(call["slot"], call["tick"], exc, line)
            if debug and call["top"]:
                snapshot = {"type": "debug_snapshot", "tick": call["tick"], "role": call["slot"],
                            "function": frame.f_code.co_name, "line": frame.f_lineno,
                            "arguments": call["arguments"], "locals": {
                                name: preview(value) for name, value in islice(frame.f_locals.items(), 24)
                                if name not in call["arguments"] and not name.startswith("__") and not callable(value)}, "returned": preview(arg)}
                if arg is None and "exception" in call:
                    snapshot["exception"] = f"{type(call['exception'][0]).__name__}: {str(call['exception'][0])[:300]}"
                size = len(json.dumps(snapshot, ensure_ascii=False))
                if debug_count < 500 and debug_bytes + size <= 1_000_000:
                    events.append(snapshot)
                    debug_count += 1
                    debug_bytes += size
                elif not limited:
                    events.append({"type": "debug_limit", "tick": call["tick"], "message": "Достигнут лимит отладочной записи. Игра продолжена без записи переменных."})
                    limited = True
        return trace

    output = io.StringIO()
    builtins.exec = instrumented_exec
    sys.settrace(trace)
    try:
        with redirect_stdout(output):
            runpy.run_path(str(Path(entrypoint).resolve()), run_name="__main__")
    finally:
        sys.settrace(None)
        builtins.exec = original_exec
    lines = output.getvalue().splitlines()
    if not lines:
        raise RuntimeError("Game engine did not print result payload")
    payload = json.loads(lines[-1])
    if events:
        payload.setdefault("events", []).extend(events)
    if errors:
        payload.setdefault("metrics", {})["bot_errors"] = len(errors)
    if debug:
        payload["debug_recorded"] = debug_count
        payload["debug_truncated"] = limited
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    execute(sys.argv[1])
