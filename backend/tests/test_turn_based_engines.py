from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_tic_tac_toe_training_match_returns_scores() -> None:
    module = _load_module(_repo_root() / "games" / "tic_tac_toe" / "engine.py", "ttt_engine_training_test")
    context = {
        "run_kind": "training_match",
        "codes_by_slot": {
            "bot": (
                "def make_choice(field, role):\n"
                "    for x in range(5):\n"
                "        for y in range(5):\n"
                "            if field[x][y] == 0:\n"
                "                return x, y\n"
            )
        },
    }
    payload = module.run(context)
    metrics = payload["metrics"]
    assert payload["status"] == "finished"
    assert "scores" in payload
    assert metrics["turns_played"] > 0
    assert metrics["winner_role"] in {-1, 0, 1}
    assert isinstance(payload.get("frames"), list) and payload["frames"]
    assert isinstance(payload.get("events"), list)


def test_tic_tac_toe_competition_match_returns_placements() -> None:
    module = _load_module(_repo_root() / "games" / "tic_tac_toe" / "engine.py", "ttt_engine_competition_test")
    context = {
        "run_kind": "competition_match",
        "codes_by_slot": {
            "bot": (
                "class Bot:\n"
                "    def make_move(self, observation):\n"
                "        field = observation['field']\n"
                "        for x in range(5):\n"
                "            for y in range(5):\n"
                "                if field[x][y] == 0:\n"
                "                    return x, y\n"
            )
        },
    }
    payload = module.run(context)
    assert payload["status"] == "finished"
    assert "placements" in payload
    assert "scores" in payload
    assert payload["metrics"]["draw"] in {True, False}
    assert isinstance(payload.get("frames"), list) and payload["frames"]
    assert isinstance(payload.get("events"), list)


def test_tanks_training_match_uses_driver_and_support() -> None:
    module = _load_module(_repo_root() / "games" / "tanks" / "engine.py", "tanks_engine_training_test")
    context = {
        "run_kind": "training_match",
        "codes_by_slot": {
            "driver": (
                "def make_choice(x, y, map_state):\n"
                "    print('tick', map_state['tick'])\n"
                "    flag = map_state['flag']\n"
                "    if x < flag['x']:\n"
                "        return 'right'\n"
                "    if x > flag['x']:\n"
                "        return 'left'\n"
                "    if y < flag['y']:\n"
                "        return 'down'\n"
                "    if y > flag['y']:\n"
                "        return 'up'\n"
                "    return 'stay'\n"
            ),
            "support": (
                "def make_support(state):\n"
                "    return 'boost' if state['support']['boost_cooldown'] == 0 else 'none'\n"
            ),
        },
    }
    payload = module.run(context)
    assert payload["status"] == "finished"
    assert "scores" in payload
    metrics = payload["metrics"]
    assert metrics["ticks_played"] > 0
    assert metrics["winner"] in {"player", "enemy", "draw"}
    assert "compile_error_driver" not in metrics
    assert "compile_error_support" not in metrics
    assert isinstance(payload.get("frames"), list) and payload["frames"]
    assert isinstance(payload.get("events"), list)


def test_template_turn_based_engine_runs_with_context() -> None:
    module = _load_module(_repo_root() / "games" / "template" / "engine.py", "template_engine_test")
    context = {
        "run_kind": "single_task",
        "codes_by_slot": {
            "bot": (
                "def make_choice(state):\n"
                "    return 'stop' if state['turn'] >= 2 else 'inc'\n"
            )
        },
    }
    payload = module.run(context)
    assert payload["status"] == "finished"
    assert payload["metrics"]["final_value"] >= 2
    assert "replay_ref" in payload
    assert isinstance(payload.get("frames"), list) and payload["frames"]
    assert isinstance(payload.get("events"), list)


def test_tic_tac_toe_competition_draw_marks_explicit_tie(monkeypatch) -> None:
    module = _load_module(_repo_root() / "games" / "tic_tac_toe" / "engine.py", "ttt_engine_draw_tie_test")
    monkeypatch.setattr(module, "_MAX_TURNS", 0)
    payload = module.run({"run_kind": "competition_match", "codes_by_slot": {}})
    assert payload["status"] == "finished"
    assert payload["metrics"]["draw"] is True
    assert payload["placements"]["team-player"] == payload["placements"]["team-bot"]
    assert payload["tie_resolution"] == "explicit_tie"


def test_tanks_competition_draw_marks_explicit_tie(monkeypatch) -> None:
    module = _load_module(_repo_root() / "games" / "tanks" / "engine.py", "tanks_engine_draw_tie_test")
    monkeypatch.setattr(module, "_MAX_TICKS", 0)
    payload = module.run({"run_kind": "competition_match", "codes_by_slot": {}})
    assert payload["status"] == "finished"
    assert payload["metrics"]["winner"] == "draw"
    assert payload["placements"]["team-player"] == payload["placements"]["team-bot"]
    assert payload["tie_resolution"] == "explicit_tie"
