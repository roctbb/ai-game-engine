def _create_small_match_game(client, slug: str, headers: dict[str, str]) -> dict:
    return client.post(
        "/api/v1/games",
        json={
            "slug": slug,
            "title": "Competition Game",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
        },
        headers=headers,
    ).json()


def _create_ready_team(client, game_id: str, name: str, captain: str) -> dict:
    team = client.post(
        "/api/v1/teams",
        json={"game_id": game_id, "name": name, "captain_user_id": captain},
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/bot",
        json={"actor_user_id": captain, "code": "def make_choice(field, role):\n    return 0, 0\n"},
    )
    return team


def test_competition_start_schedules_competition_runs(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_game_start", headers=teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], name="Alpha", captain="captain-a")
    team_b = _create_ready_team(client, game_id=game["game_id"], name="Bravo", captain="captain-b")

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Spring Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()

    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_a["team_id"]},
        headers=teacher_headers,
    )
    registered = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_b["team_id"]},
        headers=teacher_headers,
    ).json()
    assert all(item["ready"] for item in registered["entrants"])

    started = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": "teacher-1"},
        headers=teacher_headers,
    ).json()
    assert started["status"] == "running"
    assert len(started["last_scheduled_run_ids"]) == 2

    runs = client.get(
        f"/api/v1/runs?lobby_id={competition['competition_id']}&run_kind=competition_match"
    ).json()
    assert len(runs) == 2
    assert {item["team_id"] for item in runs} == {team_a["team_id"], team_b["team_id"]}
    assert all(item["status"] == "queued" for item in runs)


def test_competition_ban_disables_ready(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_game_ban", headers=teacher_headers)
    team = _create_ready_team(client, game_id=game["game_id"], name="Alpha", captain="captain-ban")

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Ban Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team["team_id"]},
        headers=teacher_headers,
    )

    moderated = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/moderation/ban",
        json={"team_id": team["team_id"], "banned": True, "reason": "manual moderation"},
        headers=teacher_headers,
    ).json()

    entrant = next(item for item in moderated["entrants"] if item["team_id"] == team["team_id"])
    assert entrant["banned"] is True
    assert entrant["ready"] is False
    assert entrant["blocker_reason"] == "manual moderation"


def test_competition_ban_cancels_active_runs_for_team(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_ban_cancel_runs", headers=teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], name="Alpha", captain="captain-cancel-a")
    team_b = _create_ready_team(client, game_id=game["game_id"], name="Bravo", captain="captain-cancel-b")

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Ban Cancel Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_a["team_id"]},
        headers=teacher_headers,
    )
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_b["team_id"]},
        headers=teacher_headers,
    )

    started = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": "teacher-ban-cancel"},
        headers=teacher_headers,
    ).json()
    match = started["rounds"][0]["matches"][0]
    run_id_for_a = match["run_ids_by_team"][team_a["team_id"]]
    run_id_for_b = match["run_ids_by_team"][team_b["team_id"]]

    moderated = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/moderation/ban",
        json={"team_id": team_a["team_id"], "banned": True, "reason": "manual moderation"},
        headers=teacher_headers,
    )
    assert moderated.status_code == 200

    run_a = client.get(f"/api/v1/runs/{run_id_for_a}")
    run_b = client.get(f"/api/v1/runs/{run_id_for_b}")
    assert run_a.status_code == 200
    assert run_b.status_code == 200
    assert run_a.json()["status"] == "canceled"
    assert run_a.json()["error_message"] == "manual_moderation_ban"
    assert run_b.json()["status"] == "queued"

    runs_view = client.get(f"/api/v1/competitions/{competition['competition_id']}/runs")
    assert runs_view.status_code == 200
    items = runs_view.json()
    canceled_item = next(item for item in items if item["run_id"] == run_id_for_a)
    queued_item = next(item for item in items if item["run_id"] == run_id_for_b)
    assert canceled_item["status"] == "canceled"
    assert canceled_item["error_message"] == "manual_moderation_ban"
    assert queued_item["status"] == "queued"
    assert queued_item["error_message"] is None


def test_competition_advance_finishes_and_sets_winner(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_game_advance", headers=teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], name="Alpha", captain="captain-a-2")
    team_b = _create_ready_team(client, game_id=game["game_id"], name="Bravo", captain="captain-b-2")

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Advance Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_a["team_id"]},
        headers=teacher_headers,
    )
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_b["team_id"]},
        headers=teacher_headers,
    )

    started = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": "teacher-2"},
        headers=teacher_headers,
    ).json()
    round_one = started["rounds"][0]
    match = round_one["matches"][0]
    run_ids_by_team = match["run_ids_by_team"]

    for team_id, run_id in run_ids_by_team.items():
        score = 100 if team_id == team_b["team_id"] else 50
        client.post(
            f"/api/v1/internal/runs/{run_id}/finished",
            json={
                "payload": {
                    "status": "ok",
                    "metrics": {},
                    "placements": {team_id: 1},
                    "scores": {team_id: score},
                }
            },
        )

    advanced = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/advance",
        json={"requested_by": "teacher-2"},
        headers=teacher_headers,
    ).json()

    assert advanced["status"] == "finished"
    assert advanced["winner_team_ids"] == [team_b["team_id"]]
    assert advanced["current_round_index"] is None
    assert advanced["rounds"][0]["status"] == "finished"


def test_competition_advance_manual_tie_requires_resolution(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_game_tie", headers=teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], name="Alpha", captain="captain-a-3")
    team_b = _create_ready_team(client, game_id=game["game_id"], name="Bravo", captain="captain-b-3")

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Tie Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_a["team_id"]},
        headers=teacher_headers,
    )
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_b["team_id"]},
        headers=teacher_headers,
    )

    started = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": "teacher-tie"},
        headers=teacher_headers,
    ).json()
    match = started["rounds"][0]["matches"][0]
    run_ids_by_team = match["run_ids_by_team"]

    for team_id, run_id in run_ids_by_team.items():
        client.post(
            f"/api/v1/internal/runs/{run_id}/finished",
            json={
                "payload": {
                    "status": "ok",
                    "metrics": {},
                    "placements": {team_id: 1},
                    "scores": {team_id: 10},
                }
            },
        )

    paused = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/advance",
        json={"requested_by": "teacher-tie"},
        headers=teacher_headers,
    ).json()
    assert paused["status"] == "paused"
    assert paused["pending_reason"] is not None
    assert paused["rounds"][0]["matches"][0]["status"] == "awaiting_tiebreak"

    resolved = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/matches/resolve",
        json={
            "round_index": 1,
            "match_id": match["match_id"],
            "advanced_team_ids": [team_a["team_id"]],
        },
        headers=teacher_headers,
    ).json()
    assert resolved["rounds"][0]["matches"][0]["status"] == "finished"

    resumed = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": "teacher-tie"},
        headers=teacher_headers,
    ).json()
    assert resumed["status"] == "running"

    finished = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/advance",
        json={"requested_by": "teacher-tie"},
        headers=teacher_headers,
    ).json()
    assert finished["status"] == "finished"
    assert finished["winner_team_ids"] == [team_a["team_id"]]


def test_competition_mutations_require_teacher_or_admin(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_role_guard", headers=teacher_headers)
    team = _create_ready_team(client, game_id=game["game_id"], name="Alpha", captain="captain-role")

    student_session = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": "student-comp", "role": "student"},
    )
    assert student_session.status_code == 200
    student_headers = {"X-Session-Id": student_session.json()["session_id"]}

    denied_create = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Denied Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=student_headers,
    )
    assert denied_create.status_code == 403

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Allowed Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()

    denied_register = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team["team_id"]},
        headers=student_headers,
    )
    assert denied_register.status_code == 403

    denied_patch = client.patch(
        f"/api/v1/competitions/{competition['competition_id']}",
        json={"title": "Denied update"},
        headers=student_headers,
    )
    assert denied_patch.status_code == 403


def test_competition_patch_updates_draft_competition(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_patch_ok", headers=teacher_headers)
    created = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Patchable Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    )
    assert created.status_code == 200
    competition = created.json()

    patched = client.patch(
        f"/api/v1/competitions/{competition['competition_id']}",
        json={
            "title": "Patchable Cup v2",
            "tie_break_policy": "shared_advancement",
            "advancement_top_k": 2,
            "match_size": 4,
        },
        headers=teacher_headers,
    )
    assert patched.status_code == 200
    payload = patched.json()
    assert payload["title"] == "Patchable Cup v2"
    assert payload["tie_break_policy"] == "shared_advancement"
    assert payload["advancement_top_k"] == 2
    assert payload["match_size"] == 4


def test_competition_patch_denied_for_non_draft(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_patch_status_guard", headers=teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], name="Alpha", captain="captain-pa")
    team_b = _create_ready_team(client, game_id=game["game_id"], name="Bravo", captain="captain-pb")

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Status Guard Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_a["team_id"]},
        headers=teacher_headers,
    )
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_b["team_id"]},
        headers=teacher_headers,
    )
    started = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": "teacher-status-guard"},
        headers=teacher_headers,
    )
    assert started.status_code == 200

    denied = client.patch(
        f"/api/v1/competitions/{competition['competition_id']}",
        json={"title": "Should fail"},
        headers=teacher_headers,
    )
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "invariant_violation"


def test_competition_bracket_rounds_matches_endpoints(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "competition_api_read_views", headers=teacher_headers)
    team_a = _create_ready_team(client, game_id=game["game_id"], name="Alpha", captain="captain-r1")
    team_b = _create_ready_team(client, game_id=game["game_id"], name="Bravo", captain="captain-r2")

    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game["game_id"],
            "title": "Read Views Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=teacher_headers,
    ).json()
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_a["team_id"]},
        headers=teacher_headers,
    )
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/register",
        json={"team_id": team_b["team_id"]},
        headers=teacher_headers,
    )
    client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": "teacher-read-views"},
        headers=teacher_headers,
    )

    bracket = client.get(f"/api/v1/competitions/{competition['competition_id']}/bracket")
    rounds = client.get(f"/api/v1/competitions/{competition['competition_id']}/rounds")
    matches = client.get(f"/api/v1/competitions/{competition['competition_id']}/matches")

    assert bracket.status_code == 200
    assert rounds.status_code == 200
    assert matches.status_code == 200
    assert isinstance(bracket.json(), list)
    assert isinstance(rounds.json(), list)
    assert isinstance(matches.json(), list)
    assert len(bracket.json()) == len(rounds.json())
    assert len(matches.json()) >= 1
