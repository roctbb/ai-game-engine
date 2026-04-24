from game_catalog.domain.model import SlotDefinition


def test_snapshot_fixed_on_queue_not_on_run_creation(client):
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": "Team Freeze",
            "captain_user_id": "captain-1",
        },
    ).json()

    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-1",
        },
    ).json()
    assert run["snapshot_id"] is None

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": "captain-1", "code": "print('v1')"},
    )

    queued = client.post(f"/api/v1/runs/{run['run_id']}/queue").json()
    assert queued["status"] == "queued"
    first_revision = queued["revisions_by_slot"]["agent"]

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": "captain-1", "code": "print('v2')"},
    )

    frozen = client.get(f"/api/v1/runs/{run['run_id']}").json()
    assert frozen["revisions_by_slot"]["agent"] == first_revision


def test_queue_uses_explicit_target_version_for_snapshot(client, container):
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    target_version = container.game_catalog.add_game_version(
        game_id=game["game_id"],
        semver="9.9.9",
        required_slots=(SlotDefinition(key="agent", title="Agent", required=True),),
    )

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": "Team Target Version",
            "captain_user_id": "captain-target",
        },
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": "captain-target", "code": "print('target')"},
    )

    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-target",
            "run_kind": "single_task",
            "version_id": target_version.version_id,
        },
    ).json()
    queued = client.post(f"/api/v1/runs/{run['run_id']}/queue").json()

    assert queued["target_version_id"] == target_version.version_id
    assert queued["snapshot_version_id"] == target_version.version_id


def test_snapshot_boundary_is_queue_transition_for_each_run(client):
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")

    team = client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": "Team Queue Boundary",
            "captain_user_id": "captain-boundary",
        },
    ).json()

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": "captain-boundary", "code": "print('v1')"},
    )

    run_a_response = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-boundary",
            "run_kind": "training_match",
        },
    )
    assert run_a_response.status_code == 200, run_a_response.json()
    run_a = run_a_response.json()

    run_b_response = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain-boundary",
            "run_kind": "training_match",
        },
    )
    assert run_b_response.status_code == 200, run_b_response.json()
    run_b = run_b_response.json()

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": "captain-boundary", "code": "print('v2')"},
    )

    queued_a = client.post(f"/api/v1/runs/{run_a['run_id']}/queue").json()
    assert queued_a["status"] == "queued"
    assert queued_a["revisions_by_slot"]["agent"] == 2

    context_a_before = client.get(f"/api/v1/internal/runs/{run_a['run_id']}/execution-context").json()
    assert context_a_before["codes_by_slot"]["agent"] == "print('v2')\n"

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={"actor_user_id": "captain-boundary", "code": "print('v3')"},
    )

    queued_b = client.post(f"/api/v1/runs/{run_b['run_id']}/queue").json()
    assert queued_b["status"] == "queued"
    assert queued_b["revisions_by_slot"]["agent"] == 3

    context_a_after = client.get(f"/api/v1/internal/runs/{run_a['run_id']}/execution-context").json()
    context_b = client.get(f"/api/v1/internal/runs/{run_b['run_id']}/execution-context").json()

    assert context_a_after["codes_by_slot"]["agent"] == "print('v2')\n"
    assert context_b["codes_by_slot"]["agent"] == "print('v3')\n"


def test_snapshot_boundary_is_independent_for_same_team_in_multiple_lobbies(client, teacher_headers):
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "ttt_connect5_v1")

    def _create_team(team_name: str, captain: str) -> dict:
        team = client.post(
            "/api/v1/teams",
            json={
                "game_id": game["game_id"],
                "name": team_name,
                "captain_user_id": captain,
            },
        ).json()
        client.put(
            f"/api/v1/teams/{team['team_id']}/slots/bot",
            json={
                "actor_user_id": captain,
                "code": "def make_move(state, memory):\n    return {'row': 0, 'col': 0}, memory\n",
            },
        )
        return team

    team_a = _create_team(team_name="Alpha", captain="cap-alpha")
    team_b = _create_team(team_name="Bravo", captain="cap-bravo")
    team_c = _create_team(team_name="Charlie", captain="cap-charlie")

    def _create_lobby(title: str) -> dict:
        return client.post(
            "/api/v1/lobbies",
            json={
                "game_id": game["game_id"],
                "title": title,
                "kind": "training",
                "access": "public",
                "max_teams": 16,
            },
            headers=teacher_headers,
        ).json()

    lobby_a = _create_lobby("Snapshot Lobby A")
    lobby_b = _create_lobby("Snapshot Lobby B")

    def _join_and_ready(lobby_id: str, team_id: str) -> None:
        join_response = client.post(
            f"/api/v1/lobbies/{lobby_id}/teams/{team_id}/join",
            json={},
            headers=teacher_headers,
        )
        assert join_response.status_code == 200, join_response.json()
        ready_response = client.post(
            f"/api/v1/lobbies/{lobby_id}/teams/{team_id}/ready",
            json={"ready": True},
            headers=teacher_headers,
        )
        assert ready_response.status_code == 200, ready_response.json()

    _join_and_ready(lobby_a["lobby_id"], team_a["team_id"])

    client.put(
        f"/api/v1/teams/{team_a['team_id']}/slots/bot",
        json={
            "actor_user_id": "cap-alpha",
            "code": "def make_move(state, memory):\n    return {'row': 1, 'col': 1}, memory\n",
        },
    )

    _join_and_ready(lobby_a["lobby_id"], team_b["team_id"])

    runs_lobby_a = client.get(f"/api/v1/runs?lobby_id={lobby_a['lobby_id']}").json()
    run_a = next(item for item in runs_lobby_a if item["team_id"] == team_a["team_id"])
    assert run_a["status"] == "queued"
    assert run_a["revisions_by_slot"]["bot"] == 2

    client.put(
        f"/api/v1/teams/{team_a['team_id']}/slots/bot",
        json={
            "actor_user_id": "cap-alpha",
            "code": "def make_move(state, memory):\n    return {'row': 2, 'col': 2}, memory\n",
        },
    )

    _join_and_ready(lobby_b["lobby_id"], team_a["team_id"])

    client.put(
        f"/api/v1/teams/{team_a['team_id']}/slots/bot",
        json={
            "actor_user_id": "cap-alpha",
            "code": "def make_move(state, memory):\n    return {'row': 3, 'col': 3}, memory\n",
        },
    )

    _join_and_ready(lobby_b["lobby_id"], team_c["team_id"])

    runs_lobby_b = client.get(f"/api/v1/runs?lobby_id={lobby_b['lobby_id']}").json()
    run_b = next(item for item in runs_lobby_b if item["team_id"] == team_a["team_id"])
    assert run_b["status"] == "queued"
    assert run_b["revisions_by_slot"]["bot"] == 4

    context_a = client.get(f"/api/v1/internal/runs/{run_a['run_id']}/execution-context").json()
    context_b = client.get(f"/api/v1/internal/runs/{run_b['run_id']}/execution-context").json()

    assert "row': 1" in context_a["codes_by_slot"]["bot"]
    assert "col': 1" in context_a["codes_by_slot"]["bot"]
    assert "row': 3" in context_b["codes_by_slot"]["bot"]
    assert "col': 3" in context_b["codes_by_slot"]["bot"]
