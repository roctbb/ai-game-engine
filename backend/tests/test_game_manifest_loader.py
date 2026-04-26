import json
from pathlib import Path

import pytest

from game_catalog.infrastructure.manifest_loader import (
    find_game_manifest_path,
    load_game_manifest,
    load_game_manifests,
)
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
        "tower_defense_v1",
        "ttt_connect5_v1",
    }.issubset(by_id)
    assert by_id["ttt_connect5_v1"].code_api_mode == "turn_based"
    assert by_id["maze_escape_v1"].code_api_mode == "script_based"
    assert by_id["tanks_ctf_v1"].to_register_input().required_slots[0].key == "driver"
    assert by_id["tanks_ctf_v1"].to_register_input().mode.value == "multiplayer"
    assert by_id["tanks_ctf_v1"].match_player_bounds == (2, 16)
    assert by_id["maze_escape_v1"].difficulty == "medium"
    assert by_id["maze_escape_v1"].learning_section == "Поиск пути BFS"
    assert "поиск пути" in by_id["maze_escape_v1"].topics
    assert by_id["maze_escape_v1"].demo_strategies[0].slot_key == "agent"
    assert by_id["tanks_ctf_v1"].demo_strategies[1].slot_key == "support"


def test_repository_learning_sections_match_course_topics() -> None:
    manifests = load_game_manifests(_repo_root() / "games")
    by_id = {manifest.id: manifest for manifest in manifests}

    expected_sections = {
        "apple_market_v1": "Соревновательные стратегии",
        "courier_v1": "Состояния: время, ключи, ресурсы",
        "garden_harvest_v1": "Состояния: время, ключи, ресурсы",
        "snake_v1": "Симуляции мира",
        "trap_coin_duel_v1": "Соревновательные стратегии",
        "coins_right_down_v1": "Динамическое программирование",
    }

    for game_id, section in expected_sections.items():
        assert by_id[game_id].learning_section == section

    assert "графы" not in by_id["coins_right_down_v1"].topics
    assert {"матрицы", "динамическое программирование", "оптимальный путь"}.issubset(
        by_id["coins_right_down_v1"].topics
    )


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


def test_bulk_manifest_loading_skips_invalid_packages_unless_strict(tmp_path: Path) -> None:
    valid_dir = tmp_path / "valid_game"
    valid_dir.mkdir()
    (valid_dir / "engine.py").write_text("", encoding="utf-8")
    (valid_dir / "manifest.yaml").write_text(
        """
id: valid_game
title: Valid Game
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

    broken_dir = tmp_path / "broken_game"
    broken_dir.mkdir()
    (broken_dir / "manifest.yaml").write_text("id: [", encoding="utf-8")

    assert [manifest.id for manifest in load_game_manifests(tmp_path)] == ["valid_game"]
    assert find_game_manifest_path(tmp_path, "valid_game") == valid_dir / "manifest.yaml"
    with pytest.raises(InvariantViolationError):
        load_game_manifests(tmp_path, strict=True)


def test_new_reference_game_graphics_are_svg() -> None:
    games_root = _repo_root() / "games"
    for game_dir in ("maze_escape", "coins_right_down", "tower_defense"):
        renderer_assets = list((games_root / game_dir / "renderer").glob("*.svg"))
        assert renderer_assets, f"{game_dir} must provide SVG renderer assets"


def test_repository_game_demo_strategies_point_to_existing_slots_and_files() -> None:
    for manifest in load_game_manifests(_repo_root() / "games"):
        assert manifest.demo_strategies, f"{manifest.id} must provide at least one demo strategy"
        slot_keys = {slot.key for slot in manifest.slots}
        manifest_path = find_game_manifest_path(_repo_root() / "games", manifest.id)
        for strategy in manifest.demo_strategies:
            assert strategy.slot_key in slot_keys
            assert (manifest_path.parent / strategy.path).is_file()


def test_repository_renderers_have_initial_preview_frames() -> None:
    for manifest in load_game_manifests(_repo_root() / "games"):
        if not manifest.renderer_entrypoint:
            continue

        manifest_path = find_game_manifest_path(_repo_root() / "games", manifest.id)
        renderer_root = manifest_path.parent / Path(manifest.renderer_entrypoint).parent
        preview_path = renderer_root / "preview.json"

        assert preview_path.is_file(), f"{manifest.id} must show a map before the first run"
        preview = json.loads(preview_path.read_text(encoding="utf-8"))
        assert isinstance(preview.get("frame"), dict), manifest.id
        assert preview["frame"], manifest.id
