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


def test_maze_escape_engine_uses_script() -> None:
    module = _load_module(_repo_root() / "games" / "maze_escape" / "engine.py", "maze_engine_test")
    context = {
        "codes_by_slot": {
            "agent": (
                "def make_move(state):\n"
                "    x = state['position']['x']\n"
                "    y = state['position']['y']\n"
                "    if y < 6 and x in {0, 6}:\n"
                "        return 'down'\n"
                "    if x < 6:\n"
                "        return 'right'\n"
                "    return 'down'\n"
            )
        }
    }
    payload = module.run(context)
    metrics = payload["metrics"]
    assert payload["status"] == "finished"
    assert metrics["reached_exit"] is True
    assert metrics["score"] > 0
    assert isinstance(payload.get("frames"), list) and payload["frames"]
    assert isinstance(payload.get("events"), list)


def test_coins_engine_collects_with_script() -> None:
    module = _load_module(
        _repo_root() / "games" / "coins_right_down" / "engine.py",
        "coins_engine_test",
    )
    context = {
        "codes_by_slot": {
            "agent": (
                "def make_move(state):\n"
                "    if state['position']['x'] < state['goal']['x']:\n"
                "        return 'right'\n"
                "    return 'down'\n"
            )
        }
    }
    payload = module.run(context)
    metrics = payload["metrics"]
    assert payload["status"] == "finished"
    assert metrics["reached_goal"] is True
    assert metrics["coins_collected"] >= 3
    assert isinstance(payload.get("frames"), list) and payload["frames"]
    assert isinstance(payload.get("events"), list)


def test_tower_defense_engine_places_towers_from_script() -> None:
    module = _load_module(
        _repo_root() / "games" / "tower_defense" / "engine.py",
        "tower_engine_test",
    )
    context = {
        "codes_by_slot": {
            "defender": (
                "def place_tower(state):\n"
                "    return state['tick'] % 3\n"
            )
        }
    }
    payload = module.run(context)
    metrics = payload["metrics"]
    assert payload["status"] == "finished"
    assert metrics["towers_built"] > 0
    assert metrics["base_hp"] >= 0
    assert isinstance(payload.get("frames"), list) and payload["frames"]
    assert isinstance(payload.get("events"), list)


def test_single_task_engine_allows_print_for_debug() -> None:
    module = _load_module(_repo_root() / "games" / "maze_escape" / "engine.py", "maze_engine_print_test")
    context = {
        "codes_by_slot": {
            "agent": (
                "def make_move(state):\n"
                "    print('step', state['step'])\n"
                "    return 'right'\n"
            )
        }
    }
    payload = module.run(context)
    metrics = payload["metrics"]
    assert payload["status"] == "finished"
    assert "compile_error" not in metrics
    print_events = [event for event in payload["events"] if event.get("type") == "bot_print"]
    assert print_events
    assert print_events[0]["role"] == "agent"
    assert print_events[0]["message"].startswith("step ")
