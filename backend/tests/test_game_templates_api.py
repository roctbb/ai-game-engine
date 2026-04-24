from __future__ import annotations


def _find_game_id(client, slug: str) -> str:
    games = client.get("/api/v1/games").json()
    return next(item["game_id"] for item in games if item["slug"] == slug)


def test_get_game_templates_for_script_based_game(client) -> None:
    game_id = _find_game_id(client, "maze_escape_v1")
    response = client.get(f"/api/v1/games/{game_id}/templates")
    assert response.status_code == 200
    payload = response.json()

    assert payload["code_api_mode"] == "script_based"
    assert payload["templates"][0]["slot_key"] == "agent"
    assert "def make_move(state):" in payload["templates"][0]["code"]
    assert payload["demo_strategies"][0]["slot_key"] == "agent"
    assert "BFS" in payload["demo_strategies"][0]["title"]
    assert "def make_move(state):" in payload["demo_strategies"][0]["code"]


def test_get_game_templates_uses_slot_specific_stub_for_defender(client) -> None:
    game_id = _find_game_id(client, "tower_defense_v1")
    response = client.get(f"/api/v1/games/{game_id}/templates")
    assert response.status_code == 200
    payload = response.json()

    defender_template = next(item for item in payload["templates"] if item["slot_key"] == "defender")
    assert "def place_tower(state):" in defender_template["code"]
    assert "return 0" in defender_template["code"]


def test_get_game_templates_for_turn_based_game(client) -> None:
    game_id = _find_game_id(client, "ttt_connect5_v1")
    response = client.get(f"/api/v1/games/{game_id}/templates")
    assert response.status_code == 200
    payload = response.json()

    assert payload["code_api_mode"] == "turn_based"
    bot_template = next(item for item in payload["templates"] if item["slot_key"] == "bot")
    assert "def make_choice(state):" in bot_template["code"]
    demo = next(item for item in payload["demo_strategies"] if item["slot_key"] == "bot")
    assert demo["strategy_id"] == "balanced_connect5"
    assert "find_winning_move" in demo["code"]


def test_get_game_templates_fallbacks_for_api_created_game_without_manifest(client, teacher_headers) -> None:
    created = client.post(
        "/api/v1/games",
        json={
            "slug": "api_only_templates_game",
            "title": "API Only Templates Game",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [
                {"key": "bot", "title": "Bot", "required": True},
            ],
        },
        headers=teacher_headers,
    )
    assert created.status_code == 200
    game = created.json()

    response = client.get(f"/api/v1/games/{game['game_id']}/templates")
    assert response.status_code == 200
    payload = response.json()
    assert payload["code_api_mode"] == "turn_based"
    assert payload["player_instruction"] is None
    assert [item["slot_key"] for item in payload["templates"]] == ["bot"]
    assert payload["demo_strategies"] == []


def test_get_game_templates_use_active_version_slots(client, teacher_headers) -> None:
    created = client.post(
        "/api/v1/games",
        json={
            "slug": "active_version_templates_game",
            "title": "Active Version Templates Game",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [
                {"key": "bot", "title": "Bot", "required": True},
            ],
        },
        headers=teacher_headers,
    )
    assert created.status_code == 200
    game = created.json()

    added = client.post(
        f"/api/v1/games/{game['game_id']}/versions",
        json={
            "semver": "1.1.0",
            "required_slots": [
                {"key": "captain", "title": "Captain", "required": True},
                {"key": "support", "title": "Support", "required": False},
            ],
        },
        headers=teacher_headers,
    )
    assert added.status_code == 200
    new_version = next(item for item in added.json()["versions"] if item["semver"] == "1.1.0")

    activated = client.post(
        f"/api/v1/games/{game['game_id']}/activate",
        json={"version_id": new_version["version_id"]},
        headers=teacher_headers,
    )
    assert activated.status_code == 200

    response = client.get(f"/api/v1/games/{game['game_id']}/templates")
    assert response.status_code == 200
    slots = [item["slot_key"] for item in response.json()["templates"]]
    assert slots == ["captain", "support"]
