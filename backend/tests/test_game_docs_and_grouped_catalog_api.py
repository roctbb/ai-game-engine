from __future__ import annotations


def test_game_docs_endpoint_returns_manifest_payload(client) -> None:
    games = client.get("/api/v1/games")
    assert games.status_code == 200
    maze = next(item for item in games.json() if item["slug"] == "maze_escape_v1")

    docs = client.get(f"/api/v1/games/{maze['game_id']}/docs")
    assert docs.status_code == 200
    payload = docs.json()
    assert payload["game_id"] == maze["game_id"]
    assert payload["slug"] == maze["slug"]
    assert payload["player_instruction"]
    assert payload["links"]
    assert payload["links"][0]["path"] == "player_guide_ru.md"
    assert "make_move" in payload["links"][0]["content"]


def test_embedded_games_have_player_docs(client) -> None:
    games = client.get("/api/v1/games")
    assert games.status_code == 200
    for game in games.json():
        docs = client.get(f"/api/v1/games/{game['game_id']}/docs")
        assert docs.status_code == 200
        payload = docs.json()
        assert payload["player_instruction"], game["slug"]
        assert payload["links"], game["slug"]
        assert payload["links"][0]["content"], game["slug"]


def test_grouped_single_task_catalog_endpoint(client) -> None:
    grouped = client.get("/api/v1/catalog/single-tasks/grouped")
    assert grouped.status_code == 200
    payload = grouped.json()
    assert isinstance(payload, list)
    if not payload:
        return
    first = payload[0]
    assert "topic" in first
    assert "difficulty" in first
    assert "items" in first
