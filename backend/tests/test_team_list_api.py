def test_list_teams_by_game_returns_only_requested_game(client, teacher_headers) -> None:
    game_a = client.post(
        "/api/v1/games",
        json={
            "slug": "list_teams_game_a",
            "title": "List Teams A",
            "mode": "single_task",
            "semver": "1.0.0",
            "required_slots": [{"key": "agent", "title": "Agent", "required": True}],
        },
        headers=teacher_headers,
    ).json()
    game_b = client.post(
        "/api/v1/games",
        json={
            "slug": "list_teams_game_b",
            "title": "List Teams B",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
        },
        headers=teacher_headers,
    ).json()

    team_a1 = client.post(
        "/api/v1/teams",
        json={"game_id": game_a["game_id"], "name": "Alpha A1", "captain_user_id": "captain-a1"},
    ).json()
    team_a2 = client.post(
        "/api/v1/teams",
        json={"game_id": game_a["game_id"], "name": "Alpha A2", "captain_user_id": "captain-a2"},
    ).json()
    _team_b = client.post(
        "/api/v1/teams",
        json={"game_id": game_b["game_id"], "name": "Bravo B1", "captain_user_id": "captain-b1"},
    ).json()

    response = client.get(f"/api/v1/teams?game_id={game_a['game_id']}")

    assert response.status_code == 200
    payload = response.json()
    ids = {item["team_id"] for item in payload}
    assert ids == {team_a1["team_id"], team_a2["team_id"]}
