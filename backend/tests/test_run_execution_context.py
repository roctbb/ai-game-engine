def test_worker_execution_context_contains_manifest_and_snapshot(client) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": "Execution Context Team",
            "captain_user_id": "captain-context",
        },
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": "captain-context", "code": "print('context')"},
    )

    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-context",
            "run_kind": "single_task",
        },
    ).json()
    queued = client.post(f"/api/v1/runs/{run['run_id']}/queue").json()

    context = client.get(f"/api/v1/internal/runs/{run['run_id']}/execution-context")

    assert context.status_code == 200
    payload = context.json()
    assert payload["run_id"] == run["run_id"]
    assert payload["team_id"] == team["team_id"]
    assert payload["game_slug"] == "maze_escape_v1"
    assert payload["game_package_dir"] == "maze_escape"
    assert payload["code_api_mode"] == "script_based"
    assert payload["engine_entrypoint"] == "engine.py"
    assert payload["snapshot_id"] == queued["snapshot_id"]
    assert payload["codes_by_slot"]["agent"] == "print('context')\n"


def test_worker_execution_context_requires_internal_token(client) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": "Execution Context Guard Team",
            "captain_user_id": "captain-context-guard",
        },
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": "captain-context-guard", "code": "print('guard')"},
    )
    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-context-guard",
            "run_kind": "single_task",
        },
    ).json()
    client.post(f"/api/v1/runs/{run['run_id']}/queue")

    response = client.get(
        f"/api/v1/internal/runs/{run['run_id']}/execution-context",
        headers={"X-Test-No-Internal-Token": "1"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_worker_execution_context_requires_queued_run(client) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")
    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": "Unqueued Team",
            "captain_user_id": "captain-unqueued",
        },
    ).json()
    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-unqueued",
            "run_kind": "single_task",
        },
    ).json()

    response = client.get(f"/api/v1/internal/runs/{run['run_id']}/execution-context")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invariant_violation"


def test_lobby_execution_context_contains_scheduled_participants(client, teacher_headers) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "tanks_ai_legacy_v1")
    lobby = client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game["game_id"],
            "title": "Context Participants",
            "kind": "training",
            "access": "public",
            "max_teams": 8,
        },
        headers=teacher_headers,
    ).json()

    teams = []
    for name, captain, code in (
        ("Alpha", "alpha-context", "def make_choice(x, y, field):\n    return 'go_right'\n"),
        ("Bravo", "bravo-context", "def make_choice(x, y, field):\n    return 'go_left'\n"),
    ):
        team = client.post(
            "/api/v1/teams",
            json={"game_id": game["game_id"], "name": name, "captain_user_id": captain},
            headers=teacher_headers,
        ).json()
        client.put(
            f"/api/v1/teams/{team['team_id']}/slots/bot",
            json={"actor_user_id": captain, "code": code},
            headers=teacher_headers,
        )
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        ready = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
            json={"ready": True},
            headers=teacher_headers,
        ).json()
        teams.append(team)

    assert len(ready["last_scheduled_run_ids"]) == 2
    context = client.get(f"/api/v1/internal/runs/{ready['last_scheduled_run_ids'][0]}/execution-context")

    assert context.status_code == 200
    participants = context.json()["participants"]
    assert {item["team_id"] for item in participants} == {team["team_id"] for team in teams}
    assert {item["display_name"] for item in participants} == {"Alpha", "Bravo"}
    assert all(item["codes_by_slot"]["bot"].startswith("def make_choice") for item in participants)
