def _create_small_match_game(client, slug: str, headers: dict[str, str]) -> dict:
    return client.post(
        "/api/v1/games",
        json={
            "slug": slug,
            "title": "Antiplagiarism Game",
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
        },
        headers=headers,
    ).json()


def _create_team_with_code(client, game_id: str, name: str, captain: str, code: str) -> dict:
    team = client.post(
        "/api/v1/teams",
        json={"game_id": game_id, "name": name, "captain_user_id": captain},
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/bot",
        json={"actor_user_id": captain, "code": code},
    )
    return team


def _create_started_competition(
    client,
    game_id: str,
    team_ids: list[str],
    headers: dict[str, str],
    requested_by: str = "teacher",
) -> dict:
    competition = client.post(
        "/api/v1/competitions",
        json={
            "game_id": game_id,
            "title": "Antiplagiarism Cup",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        headers=headers,
    ).json()
    for team_id in team_ids:
        client.post(
            f"/api/v1/competitions/{competition['competition_id']}/register",
            json={"team_id": team_id},
            headers=headers,
        )

    started = client.post(
        f"/api/v1/competitions/{competition['competition_id']}/start",
        json={"requested_by": requested_by},
        headers=headers,
    ).json()
    assert started["status"] == "running"
    return started


def test_competition_antiplagiarism_detects_identical_code(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "antiplag_detect_game", headers=teacher_headers)
    code = (
        "def make_choice(field, role):\n"
        "    for x in range(5):\n"
        "        for y in range(5):\n"
        "            if field[x][y] == 0:\n"
        "                return x, y\n"
    )
    team_a = _create_team_with_code(client, game["game_id"], "Alpha", "captain-a", code)
    team_b = _create_team_with_code(client, game["game_id"], "Bravo", "captain-b", code)

    competition = _create_started_competition(
        client,
        game_id=game["game_id"],
        team_ids=[team_a["team_id"], team_b["team_id"]],
        headers=teacher_headers,
    )

    warnings = client.get(
        f"/api/v1/competitions/{competition['competition_id']}/antiplagiarism/warnings",
        headers=teacher_headers,
    ).json()

    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["competition_id"] == competition["competition_id"]
    assert {warning["team_a_id"], warning["team_b_id"]} == {team_a["team_id"], team_b["team_id"]}
    assert warning["slot_key"] == "bot"
    assert warning["similarity"] == 1.0
    assert warning["algorithm"] == "jaccard_shingle_5_v1"
    assert warning["run_a_id"].startswith("run_")
    assert warning["run_b_id"].startswith("run_")


def test_competition_antiplagiarism_returns_empty_for_distinct_code(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "antiplag_distinct_game", headers=teacher_headers)

    aggressive_code = (
        "def make_choice(field, role):\n"
        "    for x in range(5):\n"
        "        for y in range(5):\n"
        "            if field[x][y] == 0:\n"
        "                return x, y\n"
    )
    defensive_code = (
        "def make_choice(field, role):\n"
        "    center = (2, 2)\n"
        "    if field[center[0]][center[1]] == 0:\n"
        "        return center\n"
        "    for row in range(4, -1, -1):\n"
        "        for col in range(4, -1, -1):\n"
        "            if field[row][col] == 0:\n"
        "                return row, col\n"
    )

    team_a = _create_team_with_code(client, game["game_id"], "Alpha", "captain-a2", aggressive_code)
    team_b = _create_team_with_code(client, game["game_id"], "Bravo", "captain-b2", defensive_code)

    competition = _create_started_competition(
        client,
        game_id=game["game_id"],
        team_ids=[team_a["team_id"], team_b["team_id"]],
        headers=teacher_headers,
        requested_by="teacher-2",
    )

    warnings = client.get(
        f"/api/v1/competitions/{competition['competition_id']}/antiplagiarism/warnings?similarity_threshold=0.9",
        headers=teacher_headers,
    ).json()

    assert warnings == []


def test_competition_antiplagiarism_requires_teacher_or_admin(client, teacher_headers) -> None:
    game = _create_small_match_game(client, "antiplag_rbac_game", headers=teacher_headers)
    code = (
        "def make_choice(field, role):\n"
        "    return 0, 0\n"
    )
    team_a = _create_team_with_code(client, game["game_id"], "Alpha", "captain-ra", code)
    team_b = _create_team_with_code(client, game["game_id"], "Bravo", "captain-rb", code)

    competition = _create_started_competition(
        client,
        game_id=game["game_id"],
        team_ids=[team_a["team_id"], team_b["team_id"]],
        headers=teacher_headers,
        requested_by="teacher-rbac",
    )

    student_session = client.post(
        "/api/v1/auth/dev-login",
        json={"nickname": "student-antiplag", "role": "student"},
    )
    assert student_session.status_code == 200
    student_headers = {"X-Session-Id": student_session.json()["session_id"]}

    denied = client.get(
        f"/api/v1/competitions/{competition['competition_id']}/antiplagiarism/warnings",
        headers=student_headers,
    )
    assert denied.status_code == 403
