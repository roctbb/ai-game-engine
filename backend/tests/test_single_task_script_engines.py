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
                "def make_move(x, y, maze):\n"
                "    start = (x, y)\n"
                "    goal = None\n"
                "    for col_x, column in enumerate(maze):\n"
                "        for row_y, cell in enumerate(column):\n"
                "            if cell == 1:\n"
                "                goal = (col_x, row_y)\n"
                "                break\n"
                "        if goal is not None:\n"
                "            break\n"
                "    if goal is None:\n"
                "        return 'right'\n"
                "    directions = [('right', 1, 0), ('down', 0, 1), ('left', -1, 0), ('up', 0, -1)]\n"
                "    queue = [start]\n"
                "    came_from = {start: ('', start)}\n"
                "    head = 0\n"
                "    while head < len(queue):\n"
                "        current = queue[head]\n"
                "        head += 1\n"
                "        if current == goal:\n"
                "            break\n"
                "        for action, dx, dy in directions:\n"
                "            nx = current[0] + dx\n"
                "            ny = current[1] + dy\n"
                "            next_cell = (nx, ny)\n"
                "            if nx < 0 or nx >= len(maze) or ny < 0 or ny >= len(maze[nx]):\n"
                "                continue\n"
                "            if maze[nx][ny] == -1 or next_cell in came_from:\n"
                "                continue\n"
                "            came_from[next_cell] = (action, current)\n"
                "            queue.append(next_cell)\n"
                "    current = goal\n"
                "    while current in came_from and came_from[current][1] != start:\n"
                "        current = came_from[current][1]\n"
                "    return came_from[current][0] if current in came_from else 'right'\n"
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
            "agent": (_repo_root() / "games" / "coins_right_down" / "examples" / "agent_coin_collector.py").read_text(encoding="utf-8")
        }
    }
    payload = module.run(context)
    metrics = payload["metrics"]
    assert payload["status"] == "finished"
    assert metrics["reached_goal"] is True
    assert metrics["coins_collected"] >= 3
    assert metrics["dead_ends_total"] >= 5
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
    assert metrics["max_ticks"] == 44
    assert metrics["track_length"] == 14
    assert metrics["enemies_spawned"] == 40
    assert isinstance(payload.get("frames"), list) and payload["frames"]
    assert isinstance(payload.get("events"), list)


def test_single_task_engine_allows_print_for_debug() -> None:
    module = _load_module(_repo_root() / "games" / "maze_escape" / "engine.py", "maze_engine_print_test")
    context = {
        "codes_by_slot": {
            "agent": (
                "def make_move(x, y, maze):\n"
                "    print('position', x, y)\n"
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
    assert print_events[0]["message"].startswith("position ")
