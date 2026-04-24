from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from game_catalog.infrastructure.manifest_loader import load_game_manifest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_demo_strategies_execute_against_their_engines() -> None:
    games_root = _repo_root() / "games"

    for manifest_path in sorted(games_root.glob("*/manifest.yaml")):
        manifest = load_game_manifest(manifest_path)
        module = _load_module(manifest_path.parent / manifest.engine_entrypoint, f"{manifest.id}_demo_test")
        codes_by_slot = {
            strategy.slot_key: (manifest_path.parent / strategy.path).read_text(encoding="utf-8")
            for strategy in manifest.demo_strategies
        }

        run_kind = "single_task" if manifest.game_mode.value == "single_task" else "training_match"
        payload = module.run(
            {
                "run_kind": run_kind,
                "team_id": "demo-team",
                "codes_by_slot": codes_by_slot,
            }
        )
        metrics = payload["metrics"]

        assert payload["status"] == "finished", manifest.id
        assert not [key for key in metrics if str(key).startswith("compile_error")], manifest.id
        assert isinstance(payload.get("frames"), list) and payload["frames"], manifest.id
        assert isinstance(payload.get("events"), list), manifest.id

        if manifest.id == "maze_escape_v1":
            assert metrics["reached_exit"] is True
        elif manifest.id == "coins_right_down_v1":
            assert metrics["reached_goal"] is True
            assert metrics["coins_collected"] == metrics["coins_total"]
        elif manifest.id == "tower_defense_v1":
            assert metrics["base_hp"] > 0
            assert metrics["towers_built"] > 0
        elif manifest.id == "template_v1":
            assert metrics["final_value"] == 5
