def test_create_run_rejects_mismatched_game_and_team(client) -> None:
    games = client.get("/api/v1/games").json()
    maze = next(item for item in games if item["slug"] == "maze_escape_v1")
    ttt = next(item for item in games if item["slug"] == "ttt_connect5_v1")

    team = client.post(
        "/api/v1/teams",
        json={"game_id": maze["game_id"], "name": "Maze Team", "captain_user_id": "captain-mismatch"},
    ).json()

    response = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": ttt["game_id"],
            "requested_by": "captain-mismatch",
            "run_kind": "single_task",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invariant_violation"


def test_create_run_rejects_unknown_target_version(client) -> None:
    games = client.get("/api/v1/games").json()
    maze = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={"game_id": maze["game_id"], "name": "Maze Team 2", "captain_user_id": "captain-version"},
    ).json()

    response = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": maze["game_id"],
            "requested_by": "captain-version",
            "run_kind": "single_task",
            "version_id": "missing-version",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
