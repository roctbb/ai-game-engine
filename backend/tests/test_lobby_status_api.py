def _create_game(client, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/games",
        json={
            "slug": "lobby_status_flow_game",
            "title": "Lobby Status Flow",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
        },
        headers=headers,
    )
    return response.json()


def _create_ready_team(client, game_id: str, captain: str, name: str) -> dict:
    team = client.post(
        "/api/v1/teams",
        json={"game_id": game_id, "name": name, "captain_user_id": captain},
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/bot",
        json={"actor_user_id": captain, "code": "def make_choice(field, role):\n    return 0, 0\n"},
    )
    return team


def _create_lobby(client, game_id: str, headers: dict[str, str]) -> dict:
    return client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game_id,
            "title": "Lobby Status",
            "kind": "training",
            "access": "public",
            "max_teams": 8,
        },
        headers=headers,
    ).json()


def test_training_lobby_status_controls_and_ready_guard(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="captain-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="captain-b", name="Bravo")

    lobby = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team_a['team_id']}/join",
        json={},
        headers=teacher_headers,
    )
    ready_response = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team_a['team_id']}/ready",
        json={"ready": True},
        headers=teacher_headers,
    )
    assert ready_response.status_code == 200
    assert ready_response.json()["teams"][0]["ready"] is True

    paused = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/status",
        json={"status": "paused"},
        headers=teacher_headers,
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    blocked_ready_toggle = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team_a['team_id']}/ready",
        json={"ready": False},
        headers=teacher_headers,
    )
    assert blocked_ready_toggle.status_code == 422

    reopened = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/status",
        json={"status": "open"},
        headers=teacher_headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"

    unready = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team_a['team_id']}/ready",
        json={"ready": False},
        headers=teacher_headers,
    )
    assert unready.status_code == 200
    team_state = next(item for item in unready.json()["teams"] if item["team_id"] == team_a["team_id"])
    assert team_state["ready"] is False

    closed = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/status",
        json={"status": "closed"},
        headers=teacher_headers,
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    closed_team_state = next(item for item in closed.json()["teams"] if item["team_id"] == team_a["team_id"])
    assert closed_team_state["ready"] is False
    assert "закрыто" in (closed_team_state["blocker_reason"] or "").lower()

    reopen_from_closed = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/status",
        json={"status": "open"},
        headers=teacher_headers,
    )
    assert reopen_from_closed.status_code == 422

    join_closed = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team_b['team_id']}/join",
        json={},
        headers=teacher_headers,
    )
    assert join_closed.status_code == 422


def test_lobby_admin_mutations_require_teacher_or_admin(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    student_session = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": "student-lobby", "role": "student"},
    )
    assert student_session.status_code == 200
    student_headers = {"X-Session-Id": student_session.json()["session_id"]}

    created_by_teacher = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)

    student_create = client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game["game_id"],
            "title": "Student Lobby",
            "kind": "training",
            "access": "public",
            "max_teams": 8,
        },
        headers=student_headers,
    )
    assert student_create.status_code == 403

    student_status_change = client.post(
        f"/api/v1/lobbies/{created_by_teacher['lobby_id']}/status",
        json={"status": "paused"},
        headers=student_headers,
    )
    assert student_status_change.status_code == 403


def test_lobby_participant_actions_require_session(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    team = _create_ready_team(client, game_id=game["game_id"], captain="captain-sess", name="Sess Team")
    lobby = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)

    join_without_session = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
        json={},
    )
    assert join_without_session.status_code == 422
