def _create_team(client, game_id: str, name: str, captain: str) -> dict:
    return client.post(
        "/api/v1/teams",
        json={"game_id": game_id, "name": name, "captain_user_id": captain},
    ).json()


def _student_headers(client, nickname: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": nickname, "role": "student"},
    )
    assert response.status_code == 200
    return {"X-Session-Id": response.json()["session_id"]}


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


def test_list_runs_omits_heavy_result_payload_fields(client) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "ttt_connect5_v1")
    team = _create_team(client, game_id=game["game_id"], name="Payload Team", captain="payload-captain")
    slot = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/bot",
        json={"actor_user_id": "payload-captain", "code": "def move():\n    return None\n"},
    )
    assert slot.status_code == 200
    created = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "payload-captain",
            "run_kind": "training_match",
            "lobby_id": "lobby-heavy-payload",
        },
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    queued = client.post(f"/api/v1/runs/{run_id}/queue")
    assert queued.status_code == 200
    finished = client.post(
        f"/api/v1/internal/runs/{run_id}/finished",
        json={
                "payload": {
                    "status": "ok",
                    "frames": {"blob": {"value": "x" * 100_000}},
                "scores": {team["team_id"]: 42},
                "placements": {team["team_id"]: 1},
                "metrics": {"score": 42},
            }
        },
    )
    assert finished.status_code == 200, finished.text

    listed = client.get("/api/v1/runs?lobby_id=lobby-heavy-payload")
    assert listed.status_code == 200
    payload = listed.json()[0]["result_payload"]
    assert payload is None

    detailed = client.get(f"/api/v1/runs/{run_id}")
    assert detailed.status_code == 200
    assert detailed.json()["result_payload"]["frames"]

    compact = client.get(f"/api/v1/runs/{run_id}?compact_payload=true")
    assert compact.status_code == 200
    compact_payload = compact.json()["result_payload"]
    assert "frames" not in compact_payload
    assert compact_payload["scores"] == {team["team_id"]: 42}


def test_student_list_runs_only_returns_visible_runs_and_generic_create_is_restricted(client) -> None:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "ttt_connect5_v1")

    alice_team = _create_team(client, game_id=game["game_id"], name="Alice Runs", captain="runs-alice")
    bob_team = _create_team(client, game_id=game["game_id"], name="Bob Runs", captain="runs-bob")
    alice_run = client.post(
        "/api/v1/runs",
        json={
            "team_id": alice_team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "runs-alice",
            "run_kind": "single_task",
        },
    ).json()
    bob_run = client.post(
        "/api/v1/runs",
        json={
            "team_id": bob_team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "runs-bob",
            "run_kind": "single_task",
        },
    ).json()

    alice_headers = _student_headers(client, "runs-alice")
    listed = client.get(f"/api/v1/runs?game_id={game['game_id']}", headers=alice_headers)

    assert listed.status_code == 200
    run_ids = {item["run_id"] for item in listed.json()}
    assert alice_run["run_id"] in run_ids
    assert bob_run["run_id"] not in run_ids

    denied_create = client.post(
        "/api/v1/runs",
        headers=alice_headers,
        json={
            "team_id": alice_team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "runs-alice",
            "run_kind": "training_match",
            "lobby_id": "manual-lobby",
        },
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["error"]["code"] == "forbidden"
