from pathlib import Path

import pytest

from game_catalog.infrastructure.manifest_loader import load_game_manifest, load_game_manifests
from shared.kernel import InvariantViolationError


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_loads_repository_game_manifests() -> None:
    manifests = load_game_manifests(_repo_root() / "games")
    by_id = {manifest.id: manifest for manifest in manifests}

    assert {
        "coins_right_down_v1",
        "maze_escape_v1",
        "tanks_ctf_v1",
        "template_v1",
        "tower_defense_v1",
        "ttt_connect5_v1",
    }.issubset(by_id)
    assert by_id["ttt_connect5_v1"].code_api_mode == "turn_based"
    assert by_id["maze_escape_v1"].code_api_mode == "script_based"
    assert by_id["tanks_ctf_v1"].to_register_input().required_slots[0].key == "driver"
    assert by_id["maze_escape_v1"].difficulty == "easy"
    assert "поиск пути" in by_id["maze_escape_v1"].topics
    assert by_id["maze_escape_v1"].demo_strategies[0].slot_key == "agent"
    assert by_id["tanks_ctf_v1"].demo_strategies[1].slot_key == "support"


def test_manifest_loader_rejects_duplicate_slot_keys(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
id: broken_game
title: Broken Game
game_mode: small_match
semver: 1.0.0
code_api_mode: turn_based
engine_entrypoint: engine.py
slots:
  - key: bot
    title: Bot A
  - key: bot
    title: Bot B
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(InvariantViolationError):
        load_game_manifest(manifest)


def test_manifest_loader_rejects_missing_entrypoint(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
id: missing_entrypoint
title: Missing Entrypoint
game_mode: single_task
semver: 1.0.0
code_api_mode: script_based
engine_entrypoint: engine.py
slots:
  - key: agent
    title: Agent
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(InvariantViolationError):
        load_game_manifest(manifest)


def test_new_reference_game_graphics_are_svg() -> None:
    games_root = _repo_root() / "games"
    for game_dir in ("maze_escape", "coins_right_down", "tower_defense"):
        renderer_assets = list((games_root / game_dir / "renderer").glob("*.svg"))
        assert renderer_assets, f"{game_dir} must provide SVG renderer assets"


def test_repository_game_demo_strategies_point_to_existing_slots_and_files() -> None:
    games_root = _repo_root() / "games"

    for manifest_path in sorted(games_root.glob("*/manifest.yaml")):
        manifest = load_game_manifest(manifest_path)
        assert manifest.demo_strategies, f"{manifest.id} must provide at least one demo strategy"
        slot_keys = {slot.key for slot in manifest.slots}
        for strategy in manifest.demo_strategies:
            assert strategy.slot_key in slot_keys
            assert (manifest_path.parent / strategy.path).is_file()
