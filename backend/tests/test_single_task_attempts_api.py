from __future__ import annotations


def _auth_headers(client, nickname: str, role: str = 'student') -> dict[str, str]:
    response = client.post(
        '/api/v1/auth/dev-login',
        json={'nickname': nickname, 'role': role},
    )
    assert response.status_code == 200
    return {'X-Session-Id': response.json()['session_id']}


def _find_game_id(client, slug: str, headers: dict[str, str]) -> str:
    games = client.get('/api/v1/games', headers=headers).json()
    game = next(item for item in games if item['slug'] == slug)
    return game['game_id']


def _required_slot_key(client, game_id: str, headers: dict[str, str]) -> str:
    game = client.get(f'/api/v1/games/{game_id}', headers=headers).json()
    active_version_id = game['active_version_id']
    version = next(item for item in game['versions'] if item['version_id'] == active_version_id)
    return version['required_slot_keys'][0]


def _create_ready_team(client, game_id: str, user_id: str) -> tuple[str, dict[str, str]]:
    headers = _auth_headers(client, user_id)
    team = client.post(
        '/api/v1/teams',
        headers=headers,
        json={
            'game_id': game_id,
            'name': f'Team {user_id}',
            'captain_user_id': user_id,
        },
    ).json()
    slot = _required_slot_key(client, game_id, headers=headers)
    update = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/{slot}",
        headers=headers,
        json={
            'actor_user_id': user_id,
            'code': 'def make_move(state):\n    return "right"\n',
        },
    )
    assert update.status_code == 200
    return team['team_id'], headers


def _finish_run(client, run_id: str, metrics: dict[str, object]) -> None:
    finished = client.post(
        f'/api/v1/internal/runs/{run_id}/finished',
        json={
            'payload': {
                'status': 'finished',
                'metrics': metrics,
            }
        },
    )
    assert finished.status_code == 200


def test_single_task_run_endpoint_creates_and_queues_run(client) -> None:
    headers = _auth_headers(client, 'runner')
    game_id = _find_game_id(client, 'maze_escape_v1', headers=headers)
    team_id, headers = _create_ready_team(client, game_id=game_id, user_id='runner')

    response = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        headers=headers,
        json={
            'team_id': team_id,
            'requested_by': 'runner',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['run_kind'] == 'single_task'
    assert payload['status'] == 'queued'
    assert payload['game_id'] == game_id


def test_single_task_run_with_empty_required_slot_does_not_block_next_attempt(client) -> None:
    user_id = 'empty-slot-runner'
    headers = _auth_headers(client, user_id)
    maze_game_id = _find_game_id(client, 'maze_escape_v1', headers=headers)
    coins_game_id = _find_game_id(client, 'coins_right_down_v1', headers=headers)
    empty_team = client.post(
        '/api/v1/teams',
        headers=headers,
        json={
            'game_id': maze_game_id,
            'name': 'Empty Slot Team',
            'captain_user_id': user_id,
        },
    ).json()

    failed = client.post(
        f'/api/v1/single-tasks/{maze_game_id}/run',
        headers=headers,
        json={
            'team_id': empty_team['team_id'],
            'requested_by': user_id,
        },
    )
    assert failed.status_code == 422
    assert failed.json()['error']['code'] == 'invariant_violation'

    canceled_attempts = client.get(
        f'/api/v1/single-tasks/{maze_game_id}/attempts?requested_by={user_id}&status=canceled',
        headers=headers,
    )
    assert canceled_attempts.status_code == 200
    assert len(canceled_attempts.json()) == 1
    assert canceled_attempts.json()[0]['error_message'].startswith('snapshot_validation_failed:')

    ready_team_id, headers = _create_ready_team(client, game_id=coins_game_id, user_id=user_id)
    next_attempt = client.post(
        f'/api/v1/single-tasks/{coins_game_id}/run',
        headers=headers,
        json={
            'team_id': ready_team_id,
            'requested_by': user_id,
        },
    )

    assert next_attempt.status_code == 200, next_attempt.json()
    assert next_attempt.json()['status'] == 'queued'


def test_single_task_attempts_endpoint_supports_filter_and_limit(client) -> None:
    teacher_headers = _auth_headers(client, 'attempts-teacher', role='teacher')
    game_id = _find_game_id(client, 'maze_escape_v1', headers=teacher_headers)
    team_a, headers_a = _create_ready_team(client, game_id=game_id, user_id='attempt-a')
    team_b, headers_b = _create_ready_team(client, game_id=game_id, user_id='attempt-b')

    run_a = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        headers=headers_a,
        json={'team_id': team_a, 'requested_by': 'attempt-a'},
    ).json()
    _finish_run(client, run_id=run_a['run_id'], metrics={'score': 10, 'solved': True})

    run_b = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        headers=headers_b,
        json={'team_id': team_b, 'requested_by': 'attempt-b'},
    ).json()
    _finish_run(client, run_id=run_b['run_id'], metrics={'score': 12, 'solved': True})

    run_a2 = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        headers=headers_a,
        json={'team_id': team_a, 'requested_by': 'attempt-a'},
    ).json()
    _finish_run(client, run_id=run_a2['run_id'], metrics={'score': 15, 'solved': True})

    filtered = client.get(
        f'/api/v1/single-tasks/{game_id}/attempts?requested_by=attempt-a&limit=1',
        headers=teacher_headers,
    )
    assert filtered.status_code == 200
    items = filtered.json()
    assert len(items) == 1
    assert items[0]['run_id'] == run_a2['run_id']


def test_single_task_attempts_endpoint_supports_status_and_offset(client) -> None:
    headers = _auth_headers(client, 'offset-user')
    game_id = _find_game_id(client, 'maze_escape_v1', headers=headers)
    team, headers = _create_ready_team(client, game_id=game_id, user_id='offset-user')

    run_finished = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        headers=headers,
        json={'team_id': team, 'requested_by': 'offset-user'},
    ).json()
    _finish_run(client, run_id=run_finished['run_id'], metrics={'score': 7, 'solved': True})

    run_cancelled = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        headers=headers,
        json={'team_id': team, 'requested_by': 'offset-user'},
    ).json()
    cancelled = client.post(
        f'/api/v1/single-tasks/{game_id}/stop',
        headers=headers,
        json={'run_id': run_cancelled['run_id']},
    )
    assert cancelled.status_code == 200

    finished_only = client.get(f'/api/v1/single-tasks/{game_id}/attempts?status=finished', headers=headers)
    assert finished_only.status_code == 200
    finished_items = finished_only.json()
    assert len(finished_items) == 1
    assert finished_items[0]['run_id'] == run_finished['run_id']

    paged = client.get(f'/api/v1/single-tasks/{game_id}/attempts?limit=1&offset=1', headers=headers)
    assert paged.status_code == 200
    paged_items = paged.json()
    assert len(paged_items) == 1
    assert paged_items[0]['run_id'] == run_finished['run_id']


def test_single_task_stop_and_logs_endpoints(client) -> None:
    headers = _auth_headers(client, 'stopper')
    game_id = _find_game_id(client, 'maze_escape_v1', headers=headers)
    team_id, headers = _create_ready_team(client, game_id=game_id, user_id='stopper')

    run = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        headers=headers,
        json={'team_id': team_id, 'requested_by': 'stopper'},
    ).json()

    stop = client.post(
        f'/api/v1/single-tasks/{game_id}/stop',
        headers=headers,
        json={'run_id': run['run_id']},
    )
    assert stop.status_code == 200
    assert stop.json()['status'] == 'canceled'
    assert stop.json()['error_message'] == 'manual_stop_single_task'

    run_for_logs = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        headers=headers,
        json={'team_id': team_id, 'requested_by': 'stopper'},
    ).json()
    _finish_run(
        client,
        run_id=run_for_logs['run_id'],
        metrics={'score': 0, 'solved': False, 'compile_error': 'invalid syntax'},
    )

    logs = client.get(f"/api/v1/single-task-attempts/{run_for_logs['run_id']}/logs", headers=headers)
    assert logs.status_code == 200
    payload = logs.json()
    assert payload['attempt_id'] == run_for_logs['run_id']
    assert payload['lines'] == ['compile_error: invalid syntax']

    lookup = client.get(f"/api/v1/single-task-attempts/{run_for_logs['run_id']}", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()['run_kind'] == 'single_task'
