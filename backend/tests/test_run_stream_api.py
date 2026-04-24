import json


def _extract_data_lines(payload: str) -> list[dict]:
    items: list[dict] = []
    for line in payload.splitlines():
        if not line.startswith("data: "):
            continue
        items.append(json.loads(line.replace("data: ", "")))
    return items


def _create_ready_single_task_run(client, requested_by: str) -> dict:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": f"Stream Team {requested_by}",
            "captain_user_id": requested_by,
        },
    ).json()
    code_response = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={
            "actor_user_id": requested_by,
            "code": "def make_move(state):\n    return 'right'\n",
        },
    )
    assert code_response.status_code == 200, code_response.json()

    created = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": requested_by,
            "run_kind": "single_task",
        },
    ).json()
    return created


def test_run_stream_emits_created_status(client) -> None:
    run = _create_ready_single_task_run(client, requested_by="captain-stream-created")

    with client.stream(
        "GET",
        f"/api/v1/runs/{run['run_id']}/stream?poll_interval_ms=10&max_events=1",
    ) as response:
        assert response.status_code == 200
        payload = "".join(response.iter_text())

    assert "event: agp.update" in payload
    data_items = _extract_data_lines(payload)
    assert data_items
    first = data_items[0]
    assert first["channel"] == "run"
    assert first["entity_id"] == run["run_id"]
    assert first["kind"] == "snapshot"
    assert first["status"] == "created"
    assert first["payload"]["run_id"] == run["run_id"]


def test_run_stream_emits_terminal_event_for_finished_run(client) -> None:
    run = _create_ready_single_task_run(client, requested_by="captain-stream-finished")
    queued = client.post(f"/api/v1/runs/{run['run_id']}/queue").json()

    start_response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/started",
        json={"worker_id": "worker-stream-1"},
    )
    if start_response.status_code == 404:
        register = client.post(
            "/api/v1/internal/workers/register",
            json={
                "worker_id": "worker-stream-1",
                "hostname": "stream-host",
                "capacity_total": 1,
                "labels": {},
            },
        )
        assert register.status_code == 200, register.json()
        start_response = client.post(
            f"/api/v1/internal/runs/{run['run_id']}/started",
            json={"worker_id": "worker-stream-1"},
        )
    assert start_response.status_code == 200, start_response.json()

    finish_response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/finished",
        json={"payload": {"status": "finished", "metrics": {"duration_ms": 10}}},
    )
    assert finish_response.status_code == 200, finish_response.json()

    with client.stream(
        "GET",
        f"/api/v1/runs/{run['run_id']}/stream?poll_interval_ms=10",
    ) as response:
        assert response.status_code == 200
        payload = "".join(response.iter_text())

    assert "event: agp.update" in payload
    assert "event: agp.terminal" in payload
    data_items = _extract_data_lines(payload)
    terminal_payload = next(item for item in data_items if item.get("kind") == "terminal")
    assert terminal_payload["channel"] == "run"
    assert terminal_payload["entity_id"] == run["run_id"]
    assert terminal_payload["status"] == "finished"
    assert queued["run_id"] == run["run_id"]


def test_run_stream_emits_terminal_event_for_canceled_run(client) -> None:
    run = _create_ready_single_task_run(client, requested_by="captain-stream-canceled")
    canceled = client.post(f"/api/v1/runs/{run['run_id']}/cancel")
    assert canceled.status_code == 200, canceled.json()
    assert canceled.json()["status"] == "canceled"
    assert canceled.json()["error_message"] == "manual_cancel"

    with client.stream(
        "GET",
        f"/api/v1/runs/{run['run_id']}/stream?poll_interval_ms=10",
    ) as response:
        assert response.status_code == 200
        payload = "".join(response.iter_text())

    assert "event: agp.update" in payload
    assert "event: agp.terminal" in payload
    data_items = _extract_data_lines(payload)
    snapshot_payload = next(item for item in data_items if item.get("kind") == "snapshot")
    terminal_payload = next(item for item in data_items if item.get("kind") == "terminal")

    assert snapshot_payload["status"] == "canceled"
    assert snapshot_payload["payload"]["status"] == "canceled"
    assert snapshot_payload["payload"]["error_message"] == "manual_cancel"
    assert terminal_payload["channel"] == "run"
    assert terminal_payload["entity_id"] == run["run_id"]
    assert terminal_payload["status"] == "canceled"
