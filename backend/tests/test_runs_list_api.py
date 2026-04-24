def _create_team(client, game_id: str, name: str, captain: str) -> dict:
    return client.post(
        "/api/v1/teams",
        json={"game_id": game_id, "name": name, "captain_user_id": captain},
    ).json()


def test_list_runs_supports_lobby_and_kind_filters(client) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "ttt_connect5_v1")

    team_a = _create_team(client, game_id=game["game_id"], name="Team A", captain="captain-a")
    team_b = _create_team(client, game_id=game["game_id"], name="Team B", captain="captain-b")

    run_a = client.post(
        "/api/v1/runs",
        json={
            "team_id": team_a["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-a",
            "run_kind": "training_match",
            "lobby_id": "lobby-1",
        },
    ).json()
    _run_b = client.post(
        "/api/v1/runs",
        json={
            "team_id": team_b["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-b",
            "run_kind": "competition_match",
            "lobby_id": "lobby-2",
        },
    ).json()

    by_lobby = client.get("/api/v1/runs?lobby_id=lobby-1")
    assert by_lobby.status_code == 200
    lobby_ids = {item["lobby_id"] for item in by_lobby.json()}
    assert lobby_ids == {"lobby-1"}
    assert {item["run_id"] for item in by_lobby.json()} == {run_a["run_id"]}

    by_kind = client.get("/api/v1/runs?run_kind=competition_match")
    assert by_kind.status_code == 200
    assert all(item["run_kind"] == "competition_match" for item in by_kind.json())


def test_list_runs_preserves_error_message_for_canceled_lobby_runs(client) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "ttt_connect5_v1")

    team = _create_team(client, game_id=game["game_id"], name="Cancel Team", captain="captain-cancel")
    created = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-cancel",
            "run_kind": "training_match",
            "lobby_id": "lobby-cancel-1",
        },
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]

    canceled = client.post(f"/api/v1/runs/{run_id}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert canceled.json()["error_message"] == "manual_cancel"

    listed = client.get("/api/v1/runs?lobby_id=lobby-cancel-1")
    assert listed.status_code == 200
    assert listed.json()
    only = listed.json()[0]
    assert only["run_id"] == run_id
    assert only["status"] == "canceled"
    assert only["error_message"] == "manual_cancel"
