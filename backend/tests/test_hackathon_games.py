from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from game_catalog.infrastructure.manifest_loader import load_game_manifest


ROOT = Path(__file__).resolve().parents[2]
GAMES = ("planet_wars", "defender_duel", "territory_capture", "bomb_arena")


def load(game):
    spec = importlib.util.spec_from_file_location(game, ROOT / "games" / game / "engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context(game, count=2, source=None):
    root = ROOT / "games" / game
    if source is None:
        manifest = load_game_manifest(root / "manifest.yaml")
        source = (root / manifest.demo_strategies[0].path).read_text()
    return {"participants": [{"team_id": f"team-{i}", "display_name": f"Команда {i}",
                              "run_id": f"match-{i}", "codes_by_slot": {"player": source}}
                             for i in range(count)]}


@pytest.mark.parametrize("game", GAMES)
def test_hackathon_games_are_available_in_team_catalog(client, game):
    response = client.get("/api/v1/games")
    item = next(g for g in response.json() if g["slug"] == f"{game}_v1")
    assert item["mode"] == "multiplayer"
    game_id = item["game_id"]
    templates = client.get(f"/api/v1/games/{game_id}/templates").json()
    assert [t["slot_key"] for t in templates["templates"]] == ["player"]
    assert "def make_move(state):" in templates["templates"][0]["code"]
    assert templates["demo_strategies"]
    docs = client.get(f"/api/v1/games/{game_id}/docs").json()
    assert "make_move(state)" in docs["links"][0]["content"]
    manifest = load_game_manifest(ROOT / "games" / game / "manifest.yaml")
    assert manifest.match_player_bounds == (2, 2 if game == "defender_duel" else 4)


@pytest.mark.parametrize("game,count", [(g, n) for g in GAMES for n in (2, 3, 4)
                                        if g != "defender_duel" or n == 2])
def test_demo_matches_finish_with_consistent_team_results(game, count):
    engine = load(game)
    ctx = context(game, count)
    result = engine.run(ctx)
    assert result["status"] == "finished"
    assert set(result["scores"]) == {f"team-{i}" for i in range(count)}
    assert result["placements"].keys() == result["scores"].keys()
    assert min(result["placements"].values()) == 1
    assert not result["metrics"].get("compile_errors")
    assert not [e for e in result["events"] if e["type"] == "bot_error"]
    assert result["frames"][0]["tick"] == 0
    assert result["frames"][-1]["phase"] == "finished"
    assert result["frames"][-1]["frame"]["winner_slots"] == result["metrics"]["winner_slots"]
    assert result["metrics"]["turns"] <= engine._MAX_TURNS
    # Same participants see exactly the same generated map and replay on each worker.
    assert result == engine.run({**ctx, "run_id": "a-different-worker-run"})
    json.dumps(result)


@pytest.mark.parametrize("game", GAMES)
def test_packages_execute_without_other_repository_files(game, tmp_path):
    package = tmp_path / game
    shutil.copytree(ROOT / "games" / game, package)
    ctx = context(game, source="def make_move(state):\n    return None\n")
    completed = subprocess.run([sys.executable, str(package / "engine.py")], cwd=tmp_path,
                               env={**os.environ, "AGP_RUN_CONTEXT": json.dumps(ctx)},
                               capture_output=True, text=True, timeout=15, check=True)
    result = json.loads(completed.stdout)
    assert result["status"] == "finished"
    assert result["scores"].keys() == {"team-0", "team-1"}


@pytest.mark.parametrize("game", GAMES)
def test_bot_errors_and_mutation_do_not_break_matches(game, monkeypatch):
    engine = load(game)
    monkeypatch.setattr(engine, "_MAX_TURNS", 3)
    ctx = context(game, source="def make_move(state):\n    state.clear()\n    raise ValueError('broken')\n")
    result = engine.run(ctx)
    assert result["status"] == "finished"
    assert any(event["type"] == "bot_error" for event in result["events"])
    assert result["frames"][0]["frame"]["active_slots"] == ["red", "blue"]
    ctx["participants"][0]["codes_by_slot"]["player"] = "def invalid("
    result = engine.run(ctx)
    assert "red" in result["metrics"]["compile_errors"]


def test_planet_orders_use_starting_garrison_and_one_fleet_per_source():
    engine = load("planet_wars")
    planets = [{"id": 0, "owner": "red", "ships": 10, "production": 3, "x": 0, "y": 0},
               {"id": 1, "owner": None, "ships": 4, "production": 1, "x": 6, "y": 0}]
    fleets = []
    engine._launch(planets, fleets, {"red": [{"from": 0, "to": 1, "ships": 11},
                                           {"from": 0, "to": 1, "ships": 7},
                                           {"from": 0, "to": 1, "ships": 2}]}, 0)
    assert planets[0]["ships"] == 3
    assert len(fleets) == 1
    engine._advance(planets, fleets)
    assert planets[0]["ships"] == 6
    assert (planets[1]["owner"], planets[1]["ships"]) == ("red", 3)
    assert not fleets


@pytest.mark.parametrize("garrison,arrivals,expected", [
    (15, {"red": 10}, ("blue", 5)),
    (15, {"red": 20}, ("red", 5)),
    (15, {"red": 15}, (None, 0)),
    (15, {"red": 20, "green": 10}, (None, 0)),
    (15, {"red": 40, "green": 10}, ("red", 15)),
    (15, {"blue": 7, "red": 20}, ("blue", 2)),
])
def test_planet_arrivals_resolve_all_sides_together(garrison, arrivals, expected):
    engine = load("planet_wars")
    planets = [{"id": 0, "owner": "blue", "ships": garrison, "production": 0}]
    fleets = [{"owner": s, "ships": n, "to": 0, "eta": 1} for s, n in arrivals.items()]
    engine._advance(planets, fleets)
    assert (planets[0]["owner"], planets[0]["ships"]) == expected


def test_planet_team_with_only_a_fleet_is_still_alive():
    engine = load("planet_wars")
    _, ships, alive = engine._totals(["red", "blue"], [], [{"owner": "red", "ships": 4}])
    assert alive == ["red"]
    assert ships == {"red": 4, "blue": 0}


def test_planet_map_is_rotationally_balanced():
    engine = load("planet_wars")
    for count in (2, 3, 4):
        slots = list(engine._SLOTS[:count])
        planets = engine._make_planets(slots, engine.random.Random("symmetry"))
        assert 12 <= len(planets) <= 18
        for index in range(0, len(planets), count):
            group = planets[index:index + count]
            assert len({(p["ships"], p["production"]) for p in group}) == 1
            radii = [engine.math.hypot(p["x"] - 50, p["y"] - 50) for p in group]
            assert max(radii) - min(radii) < .02


def test_defender_purchases_share_a_budget_and_dont_reward_kills():
    engine = load("defender_duel")
    player = {"hp": 50, "money": 70, "income": 12, "income_upgrades": 0, "towers": []}
    enemies = []
    engine._buy(player, {"action": "build", "pad": 3, "tower": "arrow"}, "blue", enemies)
    engine._buy(player, {"action": "build", "pad": 3, "tower": "arrow"}, "blue", enemies)
    assert player["money"] == 40
    assert len(player["towers"]) == 1
    engine._buy(player, {"action": "income"}, "blue", enemies)
    assert (player["money"], player["income"]) == (0, 16)
    enemy = {"target": "red", "type": "scout", "hp": 1, "distance": 8, "speed": 1,
             "armor": 0, "damage": 1}
    engine._fight({"red": player}, [enemy])
    assert player["money"] == 0


def test_defender_simultaneous_base_destruction_is_a_tie():
    engine = load("defender_duel")
    players = {s: {"hp": 1, "towers": []} for s in ("red", "blue")}
    enemies = [{"target": s, "hp": 10, "distance": 19.8, "speed": 1, "damage": 1}
               for s in players]
    engine._fight(players, enemies)
    assert [p["hp"] for p in players.values()] == [0, 0]


def territory_fixture():
    board = [[None] * 30 for _ in range(30)]
    board[2][2] = "red"
    board[27][27] = "blue"
    players = {"red": {"x": 2, "y": 2, "alive": True, "trail": []},
               "blue": {"x": 27, "y": 27, "alive": True, "trail": []}}
    return board, players


def test_closed_territory_loop_fills_interior_and_enemy_land():
    engine = load("territory_capture")
    board, players = territory_fixture()
    board[3][3] = "blue"
    trail = [(3, 2), (4, 2), (4, 3), (4, 4), (3, 4), (2, 4), (2, 3)]
    players["red"].update(x=2, y=3, trail=[list(p) for p in trail])
    predicted = engine.capture_area(board, "red", trail)
    assert (3, 3) in predicted
    assert board[3][3] == "blue"  # helper is read-only
    engine._step(board, players, {"red": "up", "blue": "stay"})
    assert all(board[x][y] == "red" for x in range(2, 5) for y in range(2, 5))
    assert players["red"]["trail"] == []


def test_cutting_a_territory_trail_eliminates_its_owner_and_neutralizes_land():
    engine = load("territory_capture")
    board, players = territory_fixture()
    players["red"].update(x=4, y=2, trail=[[3, 2], [4, 2]])
    players["blue"].update(x=3, y=3)
    killed = engine._step(board, players, {"red": "stay", "blue": "up"})
    assert killed == {"red"}
    assert not players["red"]["alive"]
    assert not any("red" in column for column in board)


def test_staying_on_own_trail_is_safe_but_stepping_back_is_not():
    engine = load("territory_capture")
    board, players = territory_fixture()
    players["red"].update(x=4, y=2, trail=[[3, 2], [4, 2]])
    assert not engine._step(board, players, {"red": "stay", "blue": "stay"})
    assert engine._step(board, players, {"red": "left", "blue": "stay"}) == {"red"}


def test_simultaneous_territory_claims_leave_disputed_cells_unchanged(monkeypatch):
    engine = load("territory_capture")
    board, players = territory_fixture()
    players["red"].update(x=3, y=2, trail=[[3, 2]])
    players["blue"].update(x=26, y=27, trail=[[26, 27]])
    board[10][10] = "red"
    monkeypatch.setattr(engine, "capture_area", lambda board, me, trail: [(10, 10), (11, 11)])
    engine._step(board, players, {"red": "left", "blue": "right"})
    assert board[10][10] == "red"
    assert board[11][11] is None


@pytest.mark.parametrize("game", ["territory_capture", "bomb_arena"])
def test_collisions_propagate_bounces_to_incoming_players(game):
    engine = load(game)
    positions = {"red": (0, 0), "blue": (1, 0), "green": (2, 0)}
    intents = {"red": (1, 0), "blue": (2, 0), "green": (2, 0)}
    assert engine._resolve_moves(positions, intents) == positions
    swapped = {"red": (1, 0), "blue": (0, 0), "green": (2, 0)}
    result = engine._resolve_moves(positions, swapped, block_swaps=game == "territory_capture")
    assert result == (positions if game == "territory_capture" else swapped)


def bomb_fixture():
    board = [[0] * 15 for _ in range(15)]
    players = {"red": {"x": 3, "y": 3, "alive": True, "capacity": 1, "range": 2, "eliminated_at": None},
               "blue": {"x": 11, "y": 11, "alive": True, "capacity": 1, "range": 2, "eliminated_at": None}}
    return board, players


def test_bomb_can_be_placed_and_left_in_the_same_turn_and_explodes_on_schedule():
    engine = load("bomb_arena")
    board, players = bomb_fixture()
    bombs = []
    fire, _, _ = engine._step(board, {}, players, bombs, {}, {"red": {"move": "right", "bomb": True}}, 0)
    assert not fire
    assert bombs == [{"owner": "red", "x": 3, "y": 3, "range": 2, "explode_at": 5}]
    assert players["red"]["x"] == 4
    engine._step(board, {}, players, bombs, {}, {"red": "left"}, 1)
    assert players["red"]["x"] == 4  # reentry is blocked
    engine._step(board, {}, players, bombs, {}, {"red": "down"}, 2)
    fire, _, _ = engine._step(board, {}, players, bombs, {}, {}, 4)
    assert (3, 3) in fire
    assert not bombs
    assert players["red"]["alive"]


def test_bomb_chain_is_order_independent_and_preserves_crate_blocking():
    engine = load("bomb_arena")
    board, _ = bomb_fixture()
    board[5][3] = 1
    board[3][1] = -1
    bombs = [{"x": 3, "y": 3, "range": 5, "explode_at": 5},
             {"x": 4, "y": 3, "range": 5, "explode_at": 20}]
    fire, crates, exploded = engine._blast(board, bombs, 5)
    reverse_fire, reverse_crates, reverse_exploded = engine._blast(board, bombs[::-1], 5)
    assert (fire, crates, len(exploded)) == (reverse_fire, reverse_crates, len(reverse_exploded))
    assert len(exploded) == 2
    assert (5, 3) in crates
    assert (6, 3) not in fire
    assert (3, 0) not in fire


def test_future_blast_helper_accounts_for_crates_removed_in_earlier_phases():
    engine = load("bomb_arena")
    board, _ = bomb_fixture()
    board[5][3] = 1
    bombs = [{"x": 3, "y": 3, "range": 2, "explode_at": 5},
             {"x": 7, "y": 3, "range": 4, "explode_at": 8}]
    state = {"tick": 0, "board": board, "bombs": bombs}
    original = copy.deepcopy(state)
    times = engine.blast_times(state)
    assert times[5][3] == 5
    assert times[6][3] == 8
    assert state == original


def test_blast_forecast_can_keep_repeated_explosions_on_the_same_cell():
    engine = load("bomb_arena")
    board, _ = bomb_fixture()
    bombs = [{"x": 3, "y": 3, "range": 3, "explode_at": 5},
             {"x": 6, "y": 6, "range": 3, "explode_at": 8}]
    state = {"tick": 0, "board": board, "bombs": bombs}
    assert engine.blast_times(state)[6][3] == 5
    assert engine.blast_times(state, all_phases=True)[6][3] == [5, 8]


def test_bomb_capacity_and_powerups_and_shrink():
    engine = load("bomb_arena")
    board, players = bomb_fixture()
    bombs = [{"x": 7, "y": 7, "owner": "red", "range": 2, "explode_at": 120}]
    powerups = {(4, 3): "capacity"}
    engine._step(board, {}, players, bombs, powerups, {"red": {"bomb": True, "move": "right"}}, 0)
    assert len(bombs) == 1
    assert players["red"]["capacity"] == 2
    engine._step(board, {}, players, bombs, powerups, {"red": {"bomb": True, "move": "down"}}, 1)
    assert len(bombs) == 2
    players["red"].update(x=1, y=2)
    _, _, killed = engine._step(board, {}, players, bombs, powerups, {}, 99)
    assert "red" in killed
    assert board[1][2] == -2


def test_bomb_map_and_hidden_bonuses_are_symmetric():
    engine = load("bomb_arena")
    board, hidden = engine._make_board(engine.random.Random("symmetric"))
    for x in range(15):
        for y in range(15):
            assert board[x][y] == board[14 - x][y] == board[x][14 - y]
            assert hidden.get((x, y)) == hidden.get((14 - x, y)) == hidden.get((x, 14 - y))


def test_bomber_demo_escapes_its_first_bomb():
    engine = load("bomb_arena")
    result = engine.run(context("bomb_arena"))
    first_bomb = next(frame for frame in result["frames"] if frame["frame"]["bombs"])
    bomb = first_bomb["frame"]["bombs"][0]
    after_explosion = next(frame for frame in result["frames"] if frame["tick"] == bomb["explode_at"])
    assert after_explosion["frame"]["players"][bomb["owner"]]["alive"]


@pytest.mark.parametrize("seed", range(6))
def test_bomber_demo_clears_crates_and_avoids_own_bombs_before_shrink(seed):
    engine = load("bomb_arena")
    source = (ROOT / "games" / "bomb_arena" / "examples" / "safe_bomber.py").read_text()
    result = engine.run({"run_id": f"safe-{seed}", "codes_by_slot": {
        "red": source, "blue": "def make_move(state):\n    return 'stay'\n"}})
    assert any(f["frame"]["bombs"] for f in result["frames"])
    assert result["frames"][-1]["frame"]["players"]["red"]["alive"]
