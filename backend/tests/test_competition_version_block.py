def test_activate_game_version_blocked_during_running_competition(client, teacher_headers) -> None:
    game = client.post(
        "/api/v1/games",
        json={
            "slug": "activation_block_game",
            "title": "Activation Block Game",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
        },
        headers=teacher_headers,
    ).json()
    team_a = client.post(
        "/api/v1/teams",
        json={"game_id": game["game_id"], "name": "Alpha", "captain_user_id": "captain-a"},
    ).json()
    team_b = client.post(
        "/api/v1/teams",
        json={"game_id": game["game_id"], "name": "Bravo", "captain_user_id": "captain-b"},
    ).json()
    client.put(
        f"/api/v1/teams/{team_a['team_id']}/slots/bot",
        json={"actor_user_id": "captain-a", "code": "def make_choice(field, role):\n    return 0, 0\n"},
    )
    client.put(
        f"/api/v1/teams/{team_b['team_id']}/slots/bot",
        json={"actor_user_id": "captain-b", "code": "def make_choice(field, role):\n    return 0, 0\n"},
    )

    added = client.post(
        f"/api/v1/games/{game['game_id']}/versions",
        json={
            "semver": "1.1.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
        },
        headers=teacher_headers,
    ).json()
    next_version = next(item for item in added["versions"] if item["semver"] == "1.1.0")

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Running Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_a["team_id"]},
        headers=teacher_headers,
    )
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_b["team_id"]},
        headers=teacher_headers,
    )
    started = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": "teacher-activation"},
        headers=teacher_headers,
    ).json()
    assert started["status"] == "running"

    activation = client.post(
        f"/api/v1/games/{game['game_id']}/activate",
        json={"version_id": next_version["version_id"]},
        headers=teacher_headers,
    )
    assert activation.status_code == 409
    assert activation.json()["error"]["code"] == "conflict"
