def test_catalog_is_seeded_from_game_manifests(client) -> None:
    games = client.get("/api/v1/games").json()
    by_slug = {game["slug"]: game for game in games}

    assert "maze_escape_v1" in by_slug
    assert "coins_right_down_v1" in by_slug
    assert "tower_defense_v1" in by_slug
    assert "ttt_connect5_v1" in by_slug
    assert "tanks_ctf_v1" in by_slug
    assert "tanks_ai_legacy_v1" in by_slug
    assert "tanks_lobby_v1" not in by_slug
    assert "archer_duel_lite_v1" not in by_slug
    assert "beacon_duel_v1" not in by_slug
    assert "hill_control_v1" not in by_slug
    assert "jump_gem_duel_v1" not in by_slug
    assert "blinking_gem_duel_v1" not in by_slug
    assert "relic_delivery_duel_v1" not in by_slug
    assert "template_v1" not in by_slug
    assert by_slug["tower_defense_v1"]["versions"][0]["required_slot_keys"] == ["defender"]
    assert by_slug["tower_defense_v1"]["difficulty"] == "medium"
    assert by_slug["tower_defense_v1"]["learning_section"] == "Жадные стратегии"
    assert "симуляция" in by_slug["tower_defense_v1"]["topics"]
    assert by_slug["maze_escape_v1"]["description"] is not None
    assert by_slug["maze_escape_v1"]["catalog_metadata_status"] == "ready"
