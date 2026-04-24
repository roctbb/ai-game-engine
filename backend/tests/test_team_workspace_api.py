def _create_maze_team(client, captain_user_id: str, name: str) -> dict:
    games = client.get("/api/v1/games").json()
    game = next(item for item in games if item["slug"] == "maze_escape_v1")
    return client.post(
        "/api/v1/teams",
        json={
            "game_id": game["game_id"],
            "name": name,
            "captain_user_id": captain_user_id,
        },
    ).json()


def test_workspace_endpoint_returns_slot_code_and_required_flag(client) -> None:
    team = _create_maze_team(
        client,
        captain_user_id="captain-workspace",
        name="Workspace API Team",
    )

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={
            "actor_user_id": "captain-workspace",
            "code": "def make_move(state):\n    return 'right'\n",
        },
    )
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/legacy_slot",
        json={
            "actor_user_id": "captain-workspace",
            "code": "print('legacy')\n",
        },
    )

    workspace = client.get(f"/api/v1/teams/{team['team_id']}/workspace")
    assert workspace.status_code == 200
    payload = workspace.json()

    required_slot = next(item for item in payload["slot_states"] if item["slot_key"] == "agent")
    assert required_slot["required"] is True
    assert required_slot["state"] == "filled"
    assert required_slot["code"] == "def make_move(state):\n    return 'right'\n"
    assert required_slot["revision"] == 1

    incompatible_slot = next(item for item in payload["slot_states"] if item["slot_key"] == "legacy_slot")
    assert incompatible_slot["required"] is False
    assert incompatible_slot["state"] == "incompatible"
    assert incompatible_slot["code"] == "print('legacy')\n"
    assert incompatible_slot["revision"] == 1


def test_workspace_rejects_input_call_in_user_code(client) -> None:
    team = _create_maze_team(
        client,
        captain_user_id="captain-input-guard",
        name="Workspace Input Guard Team",
    )

    response = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={
            "actor_user_id": "captain-input-guard",
            "code": "name = input('who?')\nprint(name)\n",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invariant_violation"
    assert "input()" in payload["error"]["message"]


def test_workspace_rejects_builtins_input_alias_calls(client) -> None:
    team = _create_maze_team(
        client,
        captain_user_id="captain-builtins-input",
        name="Workspace Builtins Input Guard Team",
    )

    via_module = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={
            "actor_user_id": "captain-builtins-input",
            "code": "import builtins\nname = builtins.input('who?')\nprint(name)\n",
        },
    )
    assert via_module.status_code == 422
    assert via_module.json()["error"]["code"] == "invariant_violation"

    via_import_alias = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={
            "actor_user_id": "captain-builtins-input",
            "code": "from builtins import input as ask\nname = ask('who?')\nprint(name)\n",
        },
    )
    assert via_import_alias.status_code == 422
    assert via_import_alias.json()["error"]["code"] == "invariant_violation"

    via_dynamic_import = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={
            "actor_user_id": "captain-builtins-input",
            "code": "name = __import__('builtins').input('who?')\nprint(name)\n",
        },
    )
    assert via_dynamic_import.status_code == 422
    assert via_dynamic_import.json()["error"]["code"] == "invariant_violation"


def test_workspace_allows_literal_input_text_in_invalid_code(client) -> None:
    team = _create_maze_team(
        client,
        captain_user_id="captain-input-literal",
        name="Workspace Input Literal Team",
    )

    response = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={
            "actor_user_id": "captain-input-literal",
            "code": "def broken()\n    return 'right'  # input(\n",
        },
    )

    assert response.status_code == 200, response.json()

    workspace = client.get(f"/api/v1/teams/{team['team_id']}/workspace")
    assert workspace.status_code == 200, workspace.json()
    slot = next(item for item in workspace.json()["slot_states"] if item["slot_key"] == "agent")
    assert slot["state"] == "filled"
    assert slot["revision"] == 1
