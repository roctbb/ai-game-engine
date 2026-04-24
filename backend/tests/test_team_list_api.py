def _student_headers(client, nickname: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": nickname, "role": "student"},
    )
    assert response.status_code == 200
    return {"X-Session-Id": response.json()["session_id"]}


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


def test_student_list_teams_by_game_returns_only_own_player(client, teacher_headers) -> None:
    game = client.post(
        "/api/v1/games",
        json={
            "slug": "list_teams_student_scope",
            "title": "List Teams Student Scope",
            "mode": "single_task",
            "semver": "1.0.0",
            "required_slots": [{"key": "agent", "title": "Agent", "required": True}],
        },
        headers=teacher_headers,
    ).json()
    own_team = client.post(
        "/api/v1/teams",
        json={"game_id": game["game_id"], "name": "Own Player", "captain_user_id": "student-team-list"},
        headers=teacher_headers,
    ).json()
    other_team = client.post(
        "/api/v1/teams",
        json={"game_id": game["game_id"], "name": "Other Player", "captain_user_id": "other-team-list"},
        headers=teacher_headers,
    ).json()

    response = client.get(
        f"/api/v1/teams?game_id={game['game_id']}",
        headers=_student_headers(client, "student-team-list"),
    )

    assert response.status_code == 200
    ids = {item["team_id"] for item in response.json()}
    assert own_team["team_id"] in ids
    assert other_team["team_id"] not in ids


def test_create_team_is_idempotent_per_user_and_game(client, teacher_headers) -> None:
    game = client.post(
        "/api/v1/games",
        json={
            "slug": "single_player_per_game",
            "title": "Single Player Per Game",
            "mode": "single_task",
            "semver": "1.0.0",
            "required_slots": [{"key": "agent", "title": "Agent", "required": True}],
        },
        headers=teacher_headers,
    ).json()
    headers = _student_headers(client, "single-player")

    first = client.post(
        "/api/v1/teams",
        json={"game_id": game["game_id"], "name": "First Name", "captain_user_id": "ignored"},
        headers=headers,
    )
    second = client.post(
        "/api/v1/teams",
        json={"game_id": game["game_id"], "name": "Second Name", "captain_user_id": "ignored"},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["team_id"] == first.json()["team_id"]
