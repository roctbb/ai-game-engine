from __future__ import annotations


def _student_headers(client, nickname: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": nickname, "role": "student"},
    )
    assert response.status_code == 200
    return {"X-Session-Id": response.json()["session_id"]}


def _maze_game(client, headers: dict[str, str]) -> dict:
    games = client.get("/api/v1/games", headers=headers).json()
    return next(item for item in games if item["slug"] == "maze_escape_v1")


def _multiplayer_game(client, headers: dict[str, str]) -> dict:
    games = client.get("/api/v1/games", headers=headers).json()
    return next(item for item in games if item["slug"] == "ttt_connect5_v1")


def test_student_can_only_operate_own_team(client, teacher_headers) -> None:
    alice_headers = _student_headers(client, "alice")
    bob_headers = _student_headers(client, "bob")
    game = _maze_game(client, alice_headers)

    alice_team = client.post(
        "/api/v1/teams",
        headers=alice_headers,
        json={
            "game_id": game["game_id"],
            "name": "Alice Team",
            "captain_user_id": "bob",
        },
    )
    assert alice_team.status_code == 200
    alice_team_payload = alice_team.json()
    assert alice_team_payload["captain_user_id"] == "alice"

    bob_team = client.post(
        "/api/v1/teams",
        headers=bob_headers,
        json={
            "game_id": game["game_id"],
            "name": "Bob Team",
            "captain_user_id": "alice",
        },
    )
    assert bob_team.status_code == 200
    assert bob_team.json()["captain_user_id"] == "bob"

    alice_code = client.put(
        f"/api/v1/teams/{alice_team_payload['team_id']}/slots/agent",
        headers=alice_headers,
        json={
            "actor_user_id": "bob",
            "code": "def make_move(state):\n    return 'right'\n",
        },
    )
    assert alice_code.status_code == 200

    bob_workspace = client.get(
        f"/api/v1/teams/{alice_team_payload['team_id']}/workspace",
        headers=bob_headers,
    )
    assert bob_workspace.status_code == 403
    assert bob_workspace.json()["error"]["code"] == "forbidden"

    bob_code_update = client.put(
        f"/api/v1/teams/{alice_team_payload['team_id']}/slots/agent",
        headers=bob_headers,
        json={
            "actor_user_id": "alice",
            "code": "def make_move(state):\n    return 'left'\n",
        },
    )
    assert bob_code_update.status_code == 403
    assert bob_code_update.json()["error"]["code"] == "forbidden"

    bob_start_run = client.post(
        f"/api/v1/single-tasks/{game['game_id']}/run",
        headers=bob_headers,
        json={
            "team_id": alice_team_payload["team_id"],
            "requested_by": "alice",
        },
    )
    assert bob_start_run.status_code == 403
    assert bob_start_run.json()["error"]["code"] == "forbidden"

    lobby_game = _multiplayer_game(client, teacher_headers)
    alice_lobby_team = client.post(
        "/api/v1/teams",
        headers=alice_headers,
        json={
            "game_id": lobby_game["game_id"],
            "name": "Alice Lobby Team",
            "captain_user_id": "alice",
        },
    ).json()

    lobby = client.post(
        "/api/v1/lobbies",
        headers=teacher_headers,
        json={
            "game_id": lobby_game["game_id"],
            "title": "Access Guard Lobby",
            "kind": "training",
            "access": "public",
            "max_teams": 8,
        },
    )
    assert lobby.status_code == 200
    lobby_id = lobby.json()["lobby_id"]

    for action_path, payload in (
        ("join", {}),
        ("ready", {"ready": True}),
        ("leave", None),
    ):
        method_payload = {"json": payload} if payload is not None else {}
        response = client.post(
            f"/api/v1/lobbies/{lobby_id}/teams/{alice_lobby_team['team_id']}/{action_path}",
            headers=bob_headers,
            **method_payload,
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"
