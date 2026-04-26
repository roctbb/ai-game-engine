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
    other = engine.run(
        {
            "run_id": "snake-other-seed",
            "codes_by_slot": {"agent": _read_game_example("snake", "food_chaser.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["food_eaten"] >= 1
    assert metrics["rocks_total"] > 0
    assert metrics["finish_reason"] in {"crash", "no_safe_food", "turn_limit"}
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"][0][0] == -1
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert {"x", "y"}.issubset(frame["head"])

    spawned_food_ticks = {0} | {event["tick"] for event in payload["events"] if event.get("type") == "food"}
    frames_by_tick = {entry["tick"]: entry["frame"] for entry in payload["frames"]}
    for tick in spawned_food_ticks:
        food = frames_by_tick[tick].get("food")
        if food is None:
            continue
        board = frames_by_tick[tick]["board"]
        blocked = {
            (x, y)
            for x, column in enumerate(board)
            for y, value in enumerate(column)
            if value == -1
        }
        assert (food["x"], food["y"]) in engine._non_dead_end_cells(blocked)


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
        "        if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] != -1:\n"
        "            direction = candidate\n"
        "            return candidate\n"
        "    return direction\n"
    )

    payload = engine.run({"run_id": "snake-long-run-test", "codes_by_slot": {"agent": code}})
    metrics = payload["metrics"]

    assert payload["status"] == "finished"
    assert metrics["turns"] > 10
    assert metrics["finish_reason"] in {"crash", "no_safe_food", "turn_limit"}
    assert not (metrics["food_eaten"] == 10 and metrics["alive"] is True and metrics["won"] is True)


def test_pacman_demo_uses_matrix_contract_and_collects_dots() -> None:
    engine = _load_module(_repo_root() / "games" / "pacman" / "engine.py", "pacman_engine_test")
    payload = engine.run(
        {
            "run_id": "pacman-test",
            "codes_by_slot": {"agent": _read_game_example("pacman", "nearest_dot.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "pacman-other-seed",
            "codes_by_slot": {"agent": _read_game_example("pacman", "nearest_dot.py")},
        }
    )

    metrics = payload["metrics"]
    first_frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["dots_collected"] > 0
    assert metrics["score"] > 0
    assert "compile_error" not in metrics
    assert isinstance(first_frame["board"], list)
    assert first_frame["board"][0][0] == -1
    assert metrics["walls_total"] > 0
    assert first_frame["board"] != other["frames"][0]["frame"]["board"]
    assert {"x", "y"}.issubset(first_frame["pacman"])


def test_ice_slide_demo_reaches_exit() -> None:
    engine = _load_module(_repo_root() / "games" / "ice_slide" / "engine.py", "ice_slide_engine_test")
    payload = engine.run(
        {
            "run_id": "ice-slide-test",
            "codes_by_slot": {"agent": _read_game_example("ice_slide", "bfs_slider.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["reached_exit"] is True
    assert metrics["score"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert any(cell == 1 for row in frame["board"] for cell in row)
    other = engine.run(
        {
            "run_id": "ice-slide-other-seed",
            "codes_by_slot": {"agent": _read_game_example("ice_slide", "bfs_slider.py")},
        }
    )
    assert frame["board"] != other["frames"][0]["frame"]["board"]


def test_courier_demo_delivers_all_packages() -> None:
    engine = _load_module(_repo_root() / "games" / "courier" / "engine.py", "courier_engine_test")
    payload = engine.run(
        {
            "run_id": "courier-test",
            "codes_by_slot": {"agent": _read_game_example("courier", "bfs_courier.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["completed"] is True
    assert metrics["delivered"] == metrics["packages_total"]
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)
    other = engine.run(
        {
            "run_id": "courier-other-seed",
            "codes_by_slot": {"agent": _read_game_example("courier", "bfs_courier.py")},
        }
    )
    assert metrics["walls_total"] > 0
    assert frame["board"] != other["frames"][0]["frame"]["board"]


def test_robot_vacuum_demo_cleans_random_room() -> None:
    engine = _load_module(_repo_root() / "games" / "robot_vacuum" / "engine.py", "robot_vacuum_engine_test")
    payload = engine.run(
        {
            "run_id": "robot-vacuum-test",
            "codes_by_slot": {"agent": _read_game_example("robot_vacuum", "bfs_cleaner.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "robot-vacuum-other-seed",
            "codes_by_slot": {"agent": _read_game_example("robot_vacuum", "bfs_cleaner.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["cleaned"] > 0
    assert metrics["alive"] is True
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def test_gem_race_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "gem_race" / "engine.py", "gem_race_engine_test")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "gem-race-test",
            "team_id": "team-red",
            "codes_by_slot": {
                "red": _read_game_example("gem_race", "greedy_red.py"),
                "blue": _read_game_example("gem_race", "greedy_blue.py"),
            },
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "gem-race-other-seed",
            "team_id": "team-red",
            "codes_by_slot": {
                "red": _read_game_example("gem_race", "greedy_red.py"),
                "blue": _read_game_example("gem_race", "greedy_blue.py"),
            },
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-red", "team-blue"}
    assert metrics["gems_total"] == 14
    assert metrics["walls_total"] > 0
    assert sum(metrics["collected"].values()) > 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]


def test_fire_rescue_demo_extinguishes_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "fire_rescue" / "engine.py", "fire_rescue_engine_test")
    payload = engine.run(
        {
            "run_id": "fire-rescue-test",
            "codes_by_slot": {"agent": _read_game_example("fire_rescue", "bfs_firefighter.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "fire-rescue-other-seed",
            "codes_by_slot": {"agent": _read_game_example("fire_rescue", "bfs_firefighter.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["completed"] is True
    assert metrics["extinguished"] == metrics["fires_total"]
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["fire_spread_every"] == 12
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def test_territory_duel_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "territory_duel" / "engine.py", "territory_duel_engine_test")
    demo_code = _read_game_example("territory_duel", "demo.py")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "territory-duel-test",
            "participants": [
                {"team_id": "team-green", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-purple", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-orange", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-blue", "codes_by_slot": {"player": demo_code}},
            ],
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "territory-duel-other-seed",
            "participants": [
                {"team_id": "team-green", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-purple", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-orange", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-blue", "codes_by_slot": {"player": demo_code}},
            ],
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-green", "team-purple", "team-orange", "team-blue"}
    assert metrics["active_slots"] == ["green", "purple", "orange", "blue"]
    assert metrics["painted_total"] > 2
    assert metrics["walls_total"] > 0
    assert sum(metrics["area"].values()) == metrics["painted_total"]
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]


def test_flood_escape_demo_reaches_exit_on_dynamic_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "flood_escape" / "engine.py", "flood_escape_engine_test")
    payload = engine.run(
        {
            "run_id": "flood-escape-test",
            "codes_by_slot": {"agent": _read_game_example("flood_escape", "bfs_escape.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "flood-escape-other-seed",
            "codes_by_slot": {"agent": _read_game_example("flood_escape", "bfs_escape.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["alive"] is True
    assert metrics["walls_total"] > 0
    assert metrics["water_cells"] >= 3
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == -2 for row in frame["board"] for cell in row)


def test_trap_coin_duel_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "trap_coin_duel" / "engine.py", "trap_coin_duel_engine_test")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "trap-coin-test",
            "team_id": "team-gold",
            "codes_by_slot": {
                "gold": _read_game_example("trap_coin_duel", "gold_bfs.py"),
                "silver": _read_game_example("trap_coin_duel", "silver_bfs.py"),
            },
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "trap-coin-other-seed",
            "team_id": "team-gold",
            "codes_by_slot": {
                "gold": _read_game_example("trap_coin_duel", "gold_bfs.py"),
                "silver": _read_game_example("trap_coin_duel", "silver_bfs.py"),
            },
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-gold", "team-silver"}
    assert metrics["coins_total"] == 16
    assert metrics["traps_total"] == 8
    assert metrics["walls_total"] > 0
    assert sum(metrics["collected"].values()) > 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == -3 for row in frame["board"] for cell in row)
    assert any(cell == -4 for row in frame["board"] for cell in row)
    assert len(frame["traps"]) == metrics["traps_total"]


def test_space_miner_demo_mines_ore_and_returns_to_base() -> None:
    engine = _load_module(_repo_root() / "games" / "space_miner" / "engine.py", "space_miner_engine_test")
    payload = engine.run(
        {
            "run_id": "space-miner-test",
            "codes_by_slot": {"agent": _read_game_example("space_miner", "bfs_miner.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "space-miner-other-seed",
            "codes_by_slot": {"agent": _read_game_example("space_miner", "bfs_miner.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["completed"] is True
    assert metrics["alive"] is True
    assert metrics["ore_mined"] == metrics["ore_total"]
    assert metrics["walls_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def test_capture_flag_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "capture_flag" / "engine.py", "capture_flag_engine_test")
    demo_code = _read_game_example("capture_flag", "demo.py")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "capture-flag-test",
            "participants": [
                {"team_id": "team-red", "display_name": "Red", "codes_by_slot": {"player": demo_code}, "run_id": "capture-flag-red"},
                {"team_id": "team-blue", "display_name": "Blue", "codes_by_slot": {"player": demo_code}, "run_id": "capture-flag-blue"},
                {"team_id": "team-green", "display_name": "Green", "codes_by_slot": {"player": demo_code}, "run_id": "capture-flag-green"},
                {"team_id": "team-yellow", "display_name": "Yellow", "codes_by_slot": {"player": demo_code}, "run_id": "capture-flag-yellow"},
            ],
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "capture-flag-other-seed",
            "participants": [
                {"team_id": "team-red", "display_name": "Red", "codes_by_slot": {"player": demo_code}, "run_id": "capture-other-red"},
                {"team_id": "team-blue", "display_name": "Blue", "codes_by_slot": {"player": demo_code}, "run_id": "capture-other-blue"},
                {"team_id": "team-green", "display_name": "Green", "codes_by_slot": {"player": demo_code}, "run_id": "capture-other-green"},
                {"team_id": "team-yellow", "display_name": "Yellow", "codes_by_slot": {"player": demo_code}, "run_id": "capture-other-yellow"},
            ],
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-red", "team-blue", "team-green", "team-yellow"}
    assert metrics["active_slots"] == ["red", "blue", "green", "yellow"]
    assert metrics["walls_total"] > 0
    assert sum(metrics["captures"].values()) > 0 or metrics["flag_carrier"] in metrics["active_slots"]
    assert metrics["built_walls"] >= 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)
    assert set(frame["bases"]) == {"red", "blue", "green", "yellow"}


def test_portal_escape_demo_reaches_exit_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "portal_escape" / "engine.py", "portal_escape_engine_test")
    payload = engine.run(
        {
            "run_id": "portal-escape-test",
            "codes_by_slot": {"agent": _read_game_example("portal_escape", "bfs_portal.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "portal-escape-other-seed",
            "codes_by_slot": {"agent": _read_game_example("portal_escape", "bfs_portal.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["walls_total"] > 0
    assert metrics["portal_pairs_total"] >= 4
    assert metrics["portals_total"] == metrics["portal_pairs_total"] * 2
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert sum(cell == 1 for column in frame["board"] for cell in column) == 1
    portal_values = [cell for column in frame["board"] for cell in column if cell > 1]
    assert sorted(set(portal_values)) == [2, 3, 4, 5]
    assert all(portal_values.count(value) == 2 for value in set(portal_values))
    assert not _portal_escape_reachable_without_portals(frame["board"])


def _portal_escape_reachable_without_portals(board: list[list[int]]) -> bool:
    start = (1, 1)
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        x, y = queue[head]
        head += 1
        if board[x][y] == 1:
            return True
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            if board[nx][ny] == -1 or (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    return False


def test_switch_maze_demo_flips_switch_and_escapes_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "switch_maze" / "engine.py", "switch_maze_engine_test")
    payload = engine.run(
        {
            "run_id": "switch-maze-test",
            "codes_by_slot": {"agent": _read_game_example("switch_maze", "bfs_switch.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "switch-maze-other-seed",
            "codes_by_slot": {"agent": _read_game_example("switch_maze", "bfs_switch.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["switched"] is True
    assert metrics["switches_total"] == 6
    assert metrics["doors_total"] == 48
    assert metrics["walls_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert len(frame["board"]) == 22
    assert len(frame["board"][0]) == 18
    assert _switch_maze_door_columns(frame["board"]) >= 3
    assert not _switch_maze_reachable_without_switch(frame["board"])
    assert any(cell == -2 for row in frame["board"] for cell in row)
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def _switch_maze_door_columns(board: list[list[int]]) -> int:
    height = len(board[0]) if board else 0
    return sum(1 for column in board if sum(cell == -2 for cell in column) >= height - 2)


def _switch_maze_reachable_without_switch(board: list[list[int]]) -> bool:
    queue = [(1, 1)]
    seen = {(1, 1)}
    head = 0
    while head < len(queue):
        x, y = queue[head]
        head += 1
        if board[x][y] == 2:
            return True
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx = x + dx
            ny = y + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            if board[nx][ny] in (-2, -1) or (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    return False


def test_tag_arena_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "tag_arena" / "engine.py", "tag_arena_engine_test")
    runner_code = _read_game_example("tag_arena", "runner_bfs.py")
    hunter_code = _read_game_example("tag_arena", "hunter_bfs.py")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "tag-arena-test",
            "participants": [
                {"team_id": "team-amber", "display_name": "Amber", "codes_by_slot": {"runner": runner_code, "hunter": hunter_code}, "run_id": "tag-amber"},
                {"team_id": "team-teal", "display_name": "Teal", "codes_by_slot": {"runner": runner_code, "hunter": hunter_code}, "run_id": "tag-teal"},
            ],
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "tag-arena-other-seed",
            "participants": [
                {"team_id": "team-amber", "display_name": "Amber", "codes_by_slot": {"runner": runner_code, "hunter": hunter_code}, "run_id": "tag-other-amber"},
                {"team_id": "team-teal", "display_name": "Teal", "codes_by_slot": {"runner": runner_code, "hunter": hunter_code}, "run_id": "tag-other-teal"},
            ],
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-amber", "team-teal"}
    assert metrics["active_teams"] == ["amber", "teal"]
    assert metrics["stars_total"] == 10
    assert metrics["walls_total"] > 0
    assert sum(metrics["catches"].values()) > 0 or sum(metrics["stars_collected"].values()) > 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert set(frame["positions"]) == {"amber_runner", "amber_hunter", "teal_runner", "teal_hunter"}
    assert frame["positions"]["amber_runner"]["role"] == "runner"
    assert frame["positions"]["amber_hunter"]["role"] == "hunter"
    assert frame["labels"]["amber"] == "Amber"


def test_crystal_lamps_demo_lights_all_lamps_and_escapes_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "crystal_lamps" / "engine.py", "crystal_lamps_engine_test")
    payload = engine.run(
        {
            "run_id": "crystal-lamps-test",
            "codes_by_slot": {"agent": _read_game_example("crystal_lamps", "bfs_lamps.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "crystal-lamps-other-seed",
            "codes_by_slot": {"agent": _read_game_example("crystal_lamps", "bfs_lamps.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["lamps_lit"] == metrics["lamps_total"]
    assert metrics["walls_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert sum(cell == 1 for row in frame["board"] for cell in row) == metrics["lamps_total"]
    assert not any(cell == 2 for row in frame["board"] for cell in row)
    final_board = payload["frames"][-1]["frame"]["board"]
    assert any(cell == 2 for row in final_board for cell in row)
    assert sum(cell == 3 for row in final_board for cell in row) == metrics["lamps_total"]


def test_crystal_lamps_player_board_hides_unknown_cells() -> None:
    engine = _load_module(_repo_root() / "games" / "crystal_lamps" / "engine.py", "crystal_lamps_visibility_test")
    code = (
        "printed = False\n"
        "def make_move(x, y, board, lamps_lit):\n"
        "    global printed\n"
        "    if not printed and any(cell == -9 for column in board for cell in column):\n"
        "        print('unknown-cells-visible')\n"
        "        printed = True\n"
        "    return 'stay'\n"
    )

    payload = engine.run({"run_id": "crystal-visibility-test", "codes_by_slot": {"agent": code}})

    assert any(event.get("message") == "unknown-cells-visible" for event in payload["events"])


def test_invalid_actions_have_readable_messages() -> None:
    engine = _load_module(_repo_root() / "games" / "coins_right_down" / "engine.py", "coins_error_message_test")
    code = "def make_move(x, y, board):\n    return 'banana'\n"

    payload = engine.run({"run_id": "error-message-test", "codes_by_slot": {"agent": code}})
    invalid_events = [event for event in payload["events"] if event.get("type") == "invalid_action"]

    assert invalid_events
    assert all(isinstance(event.get("message"), str) and event["message"] for event in invalid_events)


def test_river_planks_demo_escapes_with_resource_state_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "river_planks" / "engine.py", "river_planks_engine_test")
    payload = engine.run(
        {
            "run_id": "river-planks-test",
            "codes_by_slot": {"agent": _read_game_example("river_planks", "bfs_planks.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "river-planks-other-seed",
            "codes_by_slot": {"agent": _read_game_example("river_planks", "bfs_planks.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["planks_total"] == 7
    assert metrics["water_total"] == 48
    assert metrics["walls_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert len(frame["board"]) == 22
    assert len(frame["board"][0]) == 18
    assert _river_planks_water_columns(frame["board"]) >= 3
    assert not _river_planks_reachable_without_planks(frame["board"])
    assert any(cell == -2 for row in frame["board"] for cell in row)
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def _river_planks_water_columns(board: list[list[int]]) -> int:
    height = len(board[0]) if board else 0
    return sum(1 for column in board if sum(cell == -2 for cell in column) >= height - 2)


def _river_planks_reachable_without_planks(board: list[list[int]]) -> bool:
    queue = [(1, 1)]
    seen = {(1, 1)}
    head = 0
    while head < len(queue):
        x, y = queue[head]
        head += 1
        if board[x][y] == 2:
            return True
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx = x + dx
            ny = y + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            if board[nx][ny] in (-2, -1) or (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    return False


def test_oxygen_maze_demo_reaches_exit_with_oxygen_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "oxygen_maze" / "engine.py", "oxygen_maze_engine_test")
    payload = engine.run(
        {
            "run_id": "oxygen-maze-test",
            "codes_by_slot": {"agent": _read_game_example("oxygen_maze", "bfs_oxygen.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "oxygen-maze-other-seed",
            "codes_by_slot": {"agent": _read_game_example("oxygen_maze", "bfs_oxygen.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["alive"] is True
    assert metrics["refills"] > 0
    assert metrics["stations_total"] == 5
    assert metrics["walls_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert len(frame["board"]) == 24
    assert len(frame["board"][0]) == 20
    assert frame["oxygen_max"] == 28
    assert not _oxygen_maze_reachable_without_refill(frame["board"], oxygen_max=frame["oxygen_max"])
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def _oxygen_maze_reachable_without_refill(board: list[list[int]], oxygen_max: int) -> bool:
    queue = [((1, 1), 0)]
    seen = {(1, 1)}
    head = 0
    while head < len(queue):
        (x, y), distance = queue[head]
        head += 1
        if board[x][y] == 2:
            return distance < oxygen_max
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx = x + dx
            ny = y + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            if board[nx][ny] == -1 or (nx, ny) in seen:
                continue
            next_distance = distance + 1
            if next_distance >= oxygen_max:
                continue
            seen.add((nx, ny))
            queue.append(((nx, ny), next_distance))
    return False


def test_gate_keys_demo_opens_gates_and_escapes_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "gate_keys" / "engine.py", "gate_keys_engine_test")
    payload = engine.run(
        {
            "run_id": "gate-keys-test",
            "codes_by_slot": {"agent": _read_game_example("gate_keys", "bfs_gate_keys.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "gate-keys-other-seed",
            "codes_by_slot": {"agent": _read_game_example("gate_keys", "bfs_gate_keys.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["keys_total"] == 7
    assert metrics["gates_total"] == 9
    assert metrics["gates_opened"] >= 3
    assert metrics["walls_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert len(frame["board"]) == 22
    assert len(frame["board"][0]) == 18
    assert _gate_keys_gate_columns(frame["board"]) >= 3
    assert not _gate_keys_reachable_with_few_gates(frame["board"], max_gates=2)
    assert any(cell == -2 for row in frame["board"] for cell in row)
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def _gate_keys_gate_columns(board: list[list[int]]) -> int:
    height = len(board[0]) if board else 0
    return sum(1 for column in board if sum(cell in (-2, -1) for cell in column) >= height - 2 and any(cell == -2 for cell in column))


def _gate_keys_reachable_with_few_gates(board: list[list[int]], max_gates: int) -> bool:
    queue = [((1, 1), 0)]
    seen = {((1, 1), 0)}
    head = 0
    while head < len(queue):
        (x, y), opened = queue[head]
        head += 1
        if board[x][y] == 2:
            return True
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx = x + dx
            ny = y + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            cell = board[nx][ny]
            if cell == -1:
                continue
            next_opened = opened + (1 if cell == -2 else 0)
            if next_opened > max_gates:
                continue
            state = ((nx, ny), next_opened)
            if state in seen:
                continue
            seen.add(state)
            queue.append(state)
    return False


def test_energy_race_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "energy_race" / "engine.py", "energy_race_engine_test")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "energy-race-test",
            "team_id": "team-solar",
            "codes_by_slot": {
                "solar": _read_game_example("energy_race", "solar_bfs.py"),
                "lunar": _read_game_example("energy_race", "lunar_bfs.py"),
            },
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "energy-race-other-seed",
            "team_id": "team-solar",
            "codes_by_slot": {
                "solar": _read_game_example("energy_race", "solar_bfs.py"),
                "lunar": _read_game_example("energy_race", "lunar_bfs.py"),
            },
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-solar", "team-lunar"}
    assert metrics["energy_total"] == 14
    assert metrics["chargers_total"] == 4
    assert metrics["walls_total"] > 0
    assert sum(metrics["collected"].values()) > 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def test_garden_harvest_demo_delivers_all_crops_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "garden_harvest" / "engine.py", "garden_harvest_engine_test")
    payload = engine.run(
        {
            "run_id": "garden-harvest-test",
            "codes_by_slot": {"agent": _read_game_example("garden_harvest", "bfs_harvester.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "garden-harvest-other-seed",
            "codes_by_slot": {"agent": _read_game_example("garden_harvest", "bfs_harvester.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["completed"] is True
    assert metrics["delivered"] == metrics["crops_total"]
    assert metrics["capacity"] == 3
    assert metrics["walls_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def test_apple_market_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "apple_market" / "engine.py", "apple_market_engine_test")
    demo_code = _read_game_example("apple_market", "demo.py")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "apple-market-test",
            "participants": [
                {"team_id": "team-alpha", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-beta", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-gamma", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-delta", "codes_by_slot": {"player": demo_code}},
            ],
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "apple-market-other-seed",
            "participants": [
                {"team_id": "team-alpha", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-beta", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-gamma", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-delta", "codes_by_slot": {"player": demo_code}},
            ],
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-alpha", "team-beta", "team-gamma", "team-delta"}
    assert metrics["active_slots"] == ["north_west", "north_east", "south_west", "south_east"]
    assert metrics["initial_apples"] == 8
    assert metrics["apples_total"] >= metrics["initial_apples"]
    assert metrics["apples_spawned_total"] == metrics["apples_total"]
    assert metrics["turn_limit"] == 150
    assert metrics["spawn_interval"] == 10
    assert metrics["spawn_batch"] == 2
    assert metrics["max_apples_on_board"] == 12
    assert metrics["capacity"] == 2
    assert metrics["walls_total"] > 0
    assert sum(metrics["delivered"].values()) > 0
    assert set(metrics["throws"]) == set(metrics["active_slots"])
    assert set(metrics["frozen"]) == set(metrics["active_slots"])
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert frame["tree"] == {"x": 7, "y": 7}
    assert frame["board"][7][7] == 3
    assert frame["turn_limit"] == 150
    assert all(value == 0 for value in frame["carrying"].values())
    assert all(value == 0 for value in frame["delivered"].values())
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)
    delivered_events = [event for event in payload["events"] if event.get("type") == "delivered"]
    assert delivered_events
    first_delivery = delivered_events[0]
    delivery_frame = payload["frames"][int(first_delivery["tick"])]["frame"]
    slot = str(first_delivery["slot"])
    assert delivery_frame["carrying"][slot] == 0
    assert delivery_frame["delivered"][slot] > 0


def test_apple_market_throw_requires_carried_apple(monkeypatch) -> None:
    engine = _load_module(_repo_root() / "games" / "apple_market" / "engine.py", "apple_market_empty_throw_test")

    monkeypatch.setattr(engine, "_MAX_TURNS", 1)
    monkeypatch.setattr(
        engine,
        "_build_map",
        lambda _ctx, _slots: {"walls": set(engine._BORDER_WALLS), "apples": set(), "spawn_cells": []},
    )

    code = "def make_move(x, y, board, carrying):\n    return 'throw_right'\n"
    payload = engine.run(
        {
            "run_id": "apple-market-empty-throw",
            "participants": [
                {"team_id": "team-alpha", "codes_by_slot": {"player": code}},
                {"team_id": "team-beta", "codes_by_slot": {"player": "def make_move(x, y, board, carrying):\n    return 'stay'\n"}},
            ],
        }
    )

    frame = payload["frames"][1]["frame"]

    assert payload["metrics"]["throws"]["north_west"] == 0
    assert payload["metrics"]["invalid_moves"]["north_west"] == 1
    assert frame["carrying"]["north_west"] == 0
    assert frame["projectiles"] == []
    assert any(event.get("type") == "invalid_throw" and event.get("reason") == "empty_hands" for event in payload["events"])
    assert not any(event.get("type") == "throw" for event in payload["events"])


def test_apple_market_throw_spends_apple_and_freezes_hit_player(monkeypatch) -> None:
    engine = _load_module(_repo_root() / "games" / "apple_market" / "engine.py", "apple_market_throw_hit_test")

    starts = dict(engine._STARTS)
    starts["south_east"] = (4, 1)
    monkeypatch.setattr(engine, "_STARTS", starts)
    monkeypatch.setattr(engine, "_MAX_TURNS", 2)
    monkeypatch.setattr(
        engine,
        "_build_map",
        lambda _ctx, _slots: {"walls": set(engine._BORDER_WALLS), "apples": {(2, 1)}, "spawn_cells": []},
    )

    thrower_code = (
        "def make_move(x, y, board, carrying):\n"
        "    if carrying == 0:\n"
        "        return 'right'\n"
        "    return 'throw_right'\n"
    )
    payload = engine.run(
        {
            "run_id": "apple-market-spend-and-freeze",
            "participants": [
                {"team_id": "team-alpha", "display_name": "Бросающий", "codes_by_slot": {"player": thrower_code}},
                {"team_id": "team-beta", "display_name": "Цель", "codes_by_slot": {"player": "def make_move(x, y, board, carrying):\n    return 'stay'\n"}},
            ],
        }
    )

    after_collect = payload["frames"][1]["frame"]
    after_throw = payload["frames"][2]["frame"]
    projectile = after_throw["projectiles"][0]

    assert after_collect["carrying"]["north_west"] == 1
    assert after_throw["carrying"]["north_west"] == 0
    assert after_throw["throws"]["north_west"] == 1
    assert after_throw["frozen"]["south_east"] == 3
    assert projectile["slot"] == "north_west"
    assert projectile["start"] == {"x": 2, "y": 1}
    assert projectile["hit"] == "south_east"
    assert projectile["spent_apple"] is True
    assert projectile["carrying_after"] == 0
    assert any(event.get("type") == "freeze" and event.get("slot") == "south_east" for event in payload["events"])


def test_box_buttons_demo_solves_random_sokoban_map() -> None:
    engine = _load_module(_repo_root() / "games" / "box_buttons" / "engine.py", "box_buttons_engine_test")
    payload = engine.run(
        {
            "run_id": "box-buttons-test",
            "codes_by_slot": {"agent": _read_game_example("box_buttons", "bfs_boxes.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "box-buttons-other-seed",
            "codes_by_slot": {"agent": _read_game_example("box_buttons", "bfs_boxes.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["completed"] is True
    assert metrics["boxes_on_targets"] == metrics["boxes_total"]
    assert metrics["targets_total"] == 2
    assert metrics["walls_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def test_ice_treasure_duel_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(
        _repo_root() / "games" / "ice_treasure_duel" / "engine.py",
        "ice_treasure_duel_engine_test",
    )
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "ice-treasure-test",
            "team_id": "team-ruby",
            "codes_by_slot": {
                "ruby": _read_game_example("ice_treasure_duel", "ruby_slider.py"),
                "sapphire": _read_game_example("ice_treasure_duel", "sapphire_slider.py"),
            },
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "ice-treasure-other-seed",
            "team_id": "team-ruby",
            "codes_by_slot": {
                "ruby": _read_game_example("ice_treasure_duel", "ruby_slider.py"),
                "sapphire": _read_game_example("ice_treasure_duel", "sapphire_slider.py"),
            },
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-ruby", "team-sapphire"}
    assert metrics["crystals_total"] == 12
    assert metrics["walls_total"] > 0
    assert sum(metrics["collected"].values()) > 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == -2 for row in frame["board"] for cell in row)


def test_knight_coins_demo_collects_coins_and_escapes_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "knight_coins" / "engine.py", "knight_coins_engine_test")
    payload = engine.run(
        {
            "run_id": "knight-coins-test",
            "codes_by_slot": {"agent": _read_game_example("knight_coins", "bfs_knight.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "knight-coins-other-seed",
            "codes_by_slot": {"agent": _read_game_example("knight_coins", "bfs_knight.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["coins_collected"] == metrics["coins_total"]
    assert metrics["holes_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == 2 for row in frame["board"] for cell in row)


def test_knight_duel_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(_repo_root() / "games" / "knight_duel" / "engine.py", "knight_duel_engine_test")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "knight-duel-test",
            "team_id": "team-white",
            "codes_by_slot": {
                "white": _read_game_example("knight_duel", "white_bfs.py"),
                "black": _read_game_example("knight_duel", "black_bfs.py"),
            },
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "knight-duel-other-seed",
            "team_id": "team-white",
            "codes_by_slot": {
                "white": _read_game_example("knight_duel", "white_bfs.py"),
                "black": _read_game_example("knight_duel", "black_bfs.py"),
            },
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-white", "team-black"}
    assert metrics["stars_total"] == 12
    assert metrics["holes_total"] > 0
    assert sum(metrics["collected"].values()) > 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == -2 for row in frame["board"] for cell in row)


def test_conveyor_escape_demo_reaches_exit_on_random_map() -> None:
    engine = _load_module(
        _repo_root() / "games" / "conveyor_escape" / "engine.py",
        "conveyor_escape_engine_test",
    )
    payload = engine.run(
        {
            "run_id": "conveyor-escape-test",
            "codes_by_slot": {"agent": _read_game_example("conveyor_escape", "bfs_conveyor.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "conveyor-escape-other-seed",
            "codes_by_slot": {"agent": _read_game_example("conveyor_escape", "bfs_conveyor.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["walls_total"] > 0
    assert metrics["conveyors_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell in (2, 3, 4, 5) for row in frame["board"] for cell in row)


def test_conveyor_gem_duel_demo_returns_competitive_scores_on_random_map() -> None:
    engine = _load_module(
        _repo_root() / "games" / "conveyor_gem_duel" / "engine.py",
        "conveyor_gem_duel_engine_test",
    )
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "conveyor-gem-duel-test",
            "team_id": "team-orange",
            "codes_by_slot": {
                "orange": _read_game_example("conveyor_gem_duel", "orange_bfs.py"),
                "violet": _read_game_example("conveyor_gem_duel", "violet_bfs.py"),
            },
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "conveyor-gem-duel-other-seed",
            "team_id": "team-orange",
            "codes_by_slot": {
                "orange": _read_game_example("conveyor_gem_duel", "orange_bfs.py"),
                "violet": _read_game_example("conveyor_gem_duel", "violet_bfs.py"),
            },
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-orange", "team-violet"}
    assert metrics["gems_total"] == 14
    assert metrics["walls_total"] > 0
    assert metrics["conveyors_total"] > 0
    assert sum(metrics["collected"].values()) > 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell in (2, 3, 4, 5) for row in frame["board"] for cell in row)
    assert any(cell == -2 for row in frame["board"] for cell in row)


def test_road_crossing_demo_reaches_finish_on_dynamic_random_map() -> None:
    engine = _load_module(
        _repo_root() / "games" / "road_crossing" / "engine.py",
        "road_crossing_engine_test",
    )
    payload = engine.run(
        {
            "run_id": "road-crossing-test",
            "codes_by_slot": {"agent": _read_game_example("road_crossing", "time_bfs.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "road-crossing-other-seed",
            "codes_by_slot": {"agent": _read_game_example("road_crossing", "time_bfs.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["cars_total"] == 18
    assert metrics["lanes_total"] == 9
    assert metrics["car_hits"] == 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == -1 for row in frame["board"] for cell in row)
    assert any(cell == 1 for row in frame["board"] for cell in row)


def test_road_star_duel_demo_returns_competitive_scores_on_dynamic_random_map() -> None:
    engine = _load_module(
        _repo_root() / "games" / "road_star_duel" / "engine.py",
        "road_star_duel_engine_test",
    )
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "road-star-duel-test",
            "team_id": "team-red",
            "codes_by_slot": {
                "red": _read_game_example("road_star_duel", "red_time_bfs.py"),
                "blue": _read_game_example("road_star_duel", "blue_time_bfs.py"),
            },
        }
    )
    other = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "road-star-duel-other-seed",
            "team_id": "team-red",
            "codes_by_slot": {
                "red": _read_game_example("road_star_duel", "red_time_bfs.py"),
                "blue": _read_game_example("road_star_duel", "blue_time_bfs.py"),
            },
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload
    assert set(payload["scores"]) == {"team-red", "team-blue"}
    assert metrics["stars_total"] == 14
    assert metrics["cars_total"] == 18
    assert sum(metrics["collected"].values()) > 0
    assert "compile_errors" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == -1 for row in frame["board"] for cell in row)
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell == -2 for row in frame["board"] for cell in row)


def test_jump_maze_demo_reaches_exit_on_random_map() -> None:
    engine = _load_module(
        _repo_root() / "games" / "jump_maze" / "engine.py",
        "jump_maze_engine_test",
    )
    payload = engine.run(
        {
            "run_id": "jump-maze-test",
            "codes_by_slot": {"agent": _read_game_example("jump_maze", "bfs_jumps.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "jump-maze-other-seed",
            "codes_by_slot": {"agent": _read_game_example("jump_maze", "bfs_jumps.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["walls_total"] > 0
    assert metrics["jumps_total"] > 0
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell in (2, 3) for row in frame["board"] for cell in row)


def test_blinking_bridge_demo_reaches_exit_on_dynamic_random_map() -> None:
    engine = _load_module(
        _repo_root() / "games" / "blinking_bridge" / "engine.py",
        "blinking_bridge_engine_test",
    )
    payload = engine.run(
        {
            "run_id": "blinking-bridge-test",
            "codes_by_slot": {"agent": _read_game_example("blinking_bridge", "time_bfs.py")},
        }
    )
    other = engine.run(
        {
            "run_id": "blinking-bridge-other-seed",
            "codes_by_slot": {"agent": _read_game_example("blinking_bridge", "time_bfs.py")},
        }
    )

    metrics = payload["metrics"]
    frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert metrics["escaped"] is True
    assert metrics["walls_total"] > 0
    assert metrics["bridges_total"] >= 28
    assert metrics["bridge_steps"] >= 3
    assert "compile_error" not in metrics
    assert isinstance(frame["board"], list)
    assert frame["board"] != other["frames"][0]["frame"]["board"]
    assert len(frame["board"]) == 16
    assert len(frame["board"][0]) == 16
    assert not _blinking_bridge_reachable_with_few_bridges(frame["board"], max_bridge_steps=1)
    assert any(cell == 1 for row in frame["board"] for cell in row)
    assert any(cell in (-2, 2) for row in frame["board"] for cell in row)


def _blinking_bridge_reachable_with_few_bridges(board: list[list[int]], max_bridge_steps: int) -> bool:
    queue = [((1, 1), 0)]
    seen = {((1, 1), 0)}
    head = 0
    while head < len(queue):
        (x, y), bridge_steps = queue[head]
        head += 1
        if board[x][y] == 1:
            return True
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx = x + dx
            ny = y + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            cell = board[nx][ny]
            if cell == -1:
                continue
            next_bridge_steps = bridge_steps + (1 if cell in (-2, 2) else 0)
            if next_bridge_steps > max_bridge_steps:
                continue
            state = ((nx, ny), next_bridge_steps)
            if state in seen:
                continue
            seen.add(state)
            queue.append(state)
    return False


def test_multiplayer_snake_demo_returns_scores_for_all_slots() -> None:
    engine = _load_module(
        _repo_root() / "games" / "multiplayer_snake" / "engine.py",
        "multiplayer_snake_engine_test",
    )
    demo_code = _read_game_example("multiplayer_snake", "food_chaser.py")
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "run_id": "multi-snake-test",
            "participants": [
                {"team_id": "team-alpha", "codes_by_slot": {"player": demo_code}},
                {"team_id": "team-beta", "codes_by_slot": {"player": demo_code}},
            ],
        }
    )

    metrics = payload["metrics"]
    first_frame = payload["frames"][0]["frame"]

    assert payload["status"] == "finished"
    assert set(payload["scores"]) == {"team-alpha", "team-beta"}
    assert set(payload["placements"]) == set(payload["scores"])
    assert set(metrics["winner_slots"]).issubset({"snake_1", "snake_2"})
    assert set(metrics["food_eaten"]) == {"snake_1", "snake_2"}
    assert first_frame["board"][0][0] == -1
    assert "compile_errors" not in metrics
