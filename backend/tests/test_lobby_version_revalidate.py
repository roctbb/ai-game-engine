def _create_small_match_game(client, slug: str, headers: dict[str, str]) -> dict:
    return client.post(
        '/api/v1/games',
        json={
            'slug': slug,
            'title': 'Slot Revalidation',
            'mode': 'small_match',
            'semver': '1.0.0',
            'required_slots': [{'key': 'bot', 'title': 'Bot', 'required': True}],
        },
        headers=headers,
    ).json()


def _prepare_team_and_ready_lobby(client, game: dict, headers: dict[str, str]) -> tuple[dict, dict]:
    team = client.post(
        '/api/v1/teams',
        json={'game_id': game['game_id'], 'name': 'Alpha', 'captain_user_id': 'captain'},
    ).json()

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/bot",
        json={'actor_user_id': 'captain', 'code': "print('ok')"},
    )

    lobby = client.post(
        '/api/v1/lobbies',
        json={
            'game_id': game['game_id'],
            'title': 'Lobby A',
            'kind': 'training',
            'access': 'public',
            'max_teams': 8,
        },
        headers=headers,
    ).json()

    client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
        json={},
        headers=headers,
    )
    ready = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
        json={'ready': True},
        headers=headers,
    ).json()
    assert ready['teams'][0]['ready'] is True

    return team, lobby


def test_incompatible_version_switch_is_blocked(client, teacher_headers):
    game = _create_small_match_game(client, 'slot_revalidation_game_blocked', headers=teacher_headers)
    _team, lobby = _prepare_team_and_ready_lobby(client, game, headers=teacher_headers)

    updated = client.post(
        f"/api/v1/games/{game['game_id']}/versions",
        json={
            'semver': '1.1.0',
            'required_slots': [
                {'key': 'bot', 'title': 'Bot', 'required': True},
                {'key': 'strategy', 'title': 'Strategy', 'required': True},
            ],
        },
        headers=teacher_headers,
    ).json()
    new_version = next(v for v in updated['versions'] if v['semver'] == '1.1.0')

    response = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/switch-version",
        json={'version_id': new_version['version_id']},
        headers=teacher_headers,
    )

    assert response.status_code == 409
    assert response.json()['error']['code'] == 'conflict'


def test_compatible_optional_slot_addition_preserves_ready(client, teacher_headers):
    game = _create_small_match_game(client, 'slot_revalidation_game_compatible', headers=teacher_headers)
    team, lobby = _prepare_team_and_ready_lobby(client, game, headers=teacher_headers)

    updated = client.post(
        f"/api/v1/games/{game['game_id']}/versions",
        json={
            'semver': '1.1.0',
            'required_slots': [
                {'key': 'bot', 'title': 'Bot', 'required': True},
                {'key': 'strategy', 'title': 'Strategy', 'required': False},
            ],
        },
        headers=teacher_headers,
    ).json()
    new_version = next(v for v in updated['versions'] if v['semver'] == '1.1.0')

    switched = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/switch-version",
        json={'version_id': new_version['version_id']},
        headers=teacher_headers,
    ).json()

    team_state = next(item for item in switched['teams'] if item['team_id'] == team['team_id'])
    assert team_state['ready'] is True
    assert team_state['blocker_reason'] is None


def test_switch_version_cancels_active_training_runs(client, teacher_headers):
    game = _create_small_match_game(client, 'slot_revalidation_game_cancel_runs', headers=teacher_headers)
    team, lobby = _prepare_team_and_ready_lobby(client, game, headers=teacher_headers)

    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "captain",
            "run_kind": "training_match",
            "lobby_id": lobby["lobby_id"],
        },
    ).json()
    queued = client.post(f"/api/v1/runs/{run['run_id']}/queue").json()
    assert queued["status"] == "queued"

    updated = client.post(
        f"/api/v1/games/{game['game_id']}/versions",
        json={
            'semver': '1.1.0',
            'required_slots': [
                {'key': 'bot', 'title': 'Bot', 'required': True},
                {'key': 'strategy', 'title': 'Strategy', 'required': False},
            ],
        },
        headers=teacher_headers,
    ).json()
    new_version = next(v for v in updated['versions'] if v['semver'] == '1.1.0')

    switched = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/switch-version",
        json={'version_id': new_version['version_id']},
        headers=teacher_headers,
    )
    assert switched.status_code == 200, switched.json()

    canceled = client.get(f"/api/v1/runs/{run['run_id']}").json()
    assert canceled["status"] == "canceled"
    assert canceled["error_message"] == "canceled_by_game_update"
