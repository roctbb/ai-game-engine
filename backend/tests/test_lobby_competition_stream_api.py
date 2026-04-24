import json


def _extract_data_lines(payload: str) -> list[dict]:
    items: list[dict] = []
    for line in payload.splitlines():
        if not line.startswith("data: "):
            continue
        items.append(json.loads(line.replace("data: ", "")))
    return items


def _first_non_single_game(client) -> dict:
    games = client.get("/api/v1/games").json()
    return next(item for item in games if item["mode"] != "single_task")


def test_lobby_stream_emits_lobby_event(client, teacher_headers) -> None:
    game = _first_non_single_game(client)
    lobby = client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game["game_id"],
            "title": "Stream Lobby",
            "kind": "training",
            "access": "public",
            "max_teams": 8,
        },
        headers=teacher_headers,
    ).json()

    with client.stream(
        "GET",
        f"/api/v1/lobbies/{lobby['lobby_id']}/stream?poll_interval_ms=10&max_events=1",
    ) as response:
        assert response.status_code == 200
        payload = "".join(response.iter_text())

    assert "event: agp.update" in payload
    data_items = _extract_data_lines(payload)
    assert data_items
    first = data_items[0]
    assert first["channel"] == "lobby"
    assert first["entity_id"] == lobby["lobby_id"]
    assert first["kind"] == "snapshot"
    assert first["status"] == "open"


def test_lobbies_stream_emits_lobby_collection_event(client, teacher_headers) -> None:
    game = _first_non_single_game(client)
    lobby = client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game["game_id"],
            "title": "Stream Lobby Collection",
            "kind": "training",
            "access": "public",
            "max_teams": 8,
        },
        headers=teacher_headers,
    ).json()

    with client.stream(
        "GET",
        "/api/v1/lobbies/stream?poll_interval_ms=10&max_events=1",
    ) as response:
        assert response.status_code == 200
        payload = "".join(response.iter_text())

    assert "event: agp.update" in payload
    data_items = _extract_data_lines(payload)
    assert data_items
    first = data_items[0]
    assert first["channel"] == "lobbies"
    assert first["entity_id"] == "collection"
    assert first["kind"] == "snapshot"
    assert any(item["lobby_id"] == lobby["lobby_id"] for item in first["payload"]["items"])


def test_competition_stream_emits_competition_event(client, teacher_headers) -> None:
    game = _first_non_single_game(client)
    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Stream Competition",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()

    with client.stream(
        "GET",
        f"/api/v1/competitions/{competition['competition_id']}/stream?poll_interval_ms=10&max_events=1",
    ) as response:
        assert response.status_code == 200
        payload = "".join(response.iter_text())

    assert "event: agp.update" in payload
    data_items = _extract_data_lines(payload)
    assert data_items
    first = data_items[0]
    assert first["channel"] == "competition"
    assert first["entity_id"] == competition["competition_id"]
    assert first["kind"] == "snapshot"
    assert first["status"] == "draft"
