from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from game_catalog.infrastructure.manifest_loader import load_game_manifest


PREGRAPH_PACKAGES = {
    "gate_guard": "Условия и выбор",
    "wall_archer": "Условия и выбор",
    "farm_row": "Циклы и повторения",
    "crystal_corridor": "Циклы и повторения",
    "rune_decoder": "Строки и коды",
    "miner_backpack": "Счетчики и ресурсы",
    "battery_robot_lite": "Счетчики и ресурсы",
    "potion_maker": "Счетчики и ресурсы",
    "weakest_enemy": "Списки и цели",
    "priority_tower": "Списки и цели",
    "hero_inventory": "Списки и цели",
    "space_queue": "Списки и цели",
    "command_tape": "Строки и коды",
    "pixel_painter": "Матрицы и координаты",
    "treasure_scanner": "Матрицы и координаты",
    "minesweeper_numbers": "Матрицы и координаты",
    "farm_grid": "Матрицы и координаты",
    "laser_mirrors": "Симуляции мира",
    "gravity_apples": "Симуляции мира",
    "patrol_guard": "Режимы поведения",
    "boss_pattern": "Режимы поведения",
    "crystal_auction": "Соревновательные стратегии",
}

PREGRAPH_SECTION_ORDER = [
    "Условия и выбор",
    "Циклы и повторения",
    "Строки и коды",
    "Счетчики и ресурсы",
    "Списки и цели",
    "Матрицы и координаты",
    "Режимы поведения",
    "Симуляции мира",
    "Соревновательные стратегии",
]

PREGRAPH_MATRIX_PACKAGES = {
    "pixel_painter",
    "treasure_scanner",
    "minesweeper_numbers",
    "farm_grid",
    "laser_mirrors",
    "gravity_apples",
}

PREGRAPH_MATCH_PACKAGES = {"crystal_auction"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_pregraph_packages_have_expected_learning_sections() -> None:
    games_root = _repo_root() / "games"

    for package, expected_section in PREGRAPH_PACKAGES.items():
        manifest = load_game_manifest(games_root / package / "manifest.yaml")

        assert manifest.learning_section == expected_section
        assert manifest.demo_strategies, package
        assert manifest.player_instruction, package
        assert (games_root / package / "renderer" / "index.html").is_file()
        renderer_html = (games_root / package / "renderer" / "index.html").read_text(encoding="utf-8")
        assert "adventure-pregraph-15" in renderer_html
        assert "m.payload" in renderer_html
        assert "renderDuel" in renderer_html
        assert "statMeters" in renderer_html
        assert "renderGateGuard" in renderer_html
        assert "renderPotionMaker" in renderer_html
        assert "renderEnemyChoice" in renderer_html
        assert "renderSpaceQueue" in renderer_html
        assert "renderMatrixScene" in renderer_html
        assert "renderPatrolGuard" in renderer_html
        assert "renderBossPattern" in renderer_html
        assert "function setView" in renderer_html
        for slot in manifest.slots:
            assert (games_root / package / "templates" / f"{slot.key}.py").is_file()


def test_pregraph_learning_sections_are_ordered_from_intro_to_advanced() -> None:
    used_sections = [section for section in PREGRAPH_SECTION_ORDER if section in set(PREGRAPH_PACKAGES.values())]

    assert used_sections == [
        "Условия и выбор",
        "Циклы и повторения",
        "Строки и коды",
        "Счетчики и ресурсы",
        "Списки и цели",
        "Матрицы и координаты",
        "Режимы поведения",
        "Симуляции мира",
        "Соревновательные стратегии",
    ]


def test_pregraph_guides_are_specific_and_include_examples() -> None:
    games_root = _repo_root() / "games"

    for package, expected_section in PREGRAPH_PACKAGES.items():
        guide = (games_root / package / "player_guide_ru.md").read_text(encoding="utf-8")

        assert f"**{expected_section}**" in guide, package
        assert "## Что видно в визуализации" in guide, package
        assert "## Входные данные" in guide, package
        assert "## Как думать" in guide, package
        assert "## Частые ошибки" in guide, package
        assert "Карта, если она есть" not in guide, package
        if package in PREGRAPH_MATCH_PACKAGES:
            assert "## Пример стратегии участника" in guide, package
        else:
            assert "## Пример решения" in guide, package
        if package in PREGRAPH_MATRIX_PACKAGES:
            assert "[x][y]" in guide, package


def test_pregraph_engines_share_the_same_runtime_body() -> None:
    games_root = _repo_root() / "games"
    canonical = (games_root / "gate_guard" / "engine.py").read_text(encoding="utf-8")
    canonical_body = canonical[canonical.index("\ndef run(") :]

    for package in set(PREGRAPH_PACKAGES) - PREGRAPH_MATCH_PACKAGES:
        engine = (games_root / package / "engine.py").read_text(encoding="utf-8")
        body = engine[engine.index("\ndef run(") :]

        assert body == canonical_body, package


def test_pregraph_demo_strategies_run_successfully() -> None:
    games_root = _repo_root() / "games"

    for package in PREGRAPH_PACKAGES:
        package_root = games_root / package
        manifest = load_game_manifest(package_root / "manifest.yaml")
        codes_by_slot: dict[str, str] = {}
        for slot in manifest.slots:
            demo = next(item for item in manifest.demo_strategies if item.slot_key == slot.key)
            codes_by_slot[slot.key] = (package_root / demo.path).read_text(encoding="utf-8")

        context = {
            "run_id": f"test-{package}",
            "run_kind": "competition_match" if manifest.game_mode.value != "single_task" else "single_task",
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
        if manifest.game_mode.value == "single_task":
            assert payload["metrics"]["score"] == 100, package
            assert payload["metrics"]["solved"] is True, package
            assert len(payload["frames"]) > 2, package
            assert any("active_index" in frame["frame"] or "active_x" in frame["frame"] for frame in payload["frames"]), package
            if package == "miner_backpack":
                assert any("backpack_weight" in frame["frame"] for frame in payload["frames"]), package
            if package == "potion_maker":
                assert any("recipe_name" in frame["frame"] for frame in payload["frames"]), package
            if package in {"weakest_enemy", "priority_tower"}:
                assert any("enemy" in frame["frame"] for frame in payload["frames"]), package
            if package == "space_queue":
                assert any("active_ship_id" in frame["frame"] for frame in payload["frames"]), package
        else:
            assert payload["scores"], package


def test_pregraph_starter_templates_are_runnable_and_not_empty() -> None:
    games_root = _repo_root() / "games"

    for package in PREGRAPH_PACKAGES:
        package_root = games_root / package
        manifest = load_game_manifest(package_root / "manifest.yaml")
        codes_by_slot = {
            slot.key: (package_root / "templates" / f"{slot.key}.py").read_text(encoding="utf-8")
            for slot in manifest.slots
        }
        for slot_key, code in codes_by_slot.items():
            assert "\n        pass\n" not in code and "\n    pass\n" not in code, f"{package}:{slot_key}"
            assert "return None" not in code, f"{package}:{slot_key}"
            assert 'state["aimed"]' not in code, f"{package}:{slot_key}"

        context = {
            "run_id": f"starter-template-{package}",
            "run_kind": "competition_match" if manifest.game_mode.value != "single_task" else "single_task",
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
        assert not [event for event in payload["events"] if event.get("type") == "compile_error"], package


def test_pregraph_quality_templates_do_not_solve_without_student_work() -> None:
    games_root = _repo_root() / "games"

    for package in {
        "weakest_enemy",
        "priority_tower",
        "treasure_scanner",
        "space_queue",
        "boss_pattern",
        "farm_grid",
        "potion_maker",
        "minesweeper_numbers",
        "gravity_apples",
        "laser_mirrors",
    }:
        package_root = games_root / package
        code = (package_root / "templates" / "agent.py").read_text(encoding="utf-8")
        context = {
            "run_id": f"template-{package}",
            "codes_by_slot": {"agent": code},
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
        assert payload["metrics"]["solved"] is False, package
        assert payload["metrics"]["score"] < 100, package


def test_pregraph_list_scoring_penalizes_extra_actions() -> None:
    package_root = _repo_root() / "games" / "farm_row"
    context = {
        "run_id": "test-extra-actions",
        "codes_by_slot": {
            "agent": "\n".join(
                [
                    "def solve(row):",
                    "    result = []",
                    "    for cell in row:",
                    "        if cell == 1:",
                    "            result.append('water')",
                    "        else:",
                    "            result.append('skip')",
                    "    result.append('skip')",
                    "    return result",
                ]
            )
        },
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
    assert payload["metrics"]["solved"] is False
    assert payload["metrics"]["extra"] == 1
    assert payload["metrics"]["score"] < 100


def test_pregraph_nested_matrix_scoring_counts_cells() -> None:
    package_root = _repo_root() / "games" / "pixel_painter"
    context = {
        "run_id": "test-nested-matrix-partial-score",
        "codes_by_slot": {
            "agent": "\n".join(
                [
                    "def paint(pixels, palette):",
                    "    result = []",
                    "    for x in range(len(pixels)):",
                    "        column = []",
                    "        for y in range(len(pixels[x])):",
                    "            column.append(palette.get(pixels[x][y], 'transparent'))",
                    "        result.append(column)",
                    "    result[0][0] = 'wrong'",
                    "    return result",
                ]
            )
        },
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
    assert payload["metrics"]["solved"] is False
    assert payload["metrics"]["total"] == 30
    assert payload["metrics"]["correct"] == 29
    assert 90 <= payload["metrics"]["score"] < 100


def test_pregraph_api_returns_package_specific_starter_templates(client) -> None:
    games = client.get("/api/v1/games")
    assert games.status_code == 200
    by_slug = {item["slug"]: item for item in games.json()}

    gate_guard = client.get(f"/api/v1/games/{by_slug['gate_guard_v1']['game_id']}/templates")
    assert gate_guard.status_code == 200
    gate_guard_template = gate_guard.json()["templates"][0]["code"]
    assert "def choose_action(gate):" in gate_guard_template
    assert "return \"attack\"" in gate_guard_template

    pixel = client.get(f"/api/v1/games/{by_slug['pixel_painter_v1']['game_id']}/templates")
    assert pixel.status_code == 200
    pixel_template = pixel.json()["templates"][0]["code"]
    assert "def paint(pixels, palette):" in pixel_template
    assert 'palette.get(code, "transparent")' in pixel_template

    laser = client.get(f"/api/v1/games/{by_slug['laser_mirrors_v1']['game_id']}/templates")
    assert laser.status_code == 200
    laser_template = laser.json()["templates"][0]["code"]
    assert "def trace(board, start_x, start_y, dx, dy):" in laser_template
    assert "seen = set()" in laser_template

    auction = client.get(f"/api/v1/games/{by_slug['crystal_auction_v1']['game_id']}/templates")
    assert auction.status_code == 200
    templates_by_slot = {item["slot_key"]: item["code"] for item in auction.json()["templates"]}
    assert "def bid(state):" in templates_by_slot["left"]
    assert "crystal_value" in templates_by_slot["right"]
