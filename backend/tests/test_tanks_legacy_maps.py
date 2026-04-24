from __future__ import annotations

from contextlib import contextmanager
import importlib
from pathlib import Path
import sys
from typing import Any


@contextmanager
def _tanks_map_modules() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    tanks_root = project_root / "games" / "tanks"
    inserted_paths: list[str] = []
    for candidate in (str(project_root), str(tanks_root)):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
            inserted_paths.append(candidate)
    try:
        game_mod = importlib.import_module("domain.game")
        player_mod = importlib.import_module("domain.player")
        coin_mod = importlib.import_module("domain.items.coin")
        big_mod = importlib.import_module("domain.maps.big")
        tank_mod = importlib.import_module("domain.maps.tanks")
        yield {
            "Game": game_mod.Game,
            "Player": player_mod.Player,
            "Coin": coin_mod.Coin,
            "BigMap": big_mod.BigMap,
            "TankMap": tank_mod.TankMap,
            "big_mod": big_mod,
            "tank_mod": tank_mod,
        }
    finally:
        for path in inserted_paths:
            if path in sys.path:
                sys.path.remove(path)


def _template_cells(template: str, predicate: callable) -> list[tuple[int, int]]:
    rows = template.replace(" ", "").splitlines()
    cells: list[tuple[int, int]] = []
    for x, row in enumerate(rows):
        for y, ch in enumerate(row):
            if predicate(ch):
                cells.append((x, y))
    return cells


def test_legacy_big_map_alternates_player_teams(monkeypatch) -> None:
    with _tanks_map_modules() as m:
        free_cells = _template_cells(
            m["big_mod"].TEMPLATE,
            lambda ch: ch == ".",
        )
        cursor = {"n": 0}

        def fake_randint(a: int, b: int) -> int:
            pair = free_cells[(cursor["n"] // 2) % len(free_cells)]
            axis = cursor["n"] % 2
            cursor["n"] += 1
            return pair[axis]

        monkeypatch.setattr(m["big_mod"].random, "randint", fake_randint)

        game = m["Game"]()
        players = ["p1", "p2", "p3", "p4"]
        m["BigMap"].init(game, players)

        placed_players = [obj for obj in game.players.values() if isinstance(obj, m["Player"])]
        teams = {obj.properties.get("team") for obj in placed_players}

        assert len(placed_players) == len(players)
        assert teams == {"Radient", "Dare"}


def test_legacy_tank_map_places_coins_as_items_and_retries_on_collision(monkeypatch) -> None:
    with _tanks_map_modules() as m:
        dot_cells = _template_cells(
            m["tank_mod"].TEMPLATE,
            lambda ch: ch == ".",
        )
        blocked = (0, 0)
        pairs: list[tuple[int, int]] = []
        for cell in dot_cells[:30]:
            pairs.append(blocked)
            pairs.append(cell)
        cursor = {"n": 0}

        def fake_randint(a: int, b: int) -> int:
            pair = pairs[(cursor["n"] // 2) % len(pairs)]
            axis = cursor["n"] % 2
            cursor["n"] += 1
            return pair[axis]

        monkeypatch.setattr(m["tank_mod"].random, "randint", fake_randint)

        game = m["Game"]()
        m["TankMap"].init(game, players=[])

        coins_in_items = [obj for obj in game.items.values() if isinstance(obj, m["Coin"])]
        coins_in_objects = [obj for obj in game.objects.values() if isinstance(obj, m["Coin"])]

        assert len(coins_in_items) == 30
        assert coins_in_objects == []
