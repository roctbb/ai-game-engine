from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys

import pytest


@contextmanager
def _tanks_domain_modules():
    tanks_root = Path(__file__).resolve().parents[2] / "games" / "tanks"
    inserted = False
    if str(tanks_root) not in sys.path:
        sys.path.insert(0, str(tanks_root))
        inserted = True
    try:
        from domain.common import Decision, Object, Point
        from domain.game import Game
        from domain.general_player import GeneralPlayer
        from domain.map import Map
        from domain.player import Player

        yield {
            "Decision": Decision,
            "Object": Object,
            "Point": Point,
            "Game": Game,
            "GeneralPlayer": GeneralPlayer,
            "Map": Map,
            "Player": Player,
        }
    finally:
        if inserted:
            sys.path.remove(str(tanks_root))


def test_legacy_tanks_apply_move_uses_full_speed_distance() -> None:
    with _tanks_domain_modules() as m:
        game = m["Game"]()
        game.size = (9, 7)
        player = m["GeneralPlayer"]()
        player.properties["speed"] = 3
        game.players[(1, 1)] = player

        events = game.apply_move(player, m["Point"](1, 1), m["Decision"].GO_RIGHT)

        assert events == []
        assert (4, 1) in game.players
        assert (1, 1) not in game.players


def test_legacy_tanks_apply_move_stops_before_blocker() -> None:
    with _tanks_domain_modules() as m:
        game = m["Game"]()
        game.size = (9, 7)
        player = m["GeneralPlayer"]()
        player.properties["speed"] = 3
        game.players[(1, 1)] = player
        game.objects[(3, 1)] = m["Object"]()

        events = game.apply_move(player, m["Point"](1, 1), m["Decision"].GO_RIGHT)

        assert events == []
        assert (2, 1) in game.players
        assert (1, 1) not in game.players


def test_legacy_tanks_base_map_init_requires_override() -> None:
    with _tanks_domain_modules() as m:
        with pytest.raises(NotImplementedError):
            m["Map"].init(m["Game"]())


def test_legacy_general_player_non_string_decision_is_handled_safely() -> None:
    with _tanks_domain_modules() as m:
        player = m["GeneralPlayer"]()
        player.decider = lambda x, y, state: 123

        result = player.step(m["Point"](0, 0), map_state=[])

        assert result is None
        assert player.history[-1] == "invalid_choice"
        assert "Invalid choice type" in str(player.errors[-1])


def test_legacy_tanks_player_runs_inline_script_without_ge_sdk() -> None:
    class InlineScriptPlayer:
        script = "def make_choice(x, y, field):\n    return 'go_right'\n"

    with _tanks_domain_modules() as m:
        player = m["Player"](InlineScriptPlayer())

        result = player.step(m["Point"](0, 0), map_state=[])

        assert result == m["Decision"].GO_RIGHT
        assert player.history[-1] == "go_right"
