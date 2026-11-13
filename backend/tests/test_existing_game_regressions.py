import importlib.util
from pathlib import Path

import pytest


def load_game_module(relative_path, name):
    path = Path(__file__).resolve().parents[2] / "games" / "tic_tac_toe" / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def engine():
    return load_game_module("engine.py", "ttt_connect4_regression")


WINNING_SEGMENTS = [
    [(x + i * dx, y + i * dy) for i in range(4)]
    for x in range(5)
    for y in range(5)
    for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]
    if 0 <= x + 3 * dx < 5 and 0 <= y + 3 * dy < 5
]


@pytest.mark.parametrize("segment", WINNING_SEGMENTS)
@pytest.mark.parametrize("role", [-1, 1])
def test_tic_tac_toe_all_four_cell_lines_win(engine, segment, role):
    field = engine.createEmptyField()
    assert len(field) == 5 and all(len(column) == 5 for column in field)
    for x, y in segment[:-1]:
        field[x][y] = role
    assert engine.checkForWin(field) == 0
    x, y = segment[-1]
    field[x][y] = role
    assert engine.checkForWin(field) == role


@pytest.mark.parametrize(
    "marks",
    [
        [(0, 0), (1, 0), (3, 0), (4, 0)],  # A gap does not join two pairs.
        [(3, 0), (4, 0), (0, 1), (1, 1)],  # Rows do not wrap around.
    ],
)
def test_tic_tac_toe_disconnected_marks_do_not_win(engine, marks):
    field = engine.createEmptyField()
    for x, y in marks:
        field[x][y] = 1
    assert engine.checkForWin(field) == 0


def test_tic_tac_toe_five_also_contains_a_winning_four(engine):
    field = engine.createEmptyField()
    for x in range(5):
        field[x][2] = -1
    assert engine.checkForWin(field) == -1


@pytest.mark.parametrize("role", [-1, 1])
@pytest.mark.parametrize(
    "segment",
    [
        [(0, 4), (1, 4), (2, 4), (3, 4)],
        [(1, 0), (2, 1), (3, 2), (4, 3)],
        [(0, 4), (1, 3), (2, 2), (3, 1)],
    ],
)
def test_connect4_demo_finishes_four_and_blocks_opponent(engine, role, segment):
    demo = load_game_module("examples/connect4_balanced.py", "connect4_demo")
    for sign in [role, -role]:
        field = engine.createEmptyField()
        for x, y in segment[:-1]:
            field[x][y] = sign
        before = [column[:] for column in field]
        assert demo.make_choice(field, role) == segment[-1]
        assert field == before


def test_connect4_demo_prefers_winning_to_blocking(engine):
    demo = load_game_module("examples/connect4_balanced.py", "connect4_demo_priority")
    field = engine.createEmptyField()
    for x in range(3):
        field[x][0] = -1
        field[x][4] = 1
    assert demo.make_choice(field, 1) == (3, 4)


def test_real_match_stops_at_four_before_fifth_mark(engine):
    code = "def make_choice(field, role):\n    for x in range(5):\n        if field[x][0 if role == 1 else 4] == 0:\n            return x, 0 if role == 1 else 4\n"
    payload = engine.run(
        {
            "run_kind": "competition_match",
            "participants": [
                {"team_id": team, "codes_by_slot": {"bot": code}} for team in ["a", "b"]
            ],
        }
    )
    assert payload["metrics"]["turns_played"] == 7
    assert payload["metrics"]["winner_role"] == 1
    assert payload["metrics"]["bot_errors"] == 0
    assert payload["scores"] == {"a": 1, "b": 0}
    board = payload["frames"][-1]["frame"]["board"]
    assert sum(cell == 1 for column in board for cell in column) == 4
