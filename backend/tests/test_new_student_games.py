from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_game_example(game: str, example: str) -> str:
    return (_repo_root() / "games" / game / "examples" / example).read_text(encoding="utf-8")


def test_minesweeper_demo_uses_matrix_contract_and_opens_cells() -> None:
    engine = _load_module(_repo_root() / "games" / "minesweeper" / "engine.py", "minesweeper_engine_test")
    payload = engine.run(
        {
            "run_id": "minesweeper-test",
            "codes_by_slot": {"agent": _read_game_example("minesweeper", "basic_solver.py")},
        }
    )

    metrics = payload["metrics"]
    first_frame = payload["frames"][0]["frame"]
    final_frame = payload["frames"][-1]["frame"]
    first_open = next(event for event in payload["events"] if event.get("type") == "open")
    mines = {(cell["x"], cell["y"]) for cell in final_frame["mines"]}

    assert payload["status"] == "finished"
    assert metrics["won"] is True
    assert metrics["opened_safe_cells"] == metrics["safe_cells_total"]
    assert metrics["mines_total"] == 18
    assert "compile_error" not in metrics
    assert isinstance(first_frame["board"], list)
    assert final_frame["width"] == 12
    assert final_frame["height"] == 12
    assert final_frame["score"] == metrics["score"]
    assert "mines" in final_frame
    assert engine._is_solvable_without_guessing(  # noqa: SLF001
        first_open=(first_open["x"], first_open["y"]),
        mines=mines,
    )[0] is True


def test_coins_right_down_generates_seeded_walls_and_demo_reaches_goal() -> None:
    engine = _load_module(
        _repo_root() / "games" / "coins_right_down" / "engine.py",
        "coins_right_down_random_map_test",
    )
    code = _read_game_example("coins_right_down", "agent_coin_collector.py")

    first = engine.run({"run_id": "coins-seed-a", "codes_by_slot": {"agent": code}})
    second = engine.run({"run_id": "coins-seed-b", "codes_by_slot": {"agent": code}})

    first_metrics = first["metrics"]
    first_frame = first["frames"][0]["frame"]
    second_frame = second["frames"][0]["frame"]

    assert first_metrics["reached_goal"] is True
    assert first_metrics["coins_collected"] == first_metrics["coins_total"]
    assert first_metrics["walls_total"] > 0
    assert first_frame["board"] != second_frame["board"]
    assert any(cell == -1 for row in first_frame["board"] for cell in row)
    assert any(cell == 1 for row in first_frame["board"] for cell in row)


def test_snake_demo_eats_food_and_uses_simple_parameters() -> None:
    engine = _load_module(_repo_root() / "games" / "snake" / "engine.py", "snake_engine_test")
    payload = engine.run(
        {
            "run_id": "snake-test",
            "codes_by_slot": {"agent": _read_game_example("snake", "food_chaser.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["food_eaten"] >= 1
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"][0][0] == -1
    assert {"x", "y"}.issubset(frame["head"])


def test_snake_single_player_does_not_stop_after_ten_foods() -> None:
    engine = _load_module(_repo_root() / "games" / "snake" / "engine.py", "snake_engine_no_food_limit_test")
    code = (
        "direction = 'right'\n"
        "order = ['right', 'down', 'left', 'up']\n"
        "delta = {'right': (1, 0), 'down': (0, 1), 'left': (-1, 0), 'up': (0, -1)}\n"
        "def make_move(x, y, board):\n"
        "    global direction\n"
        "    start = order.index(direction)\n"
        "    for offset in (0, 1, -1, 2):\n"
        "        candidate = order[(start + offset) % len(order)]\n"
        "        dx, dy = delta[candidate]\n"
        "        nx, ny = x + dx, y + dy\n"
        "        if 0 <= ny < len(board) and 0 <= nx < len(board[ny]) and board[ny][nx] != -1:\n"
        "            direction = candidate\n"
        "            return candidate\n"
        "    return direction\n"
    )

    payload = engine.run({"run_id": "snake-long-run-test", "codes_by_slot": {"agent": code}})
    metrics = payload["metrics"]

    assert payload["status"] == "finished"
    assert metrics["turns"] > 10
    assert not (metrics["food_eaten"] == 10 and metrics["alive"] is True and metrics["won"] is True)


def test_multiplayer_snake_demo_returns_scores_for_all_slots() -> None:
    engine = _load_module(
        _repo_root() / "games" / "multiplayer_snake" / "engine.py",
        "multiplayer_snake_engine_test",
    )
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "multi-snake-test",
            "team_id": "team-primary",
            "codes_by_slot": {
                "snake_1": _read_game_example("multiplayer_snake", "food_chaser_1.py"),
                "snake_2": _read_game_example("multiplayer_snake", "food_chaser_2.py"),
                "snake_3": _read_game_example("multiplayer_snake", "food_chaser_3.py"),
                "snake_4": _read_game_example("multiplayer_snake", "food_chaser_4.py"),
            },
        }
    )

    metrics = payload["metrics"]
    first_frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert payload["metrics"]["score"] == sum(payload["metrics"]["slot_scores"].values())
    assert payload["scores"] == {"team-primary": payload["metrics"]["score"]}
    assert payload["placements"] == {"team-primary": 1}
    assert set(metrics["food_eaten"]) == {"snake_1", "snake_2", "snake_3", "snake_4"}
    assert first_frame["board"][0][0] == -1
    assert "compile_errors" not in metrics
