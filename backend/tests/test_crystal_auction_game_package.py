from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from game_catalog.infrastructure.manifest_loader import load_game_manifest


MATCH_PACKAGES = {"crystal_auction": "Соревновательные стратегии"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_crystal_auction_packages_have_expected_learning_sections() -> None:
    games_root = _repo_root() / "games"

    for package, expected_section in MATCH_PACKAGES.items():
        manifest = load_game_manifest(games_root / package / "manifest.yaml")

        assert manifest.learning_section == expected_section
        assert manifest.demo_strategies, package
        assert manifest.player_instruction, package
        assert (games_root / package / "renderer" / "index.html").is_file()
        renderer_html = (games_root / package / "renderer" / "index.html").read_text(
            encoding="utf-8"
        )
        assert "crystal-auction-1" in renderer_html
        assert "m.payload" in renderer_html
        assert "renderAuction" in renderer_html
        assert "function setView" in renderer_html
        for slot in manifest.slots:
            assert (games_root / package / "templates" / f"{slot.key}.py").is_file()


def test_crystal_auction_guides_are_specific_and_include_examples() -> None:
    games_root = _repo_root() / "games"

    for package, expected_section in MATCH_PACKAGES.items():
        guide = (games_root / package / "player_guide_ru.md").read_text(encoding="utf-8")

        assert f"**{expected_section}**" in guide, package
        assert "## Что видно в визуализации" in guide, package
        assert "## Входные данные" in guide, package
        assert "## Как думать" in guide, package
        assert "## Частые ошибки" in guide, package
        assert "Карта, если она есть" not in guide, package
        assert "## Пример стратегии участника" in guide, package


def test_crystal_auction_demo_strategies_run_successfully() -> None:
    games_root = _repo_root() / "games"

    for package in MATCH_PACKAGES:
        package_root = games_root / package
        manifest = load_game_manifest(package_root / "manifest.yaml")
        codes_by_slot: dict[str, str] = {}
        for slot in manifest.slots:
            demo = next(item for item in manifest.demo_strategies if item.slot_key == slot.key)
            codes_by_slot[slot.key] = (package_root / demo.path).read_text(encoding="utf-8")

        context = {
            "run_id": f"test-{package}",
            "run_kind": "competition_match",
            "codes_by_slot": codes_by_slot,
        }
        env = os.environ.copy()
        env["AGP_RUN_CONTEXT"] = json.dumps(context, ensure_ascii=False)
        completed = subprocess.run(
            [sys.executable, "engine.py"],
            cwd=package_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        payload = json.loads(completed.stdout)
        assert payload["status"] == "finished"
        assert payload["scores"], package


def test_crystal_auction_starter_templates_are_runnable_and_not_empty() -> None:
    games_root = _repo_root() / "games"

    for package in MATCH_PACKAGES:
        package_root = games_root / package
        manifest = load_game_manifest(package_root / "manifest.yaml")
        codes_by_slot = {
            slot.key: (package_root / "templates" / f"{slot.key}.py").read_text(encoding="utf-8")
            for slot in manifest.slots
        }
        for slot_key, code in codes_by_slot.items():
            assert "\n        pass\n" not in code and "\n    pass\n" not in code, (
                f"{package}:{slot_key}"
            )
            assert "return None" not in code, f"{package}:{slot_key}"
            assert 'state["aimed"]' not in code, f"{package}:{slot_key}"

        context = {
            "run_id": f"starter-template-{package}",
            "run_kind": "competition_match",
            "codes_by_slot": codes_by_slot,
        }
        env = os.environ.copy()
        env["AGP_RUN_CONTEXT"] = json.dumps(context, ensure_ascii=False)
        completed = subprocess.run(
            [sys.executable, "engine.py"],
            cwd=package_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        payload = json.loads(completed.stdout)
        assert payload["status"] == "finished", package
        assert len(payload["frames"]) > 1, package
        assert not [event for event in payload["events"] if event.get("type") == "compile_error"], (
            package
        )


def test_crystal_auction_api_returns_package_specific_starter_templates(client) -> None:
    games = client.get("/api/v1/games")
    assert games.status_code == 200
    by_slug = {item["slug"]: item for item in games.json()}

    auction = client.get(f"/api/v1/games/{by_slug['crystal_auction_v1']['game_id']}/templates")
    assert auction.status_code == 200
    templates_by_slot = {item["slot_key"]: item["code"] for item in auction.json()["templates"]}
    assert "def bid(state):" in templates_by_slot["left"]
    assert "crystal_value" in templates_by_slot["right"]
