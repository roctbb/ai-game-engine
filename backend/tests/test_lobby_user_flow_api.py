from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _student_headers(client, nickname: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": nickname, "role": "student"},
    )
    assert response.status_code == 200
    return {"X-Session-Id": response.json()["session_id"]}


def _admin_headers(client, nickname: str = "admin-lobby") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": nickname, "role": "admin"},
    )
    assert response.status_code == 200
    return {"X-Session-Id": response.json()["session_id"]}


def _create_game(client, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/games",
        json={
            "slug": "lobby_user_flow_game",
            "title": "Lobby User Flow",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def _create_lobby(client, game_id: str, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game_id,
            "title": "Lobby User Flow",
            "kind": "training",
            "access": "public",
            "max_teams": 16,
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["lobby_id"]


def test_lobby_create_rejects_competition_kind(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)

    response = client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game["game_id"],
            "title": "Old Competition Kind",
            "kind": "competition",
            "access": "public",
            "max_teams": 16,
        },
        headers=teacher_headers,
    )

    assert response.status_code == 422


def test_lobby_create_rejects_task_or_unpublished_game(client, teacher_headers) -> None:
    task = client.post(
        "/api/v1/games",
        json={
            "slug": "lobby_reject_task",
            "title": "Task Not Lobby",
            "mode": "single_task",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
            "description": "Task",
            "difficulty": "easy",
            "learning_section": "Условия и выбор",
            "topics": ["basics"],
            "catalog_metadata_status": "ready",
        },
        headers=teacher_headers,
    )
    assert task.status_code == 200

    draft_game = client.post(
        "/api/v1/games",
        json={
            "slug": "lobby_reject_draft_game",
            "title": "Draft Lobby Game",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
            "catalog_metadata_status": "draft",
        },
        headers=teacher_headers,
    )
    assert draft_game.status_code == 200

    for game_id in (task.json()["game_id"], draft_game.json()["game_id"]):
        response = client.post(
            "/api/v1/lobbies",
            json={
                "game_id": game_id,
                "title": "Invalid Lobby",
                "kind": "training",
                "access": "public",
                "max_teams": 16,
            },
            headers=teacher_headers,
        )
        assert response.status_code == 422


def test_lobby_competition_start_rejects_future_tie_break_policy(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)

    response = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/start",
        json={"title": "Future Tie Break", "tie_break_policy": "game_defined"},
        headers=teacher_headers,
    )

    assert response.status_code == 422


def test_code_lobby_details_require_access_code_or_participation(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    created = client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game["game_id"],
            "title": "Code Lobby",
            "kind": "training",
            "access": "code",
            "access_code": "secret-42",
            "max_teams": 4,
        },
        headers=teacher_headers,
    )
    assert created.status_code == 200
    lobby_id = created.json()["lobby_id"]
    headers = _student_headers(client, "code-lobby-student")

    listed = client.get("/api/v1/lobbies", headers=headers)
    assert listed.status_code == 200
    listed_lobby = next(item for item in listed.json() if item["lobby_id"] == lobby_id)
    assert listed_lobby["teams"] == []
    assert listed_lobby["participant_stats"] == []

    detail_denied = client.get(f"/api/v1/lobbies/{lobby_id}", headers=headers)
    assert detail_denied.status_code == 403
    assert detail_denied.json()["error"]["code"] == "forbidden"

    wrong_join = client.post(
        f"/api/v1/lobbies/{lobby_id}/join",
        json={"access_code": "wrong"},
        headers=headers,
    )
    assert wrong_join.status_code == 422

    joined = client.post(
        f"/api/v1/lobbies/{lobby_id}/join",
        json={"access_code": "secret-42"},
        headers=headers,
    )
    assert joined.status_code == 200
    assert joined.json()["my_team_id"] is not None

    detail_allowed = client.get(f"/api/v1/lobbies/{lobby_id}", headers=headers)
    assert detail_allowed.status_code == 200
    assert detail_allowed.json()["teams"]


def test_admin_can_add_unique_demo_bots_with_one_lobby_call(client) -> None:
    admin_headers = _admin_headers(client)
    games_response = client.get("/api/v1/games", headers=admin_headers)
    assert games_response.status_code == 200
    game = next(item for item in games_response.json() if item["slug"] == "ttt_connect5_v1")
    lobby_response = client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game["game_id"],
            "title": "Bots Lobby",
            "kind": "training",
            "access": "code",
            "access_code": "secret",
            "max_teams": 4,
        },
        headers=admin_headers,
    )
    assert lobby_response.status_code == 200
    lobby_id = lobby_response.json()["lobby_id"]

    first = client.post(f"/api/v1/lobbies/{lobby_id}/admin-bots", headers=admin_headers)
    second = client.post(f"/api/v1/lobbies/{lobby_id}/admin-bots", headers=admin_headers)

    assert first.status_code == 200, first.json()
    assert len(first.json()["participant_stats"]) == 1
    assert second.status_code == 200, second.json()
    payload = second.json()
    assert len(payload["teams"]) == 2
    assert all(item["ready"] for item in payload["teams"])
    assert len(payload["participant_stats"]) == 2
    teams_response = client.get(f"/api/v1/teams?game_id={game['game_id']}", headers=admin_headers)
    assert teams_response.status_code == 200
    bot_team_ids = {item["team_id"] for item in payload["teams"]}
    names = [item["name"] for item in teams_response.json() if item["team_id"] in bot_team_ids]
    assert len(names) == len(set(names))
    assert {"Бот Евгений", "Бот Анна"} <= set(names)

    bot_team_id = payload["teams"][0]["team_id"]
    workspace = client.get(f"/api/v1/teams/{bot_team_id}/workspace", headers=admin_headers)
    assert workspace.status_code == 200
    assert workspace.json()["slot_states"][0]["code"]

    updated = client.put(
        f"/api/v1/teams/{bot_team_id}/slots/bot",
        json={"actor_user_id": "admin-lobby", "code": "def make_choice(field, role):\n    return 0, 0\n"},
        headers=admin_headers,
    )
    assert updated.status_code == 200


def test_student_join_play_stop_without_team_id(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    alice_headers = _student_headers(client, "alice-flow")
    bob_headers = _student_headers(client, "bob-flow")

    joined = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=alice_headers)
    assert joined.status_code == 200
    joined_payload = joined.json()
    assert joined_payload["my_team_id"] is not None
    alice_team_id = joined_payload["my_team_id"]

    slot_update = client.put(
        f"/api/v1/teams/{alice_team_id}/slots/bot",
        json={"actor_user_id": "alice-flow", "code": "def make_choice(field, role):\n    return 0, 0\n"},
        headers=alice_headers,
    )
    assert slot_update.status_code == 200

    alice_play = client.post(f"/api/v1/lobbies/{lobby_id}/play", json={}, headers=alice_headers)
    assert alice_play.status_code == 200
    assert alice_play.json()["my_status"] == "queued"

    bob_join = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=bob_headers)
    assert bob_join.status_code == 200
    bob_team_id = bob_join.json()["my_team_id"]
    bob_slot = client.put(
        f"/api/v1/teams/{bob_team_id}/slots/bot",
        json={"actor_user_id": "bob-flow", "code": "def make_choice(field, role):\n    return 0, 0\n"},
        headers=bob_headers,
    )
    assert bob_slot.status_code == 200
    bob_play = client.post(f"/api/v1/lobbies/{lobby_id}/play", json={}, headers=bob_headers)
    assert bob_play.status_code == 200

    charlie_headers = _student_headers(client, "charlie-flow")
    charlie_join = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=charlie_headers)
    assert charlie_join.status_code == 200
    assert charlie_join.json()["status"] == "running"
    charlie_team_id = charlie_join.json()["my_team_id"]
    charlie_slot = client.put(
        f"/api/v1/teams/{charlie_team_id}/slots/bot",
        json={"actor_user_id": "charlie-flow", "code": "def make_choice(field, role):\n    return 0, 0\n"},
        headers=charlie_headers,
    )
    assert charlie_slot.status_code == 200
    charlie_play = client.post(f"/api/v1/lobbies/{lobby_id}/play", json={}, headers=charlie_headers)
    assert charlie_play.status_code == 200
    assert charlie_play.json()["my_status"] == "queued"
    charlie_stop = client.post(f"/api/v1/lobbies/{lobby_id}/stop", headers=charlie_headers)
    assert charlie_stop.status_code == 200
    assert charlie_stop.json()["my_status"] == "preparing"

    competition_start = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/start",
        json={"title": "Blocked Cup"},
        headers=teacher_headers,
    )
    assert competition_start.status_code == 422

    current_run = client.get(f"/api/v1/lobbies/{lobby_id}/current-run", headers=alice_headers)
    assert current_run.status_code == 200
    assert current_run.json()["status"] in {"preparing", "queued", "playing"}

    stopped = client.post(f"/api/v1/lobbies/{lobby_id}/stop", headers=alice_headers)
    assert stopped.status_code == 200
    assert stopped.json()["my_status"] == "preparing"


def test_lobby_stats_read_root_scores_and_placements(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    player_headers = [_student_headers(client, "stats-a"), _student_headers(client, "stats-b")]
    team_ids: list[str] = []

    for index, headers in enumerate(player_headers):
        joined = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=headers)
        assert joined.status_code == 200
        team_id = joined.json()["my_team_id"]
        team_ids.append(team_id)
        update = client.put(
            f"/api/v1/teams/{team_id}/slots/bot",
            json={
                "actor_user_id": f"stats-{'a' if index == 0 else 'b'}",
                "code": "def make_choice(field, role):\n    return 0, 0\n",
            },
            headers=headers,
        )
        assert update.status_code == 200
        play = client.post(f"/api/v1/lobbies/{lobby_id}/play", json={}, headers=headers)
        assert play.status_code == 200

    lobby = client.get(f"/api/v1/lobbies/{lobby_id}", headers=player_headers[0]).json()
    assert lobby["current_run_ids"]
    for run_id in lobby["current_run_ids"]:
        run = client.get(f"/api/v1/runs/{run_id}", headers=teacher_headers)
        assert run.status_code == 200
        team_id = run.json()["team_id"]
        finished = client.post(
            f"/api/v1/internal/runs/{run_id}/finished",
            json={
                "payload": {
                    "status": "ok",
                    "scores": {team_id: 25 if team_id == team_ids[0] else 10},
                    "placements": {team_id: 1 if team_id == team_ids[0] else 2},
                }
            },
        )
        assert finished.status_code == 200

    refreshed = client.get(f"/api/v1/lobbies/{lobby_id}", headers=player_headers[0])
    assert refreshed.status_code == 200
    refreshed_payload = refreshed.json()
    assert refreshed_payload["status"] == "running"
    assert refreshed_payload["cycle_phase"] in {"replay", "result"}
    assert set(refreshed_payload["current_run_ids"]) == set(lobby["current_run_ids"])
    stats_by_team = {item["team_id"]: item for item in refreshed_payload["participant_stats"]}
    assert stats_by_team[team_ids[0]]["wins"] == 1
    assert stats_by_team[team_ids[0]]["average_score"] == 25
    assert stats_by_team[team_ids[1]]["wins"] == 0
    assert stats_by_team[team_ids[1]]["average_score"] == 10


def test_training_matchmaking_waits_for_replay_display_before_next_match(client, teacher_headers, container) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    player_headers = [_student_headers(client, "replay-sync-a"), _student_headers(client, "replay-sync-b")]
    team_ids: list[str] = []

    for index, headers in enumerate(player_headers):
        joined = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=headers)
        assert joined.status_code == 200
        team_id = joined.json()["my_team_id"]
        team_ids.append(team_id)
        update = client.put(
            f"/api/v1/teams/{team_id}/slots/bot",
            json={
                "actor_user_id": f"replay-sync-{'a' if index == 0 else 'b'}",
                "code": "def make_choice(field, role):\n    return 0, 0\n",
            },
            headers=headers,
        )
        assert update.status_code == 200
        play = client.post(f"/api/v1/lobbies/{lobby_id}/play", json={}, headers=headers)
        assert play.status_code == 200

    first_lobby = client.get(f"/api/v1/lobbies/{lobby_id}", headers=player_headers[0]).json()
    first_run_ids = set(first_lobby["current_run_ids"])
    assert len(first_run_ids) == 2

    for run_id in first_run_ids:
        run = client.get(f"/api/v1/runs/{run_id}", headers=teacher_headers)
        assert run.status_code == 200
        team_id = run.json()["team_id"]
        finished = client.post(
            f"/api/v1/internal/runs/{run_id}/finished",
            json={
                "payload": {
                    "status": "ok",
                    "frames": [{"tick": index} for index in range(5)],
                    "placements": {team_id: 1 if team_id == team_ids[0] else 2},
                    "scores": {team_id: 100 if team_id == team_ids[0] else 50},
                }
            },
        )
        assert finished.status_code == 200

    during_replay = client.get(f"/api/v1/lobbies/{lobby_id}", headers=player_headers[0])
    assert during_replay.status_code == 200
    assert set(during_replay.json()["current_run_ids"]) == first_run_ids
    assert during_replay.json()["cycle_phase"] == "replay"
    assert set(during_replay.json()["playing_team_ids"]) == set(team_ids)

    old_finished_at = datetime.now(tz=UTC) - timedelta(seconds=30)
    for run_id in first_run_ids:
        run = container.execution._run_repository.get(run_id)
        run.finished_at = old_finished_at
        container.execution._run_repository.save(run)

    after_replay = client.get(f"/api/v1/lobbies/{lobby_id}", headers=player_headers[0])
    assert after_replay.status_code == 200
    next_run_ids = set(after_replay.json()["current_run_ids"])
    assert len(next_run_ids) == 2
    assert next_run_ids.isdisjoint(first_run_ids)


def test_student_stop_blocked_while_lobby_competition_is_active(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    players = [
        ("stop-comp-a", _student_headers(client, "stop-comp-a")),
        ("stop-comp-b", _student_headers(client, "stop-comp-b")),
    ]
    team_ids: list[str] = []

    for nickname, headers in players:
        joined = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=headers)
        assert joined.status_code == 200
        team_id = joined.json()["my_team_id"]
        team_ids.append(team_id)
        update = client.put(
            f"/api/v1/teams/{team_id}/slots/bot",
            json={"actor_user_id": nickname, "code": "def make_choice(field, role):\n    return 0, 0\n"},
            headers=headers,
        )
        assert update.status_code == 200

    started = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/start",
        json={"title": "Locked Cup"},
        headers=teacher_headers,
    )
    assert started.status_code == 200

    locked_update = client.put(
        f"/api/v1/teams/{team_ids[0]}/slots/bot",
        json={"actor_user_id": "stop-comp-a", "code": "def make_choice(field, role):\n    return 1, 1\n"},
        headers=players[0][1],
    )
    assert locked_update.status_code == 422

    stopped = client.post(f"/api/v1/lobbies/{lobby_id}/stop", headers=players[0][1])
    assert stopped.status_code == 422

    left = client.post(
        f"/api/v1/lobbies/{lobby_id}/teams/{team_ids[0]}/leave",
        headers=players[0][1],
    )
    assert left.status_code == 422


def test_student_can_leave_manually_paused_lobby_without_active_competition(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    student_headers = _student_headers(client, "paused-leaver")

    joined = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=student_headers)
    assert joined.status_code == 200
    team_id = joined.json()["my_team_id"]

    paused = client.post(f"/api/v1/lobbies/{lobby_id}/status", json={"status": "paused"}, headers=teacher_headers)
    assert paused.status_code == 200

    left = client.post(
        f"/api/v1/lobbies/{lobby_id}/teams/{team_id}/leave",
        headers=student_headers,
    )
    assert left.status_code == 200
    assert all(item["team_id"] != team_id for item in left.json()["teams"])


def test_failed_lobby_join_does_not_create_personal_team(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    paused = client.post(f"/api/v1/lobbies/{lobby_id}/status", json={"status": "paused"}, headers=teacher_headers)
    assert paused.status_code == 200

    student_headers = _student_headers(client, "blocked-join")
    denied = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=student_headers)
    assert denied.status_code == 422

    teams = client.get(f"/api/v1/teams?game_id={game['game_id']}", headers=teacher_headers)
    assert teams.status_code == 200
    assert all(item["captain_user_id"] != "blocked-join" for item in teams.json())


def test_start_finish_lobby_competition_and_archive(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)

    for captain in ("comp-a", "comp-b"):
        team = client.post(
            "/api/v1/teams",
            json={"game_id": game["game_id"], "name": captain, "captain_user_id": captain},
            headers=teacher_headers,
        )
        assert team.status_code == 200
        team_id = team.json()["team_id"]
        update = client.put(
            f"/api/v1/teams/{team_id}/slots/bot",
            json={"actor_user_id": captain, "code": "def make_choice(field, role):\n    return 0, 0\n"},
            headers=teacher_headers,
        )
        assert update.status_code == 200
        joined = client.post(
            f"/api/v1/lobbies/{lobby_id}/teams/{team_id}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    started = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/start",
        json={"title": "Class Cup", "code_policy": "allowed_between_matches"},
        headers=teacher_headers,
    )
    assert started.status_code == 200
    competition_id = started.json()["competition_id"]
    assert started.json()["status"] in {"running", "paused"}

    duplicate_start = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/start",
        json={"title": "Second Cup"},
        headers=teacher_headers,
    )
    assert duplicate_start.status_code == 422

    early_finish = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/{competition_id}/finish",
        headers=teacher_headers,
    )
    assert early_finish.status_code == 422

    competition = client.get(f"/api/v1/competitions/{competition_id}", headers=teacher_headers).json()
    assert competition["lobby_id"] == lobby_id
    assert competition["code_policy"] == "allowed_between_matches"
    assert not competition["title"].startswith(f"[lobby:{lobby_id}] ")
    match = competition["rounds"][0]["matches"][0]
    for index, (team_id, run_id) in enumerate(match["run_ids_by_team"].items()):
        client.post(
            f"/api/v1/internal/runs/{run_id}/finished",
            json={
                "payload": {
                    "status": "ok",
                    "metrics": {},
                    "placements": {team_id: 1},
                    "scores": {team_id: 100 - index},
                }
            },
        )

    completed = client.get(
        f"/api/v1/competitions/{competition_id}",
        headers=teacher_headers,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    finished = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/{competition_id}/finish",
        headers=teacher_headers,
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "finished"

    archive = client.get(f"/api/v1/lobbies/{lobby_id}/competitions/archive", headers=teacher_headers)
    assert archive.status_code == 200
    archived_item = next(item for item in archive.json()["items"] if item["competition_id"] == competition_id)
    assert archived_item["winner_team_ids"]


def test_direct_finished_lobby_competition_reopens_lobby(client, teacher_headers, container) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    team_ids: list[str] = []

    for captain in ("direct-finish-a", "direct-finish-b"):
        team = client.post(
            "/api/v1/teams",
            json={"game_id": game["game_id"], "name": captain, "captain_user_id": captain},
            headers=teacher_headers,
        )
        assert team.status_code == 200
        team_id = team.json()["team_id"]
        team_ids.append(team_id)
        update = client.put(
            f"/api/v1/teams/{team_id}/slots/bot",
            json={"actor_user_id": captain, "code": "def make_choice(field, role):\n    return 0, 0\n"},
            headers=teacher_headers,
        )
        assert update.status_code == 200
        joined = client.post(
            f"/api/v1/lobbies/{lobby_id}/teams/{team_id}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    started = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/start",
        json={"title": "Direct Finish Cup"},
        headers=teacher_headers,
    )
    assert started.status_code == 200
    competition_id = started.json()["competition_id"]

    competition = client.get(f"/api/v1/competitions/{competition_id}", headers=teacher_headers).json()
    match = competition["rounds"][0]["matches"][0]
    for index, (team_id, run_id) in enumerate(match["run_ids_by_team"].items()):
        client.post(
            f"/api/v1/internal/runs/{run_id}/finished",
            json={
                "payload": {
                    "status": "ok",
                    "metrics": {},
                    "placements": {team_id: 1},
                    "scores": {team_id: 100 - index},
                }
            },
        )

    completed = client.get(f"/api/v1/competitions/{competition_id}", headers=teacher_headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    direct_finished = client.post(
        f"/api/v1/competitions/{competition_id}/finish",
        headers=teacher_headers,
    )
    assert direct_finished.status_code == 200
    assert direct_finished.json()["status"] == "finished"

    lobby_model = container.training_lobby.get_lobby(lobby_id)
    for team_id in team_ids:
        lobby_model.mark_ready(team_id=team_id, ready=True)
    container.training_lobby._repository.save(lobby_model)

    lobby = client.get(f"/api/v1/lobbies/{lobby_id}", headers=teacher_headers)
    assert lobby.status_code == 200
    assert lobby.json()["status"] == "running"
    assert len(lobby.json()["current_run_ids"]) == 2


def test_lobby_competition_start_preflight_does_not_create_orphan_competition(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)

    team = client.post(
        "/api/v1/teams",
        json={"game_id": game["game_id"], "name": "solo", "captain_user_id": "solo"},
        headers=teacher_headers,
    )
    assert team.status_code == 200
    team_id = team.json()["team_id"]
    update = client.put(
        f"/api/v1/teams/{team_id}/slots/bot",
        json={"actor_user_id": "solo", "code": "def make_choice(field, role):\n    return 0, 0\n"},
        headers=teacher_headers,
    )
    assert update.status_code == 200
    joined = client.post(
        f"/api/v1/lobbies/{lobby_id}/teams/{team_id}/join",
        json={},
        headers=teacher_headers,
    )
    assert joined.status_code == 200

    failed_start = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/start",
        json={"title": "Too Small Cup"},
        headers=teacher_headers,
    )
    assert failed_start.status_code == 422

    competitions = client.get("/api/v1/competitions", headers=teacher_headers)
    assert competitions.status_code == 200
    assert all(item["lobby_id"] != lobby_id for item in competitions.json())


def test_lobby_competition_can_start_after_training_replay_when_paused(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)
    player_headers = [_student_headers(client, "cup-after-replay-a"), _student_headers(client, "cup-after-replay-b")]

    for index, headers in enumerate(player_headers):
        joined = client.post(f"/api/v1/lobbies/{lobby_id}/join", json={}, headers=headers)
        assert joined.status_code == 200
        team_id = joined.json()["my_team_id"]
        update = client.put(
            f"/api/v1/teams/{team_id}/slots/bot",
            json={
                "actor_user_id": f"cup-after-replay-{index}",
                "code": "def make_choice(field, role):\n    return 0, 0\n",
            },
            headers=headers,
        )
        assert update.status_code == 200
        play = client.post(f"/api/v1/lobbies/{lobby_id}/play", json={}, headers=headers)
        assert play.status_code == 200

    lobby = client.get(f"/api/v1/lobbies/{lobby_id}", headers=teacher_headers).json()
    assert lobby["current_run_ids"]
    for run_id in lobby["current_run_ids"]:
        run = client.get(f"/api/v1/runs/{run_id}", headers=teacher_headers).json()
        team_id = run["team_id"]
        finished = client.post(
            f"/api/v1/internal/runs/{run_id}/finished",
            json={
                "payload": {
                    "status": "ok",
                    "scores": {team_id: 10},
                    "placements": {team_id: 1},
                }
            },
        )
        assert finished.status_code == 200

    paused = client.post(
        f"/api/v1/lobbies/{lobby_id}/status",
        json={"status": "paused"},
        headers=teacher_headers,
    )
    assert paused.status_code == 200
    assert paused.json()["cycle_phase"] in {"replay", "result"}
    assert paused.json()["current_run_ids"]

    started = client.post(
        f"/api/v1/lobbies/{lobby_id}/competitions/start",
        json={"title": "Cup After Replay"},
        headers=teacher_headers,
    )
    assert started.status_code == 200
    assert started.json()["status"] == "running"


def test_legacy_lobby_title_prefix_does_not_attach_competition(client, teacher_headers) -> None:
    game = _create_game(client, teacher_headers)
    lobby_id = _create_lobby(client, game_id=game["game_id"], headers=teacher_headers)

    created = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": f"[lobby:{lobby_id}] Legacy Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "code_policy": "locked_on_start",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    )
    assert created.status_code == 200
    assert created.json()["lobby_id"] is None

    archive = client.get(f"/api/v1/lobbies/{lobby_id}/competitions/archive", headers=teacher_headers)
    assert archive.status_code == 200
    assert all(item["competition_id"] != created.json()["competition_id"] for item in archive.json()["items"])
