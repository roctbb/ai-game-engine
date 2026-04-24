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


def test_tic_tac_toe_requires_five_marks_for_win() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    engine = _load_module(
        repo_root / "games" / "tic_tac_toe" / "engine.py",
        "ttt_engine_regression_single_line",
    )

    field = engine.createEmptyField()
    for x in range(4):
        field[x][0] = 1

    assert engine.checkForWin(field) == 0


def test_tic_tac_toe_detects_both_five_cell_diagonals() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    engine = _load_module(
        repo_root / "games" / "tic_tac_toe" / "engine.py",
        "ttt_engine_regression_diagonals",
    )

    main_diag = engine.createEmptyField()
    anti_diag = engine.createEmptyField()
    for index in range(5):
        main_diag[index][index] = 1
        anti_diag[4 - index][index] = -1

    assert engine.checkForWin(main_diag) == 1
    assert engine.checkForWin(anti_diag) == -1


def test_template_engine_competition_payload_contains_placements() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    engine = _load_module(
        repo_root / "games" / "template" / "engine.py",
        "template_engine_regression_competition",
    )

    payload = engine.run(
        {
            "run_kind": "competition_match",
            "codes_by_slot": {"bot": "def make_choice(state):\n    return 'inc'\n"},
        }
    )

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" in payload


def test_template_engine_training_payload_contains_scores_only() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    engine = _load_module(
        repo_root / "games" / "template" / "engine.py",
        "template_engine_regression_training",
    )

    payload = engine.run(
        {
            "run_kind": "training_match",
            "codes_by_slot": {"bot": "def make_move(state):\n    return 'dec'\n"},
        }
    )

    assert payload["status"] == "finished"
    assert "scores" in payload
    assert "placements" not in payload
    assert payload.get("metrics", {}).get("final_value") == -20
