def _get_maze_game_id(client) -> str:
    games = client.get('/api/v1/games').json()
    game = next(item for item in games if item['slug'] == 'maze_escape_v1')
    return game['game_id']


def _create_ready_team(client, game_id: str, captain: str) -> str:
    team = client.post(
        '/api/v1/teams',
        json={
            'game_id': game_id,
            'name': 'Single Task Team',
            'captain_user_id': captain,
        },
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={'actor_user_id': captain, 'code': "print('go')"},
    )
    return team['team_id']


def test_user_cannot_start_second_single_task_run_while_first_is_active(client):
    user_id = 'student-1'
    game_id = _get_maze_game_id(client)
    team_id = _create_ready_team(client, game_id=game_id, captain=user_id)

    first = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': user_id,
            'run_kind': 'single_task',
        },
    )
    assert first.status_code == 200
    queued = client.post(f"/api/v1/runs/{first.json()['run_id']}/queue")
    assert queued.status_code == 200

    second = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': user_id,
            'run_kind': 'single_task',
        },
    )

    assert second.status_code == 409
    assert second.json()['error']['code'] == 'conflict'


def test_user_can_start_new_single_task_run_after_cancel(client):
    user_id = 'student-2'
    game_id = _get_maze_game_id(client)
    team_id = _create_ready_team(client, game_id=game_id, captain=user_id)

    first = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': user_id,
            'run_kind': 'single_task',
        },
    ).json()

    canceled = client.post(f"/api/v1/runs/{first['run_id']}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()['status'] == 'canceled'
    assert canceled.json()['error_message'] == 'manual_cancel'

    second = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': user_id,
            'run_kind': 'single_task',
        },
    )

    assert second.status_code == 200
    assert second.json()['status'] == 'created'


def test_stale_created_single_task_run_does_not_block_new_attempt(client):
    user_id = 'student-stale-created'
    game_id = _get_maze_game_id(client)
    stale_team_id = client.post(
        '/api/v1/teams',
        json={
            'game_id': game_id,
            'name': 'Stale Empty Team',
            'captain_user_id': user_id,
        },
    ).json()['team_id']
    ready_team_id = _create_ready_team(client, game_id=game_id, captain=user_id)

    stale = client.post(
        '/api/v1/runs',
        json={
            'team_id': stale_team_id,
            'game_id': game_id,
            'requested_by': user_id,
            'run_kind': 'single_task',
        },
    )
    assert stale.status_code == 200
    assert stale.json()['status'] == 'created'

    second = client.post(
        f'/api/v1/single-tasks/{game_id}/run',
        json={'team_id': ready_team_id, 'requested_by': user_id},
    )

    assert second.status_code == 200, second.json()
    assert second.json()['status'] == 'queued'
    stale_after = client.get(f"/api/v1/runs/{stale.json()['run_id']}").json()
    assert stale_after['status'] == 'canceled'
    assert stale_after['error_message'] == 'superseded_created_single_task'
