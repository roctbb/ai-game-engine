def _student_headers(client, nickname: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": nickname, "role": "student"},
    )
    assert response.status_code == 200
    return {"X-Session-Id": response.json()["session_id"]}


def _create_single_task_run(client, *, requested_by: str = "captain-replay") -> tuple[dict, dict]:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": f"Replay Team {requested_by}",
            "captain_user_id": requested_by,
        },
    ).json()
    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": requested_by,
            "run_kind": "single_task",
        },
    ).json()
    update_slot_response = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": requested_by, "code": "def make_move(state):\n    return 'right'\n"},
    )
    assert update_slot_response.status_code == 200, update_slot_response.json()
    queued_response = client.post(f"/api/v1/runs/{run['run_id']}/queue")
    assert queued_response.status_code == 200, queued_response.json()
    queued = queued_response.json()
    return game, queued


def test_replay_created_for_finished_run_and_available_via_api(client) -> None:
    game, run = _create_single_task_run(client, requested_by="captain-replay-finished")

    finish_response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/finished",
        json={
            "payload": {
                "status": "finished",
                "metrics": {"duration_ms": 42},
                "frames": [{"tick": 1, "phase": "running", "frame": {"x": 1}}],
                "events": [{"type": "move", "payload": {"dx": 1}}],
            }
        },
    )
    assert finish_response.status_code == 200

    replay_response = client.get(f"/api/v1/replays/runs/{run['run_id']}")
    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["run_id"] == run["run_id"]
    assert replay["status"] == "finished"
    assert replay["run_kind"] == "single_task"
    assert replay["summary"]["metrics"]["duration_ms"] == 42
    assert replay["frames"][0]["tick"] == 1
    assert replay["events"][0]["type"] == "move"

    captain_replay = client.get(
        f"/api/v1/replays/runs/{run['run_id']}",
        headers=_student_headers(client, "captain-replay-finished"),
    )
    assert captain_replay.status_code == 200

    anonymous_replay = client.get(
        f"/api/v1/replays/runs/{run['run_id']}",
        headers={"X-Test-No-Session": "1"},
    )
    assert anonymous_replay.status_code == 401

    unrelated_replay = client.get(
        f"/api/v1/replays/runs/{run['run_id']}",
        headers=_student_headers(client, "unrelated-replay"),
    )
    assert unrelated_replay.status_code == 403

    listing = client.get(f"/api/v1/replays?game_id={game['game_id']}&run_kind=single_task")
    assert listing.status_code == 200
    items = listing.json()
    assert any(item["run_id"] == run["run_id"] for item in items)
    listed_replay = next(item for item in items if item["run_id"] == run["run_id"])
    assert listed_replay["frames"] == []
    assert listed_replay["events"] == []
    assert listed_replay["summary"]["metrics"]["duration_ms"] == 42

    student_listing = client.get(
        f"/api/v1/replays?game_id={game['game_id']}&run_kind=single_task",
        headers=_student_headers(client, "captain-replay-finished"),
    )
    assert student_listing.status_code == 403


def test_replay_created_for_failed_run_with_error_summary(client) -> None:
    _, run = _create_single_task_run(client, requested_by="captain-replay-failed")

    fail_response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/failed",
        json={"message": "engine crashed"},
    )
    assert fail_response.status_code == 200

    replay_response = client.get(f"/api/v1/replays/runs/{run['run_id']}")
    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["status"] == "failed"
    assert replay["summary"]["error_message"] == "engine crashed"
    assert replay["events"][-1]["type"] == "run_error"
