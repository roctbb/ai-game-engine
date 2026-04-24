from __future__ import annotations


def test_game_versions_read_endpoints_return_versions_with_labels(client, teacher_headers) -> None:
    created = client.post(
        "/api/v1/games",
        json={
            "slug": "read_api_versions_game",
            "title": "Read API Versions Game",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_worker_labels": {"region": "eu-1"},
            "required_slots": [
                {
                    "key": "bot",
                    "title": "Bot",
                    "required": True,
                }
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
            "required_worker_labels": {"region": "eu-2", "accel": "gpu"},
            "required_slots": [
                {
                    "key": "bot",
                    "title": "Bot",
                    "required": True,
                }
            ],
        },
        headers=teacher_headers,
    )
    assert added.status_code == 200
    payload = added.json()
    latest = next(item for item in payload["versions"] if item["semver"] == "1.1.0")

    listed = client.get(f"/api/v1/games/{game['game_id']}/versions")
    assert listed.status_code == 200
    versions = listed.json()
    assert len(versions) == 2
    assert any(item["semver"] == "1.0.0" and item["required_worker_labels"] == {"region": "eu-1"} for item in versions)
    assert any(
        item["semver"] == "1.1.0" and item["required_worker_labels"] == {"region": "eu-2", "accel": "gpu"}
        for item in versions
    )

    by_id = client.get(f"/api/v1/games/{game['game_id']}/versions/{latest['version_id']}")
    assert by_id.status_code == 200
    assert by_id.json() == latest


def test_game_topics_endpoint_returns_topics(client, teacher_headers) -> None:
    created = client.post(
        "/api/v1/games",
        json={
            "slug": "read_api_topics_game",
            "title": "Read API Topics Game",
            "mode": "single_task",
            "semver": "1.0.0",
            "description": "Описание задачи",
            "difficulty": "easy",
            "topics": ["графы", "bfs"],
            "required_slots": [
                {
                    "key": "agent",
                    "title": "Agent",
                    "required": True,
                }
            ],
        },
        headers=teacher_headers,
    )
    assert created.status_code == 200
    game = created.json()

    response = client.get(f"/api/v1/games/{game['game_id']}/topics")
    assert response.status_code == 200
    assert response.json() == {"game_id": game["game_id"], "topics": ["графы", "bfs"]}


def test_get_game_version_returns_not_found_for_unknown_version(client) -> None:
    games = client.get("/api/v1/games").json()
    game_id = games[0]["game_id"]

    response = client.get(f"/api/v1/games/{game_id}/versions/gver_unknown")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
