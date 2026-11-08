from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from worker_service import game_runtime


ROOT = Path(__file__).resolve().parents[3] / "games"


def execute(code: str, *, debug=False, run_id="runtime-test", seed=None):
    context = {"run_kind": "single_task", "run_id": run_id, "codes_by_slot": {"agent": code}, "debug_trace": debug, "seed": seed}
    result = subprocess.run([sys.executable, game_runtime.__file__, str(ROOT / "gate_keys/engine.py")],
                            env={**os.environ, "AGP_RUN_CONTEXT": json.dumps(context)}, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_runtime_records_swallowed_bot_exception_with_line_and_deduplicates():
    result = execute('def make_move(x, y, board, keys):\n    return missing_name\n')
    errors = [e for e in result["events"] if e["type"] == "bot_error"]
    assert len(errors) == 1
    assert errors[0]["line"] == 2
    assert errors[0]["role"] == "agent"
    assert "NameError" in errors[0]["message"]
    assert result["metrics"]["bot_errors"] == 1


def test_debug_snapshots_are_opt_in_and_include_arguments_locals_and_result():
    code = 'def make_move(x, y, board, keys):\n    next_action = "stay"\n    return next_action\n'
    normal = execute(code)
    assert "bot_errors" not in normal["metrics"]
    assert not any(e["type"] == "debug_snapshot" for e in normal["events"])
    debug = execute(code, debug=True)
    snapshots = [e for e in debug["events"] if e["type"] == "debug_snapshot"]
    assert len(snapshots) == 420
    assert snapshots[0]["arguments"]["x"] == 1
    assert snapshots[0]["locals"]["next_action"] == "stay"
    assert snapshots[0]["returned"] == "stay"
    assert snapshots[-1]["tick"] == 419
    assert len(json.dumps(snapshots)) < 1_200_000


def test_seed_reproduces_field_across_run_ids():
    code = 'def make_move(x, y, board, keys):\n    return "stay"\n'
    a, b = execute(code, run_id="first", seed="fixed-map"), execute(code, run_id="second", seed="fixed-map")
    assert a["frames"][0]["frame"]["board"] == b["frames"][0]["frame"]["board"]
    assert a["metrics"] == b["metrics"]


def test_syntax_error_has_original_source_line():
    result = execute('def make_move(x, y, board, keys):\n    return (\n')
    error = next(e for e in result["events"] if e["type"] == "bot_error")
    assert error["line"] == 2
    assert "SyntaxError" in error["message"]


def test_preview_does_not_execute_user_repr_or_iter():
    class Hostile:
        def __repr__(self):
            raise AssertionError("repr must not be called")
        def __iter__(self):
            raise AssertionError("iter must not be called")
    assert game_runtime.preview(Hostile()) == "<Hostile>"


def test_debug_recording_is_bounded_without_stopping_the_engine(tmp_path):
    engine = tmp_path / "engine.py"
    engine.write_text('import json, os\nctx=json.loads(os.environ["AGP_RUN_CONTEXT"])\nnamespace={}\nexec(ctx["codes_by_slot"]["agent"], namespace, namespace)\nfor turn in range(700):\n    namespace["make_move"](turn)\nprint(json.dumps({"status":"finished","metrics":{"turns":700},"events":[]}))\n')
    context = {"run_kind": "single_task", "debug_trace": True,
               "codes_by_slot": {"agent": 'def make_move(turn):\n    local_value = turn + 1\n    return local_value\n'}}
    result = subprocess.run([sys.executable, game_runtime.__file__, str(engine)],
                            env={**os.environ, "AGP_RUN_CONTEXT": json.dumps(context)}, capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    assert payload["metrics"]["turns"] == 700
    assert payload["debug_recorded"] == 500
    assert payload["debug_truncated"] is True
    assert sum(e["type"] == "debug_limit" for e in payload["events"]) == 1


def test_handled_exception_returning_none_is_not_a_python_failure():
    result = execute('def make_move(x, y, board, keys):\n    try:\n        1/0\n    except:\n        return None\n', debug=True)
    assert not any(e["type"] == "bot_error" for e in result["events"])
    snapshots = [e for e in result["events"] if e["type"] == "debug_snapshot"]
    assert snapshots and "exception" not in snapshots[0]
    assert "bot_errors" not in result["metrics"]


def test_wrong_entrypoint_signature_is_reported_even_when_engine_handles_it():
    result = execute('def make_move(state):\n    return "stay"\n')
    assert any(e["type"] == "bot_error" and "TypeError" in e["message"] for e in result["events"])
