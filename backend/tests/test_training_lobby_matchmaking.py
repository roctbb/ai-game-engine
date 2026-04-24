def _create_game(client, slug: str, mode: str, headers: dict[str, str]) -> dict:
    return client.post(
        "/api/v1/games",
        json={
            "slug": slug,
            "title": f"{mode} game",
            "mode": mode,
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
        },
        headers=headers,
    ).json()


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


def _create_training_lobby(client, game_id: str, title: str, headers: dict[str, str]) -> dict:
    return client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game_id,
            "title": title,
            "kind": "training",
            "access": "public",
            "max_teams": 32,
        },
        headers=headers,
    ).json()


def test_small_match_matchmaking_schedules_only_full_pairs(client, teacher_headers) -> None:
    game = _create_game(client, slug="small_match_mm_game", mode="small_match", headers=teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="cap-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="cap-b", name="Bravo")
    team_c = _create_ready_team(client, game_id=game["game_id"], captain="cap-c", name="Charlie")

    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Small", headers=teacher_headers)
    ready_responses = []
    for team in (team_a, team_b, team_c):
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        ready_responses.append(
            client.post(
                f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
                json={"ready": True},
                headers=teacher_headers,
            )
        )

    assert ready_responses[1].status_code == 200
    auto_tick = ready_responses[1].json()
    assert auto_tick["status"] == "running"
    assert len(auto_tick["last_scheduled_run_ids"]) == 2

    runs = client.get(f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match").json()
    assert len(runs) == 2
    assert {item["team_id"] for item in runs} == {team_a["team_id"], team_b["team_id"]}
    assert all(item["status"] == "queued" for item in runs)

    tick_again = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/matchmaking/tick",
        json={"requested_by": "teacher-mm"},
        headers=teacher_headers,
    ).json()
    assert tick_again["last_scheduled_run_ids"] == []


def test_massive_lobby_matchmaking_schedules_all_ready_teams(client, teacher_headers) -> None:
    game = _create_game(client, slug="massive_match_mm_game", mode="massive_lobby", headers=teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="mcap-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="mcap-b", name="Bravo")
    team_c = _create_ready_team(client, game_id=game["game_id"], captain="mcap-c", name="Charlie")

    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Massive", headers=teacher_headers)
    ready_responses = []
    for team in (team_a, team_b, team_c):
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        ready_responses.append(
            client.post(
                f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
                json={"ready": True},
                headers=teacher_headers,
            )
        )

    assert ready_responses[1].status_code == 200
    auto_tick = ready_responses[1].json()
    assert auto_tick["status"] == "running"
    assert len(auto_tick["last_scheduled_run_ids"]) == 2

    runs = client.get(f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match").json()
    assert len(runs) == 2
    assert {item["team_id"] for item in runs} == {
        team_a["team_id"],
        team_b["team_id"],
    }
