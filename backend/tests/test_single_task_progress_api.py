from __future__ import annotations


def _find_game_id(client, slug: str) -> str:
    games = client.get('/api/v1/games').json()
    game = next(item for item in games if item['slug'] == slug)
    return game['game_id']


def _find_required_slot_key(client, game_id: str) -> str:
    game = client.get(f'/api/v1/games/{game_id}').json()
    active_version_id = game['active_version_id']
    version = next(item for item in game['versions'] if item['version_id'] == active_version_id)
    return version['required_slot_keys'][0]


def _prepare_team(client, game_id: str, user_id: str) -> str:
    team = client.post(
        '/api/v1/teams',
        json={
            'game_id': game_id,
            'name': f'Team {user_id}',
            'captain_user_id': user_id,
        },
    ).json()
    slot_key = _find_required_slot_key(client, game_id)
    update = client.put(
        f"/api/v1/teams/{team['team_id']}/slots/{slot_key}",
        json={
            'actor_user_id': user_id,
            'code': 'def make_move(x, y, board):\n    return "right"\n',
        },
    )
    assert update.status_code == 200
    return team['team_id']


def _finish_single_task_attempt(
    client,
    *,
    game_id: str,
    team_id: str,
    user_id: str,
    metrics: dict[str, object],
) -> None:
    run = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': user_id,
            'run_kind': 'single_task',
        },
    ).json()

    queued = client.post(f"/api/v1/runs/{run['run_id']}/queue")
    assert queued.status_code == 200

    finished = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/finished",
        json={
            'payload': {
                'status': 'finished',
                'metrics': metrics,
            }
        },
    )
    assert finished.status_code == 200


def test_single_task_leaderboard_uses_best_score_per_user(client) -> None:
    game_id = _find_game_id(client, 'maze_escape_v1')
    team_a = _prepare_team(client, game_id=game_id, user_id='user-a')
    team_b = _prepare_team(client, game_id=game_id, user_id='user-b')

    _finish_single_task_attempt(
        client,
        game_id=game_id,
        team_id=team_a,
        user_id='user-a',
        metrics={'score': 40, 'solved': True, 'reached_exit': True},
    )
    _finish_single_task_attempt(
        client,
        game_id=game_id,
        team_id=team_b,
        user_id='user-b',
        metrics={'score': 70, 'solved': True, 'reached_exit': True},
    )
    _finish_single_task_attempt(
        client,
        game_id=game_id,
        team_id=team_a,
        user_id='user-a',
        metrics={'score': 90, 'solved': True, 'reached_exit': True},
    )

    response = client.get(f'/api/v1/single-tasks/{game_id}/leaderboard')
    assert response.status_code == 200
    leaderboard = response.json()

    assert leaderboard['leaderboard_kind'] == 'score'
    assert leaderboard['entries'][0]['user_id'] == 'user-a'
    assert leaderboard['entries'][0]['best_score'] == 90
    assert leaderboard['entries'][0]['place'] == 1
    assert leaderboard['entries'][0]['finished_attempts'] == 2
    assert leaderboard['entries'][1]['user_id'] == 'user-b'
    assert leaderboard['entries'][1]['best_score'] == 70
    assert leaderboard['entries'][1]['place'] == 2


def test_catalog_solved_summary_counts_unique_tasks_per_user(client) -> None:
    maze_id = _find_game_id(client, 'maze_escape_v1')
    coins_id = _find_game_id(client, 'coins_right_down_v1')

    team_u1_maze = _prepare_team(client, game_id=maze_id, user_id='solver-1')
    team_u1_coins = _prepare_team(client, game_id=coins_id, user_id='solver-1')
    team_u2_maze = _prepare_team(client, game_id=maze_id, user_id='solver-2')

    _finish_single_task_attempt(
        client,
        game_id=maze_id,
        team_id=team_u1_maze,
        user_id='solver-1',
        metrics={'score': 30, 'solved': True, 'reached_exit': True},
    )
    _finish_single_task_attempt(
        client,
        game_id=coins_id,
        team_id=team_u1_coins,
        user_id='solver-1',
        metrics={'score': 15, 'solved': True, 'reached_goal': True},
    )
    _finish_single_task_attempt(
        client,
        game_id=maze_id,
        team_id=team_u2_maze,
        user_id='solver-2',
        metrics={'score': 10, 'solved': True, 'reached_exit': True},
    )

    response = client.get('/api/v1/catalog/single-tasks/solved-summary')
    assert response.status_code == 200
    summary = response.json()

    assert summary['total_single_tasks'] >= 3
    assert summary['entries'][0]['user_id'] == 'solver-1'
    assert summary['entries'][0]['solved_tasks_count'] == 2
    assert summary['entries'][1]['user_id'] == 'solver-2'
    assert summary['entries'][1]['solved_tasks_count'] == 1


def test_catalog_single_tasks_includes_attempt_stats(client) -> None:
    game_id = _find_game_id(client, 'maze_escape_v1')
    team_a = _prepare_team(client, game_id=game_id, user_id='stats-a')
    team_b = _prepare_team(client, game_id=game_id, user_id='stats-b')

    _finish_single_task_attempt(
        client,
        game_id=game_id,
        team_id=team_a,
        user_id='stats-a',
        metrics={'score': 5, 'solved': False, 'reached_exit': False},
    )
    _finish_single_task_attempt(
        client,
        game_id=game_id,
        team_id=team_a,
        user_id='stats-a',
        metrics={'score': 25, 'solved': True, 'reached_exit': True},
    )
    _finish_single_task_attempt(
        client,
        game_id=game_id,
        team_id=team_b,
        user_id='stats-b',
        metrics={'score': 10, 'solved': False, 'reached_exit': False},
    )

    response = client.get('/api/v1/catalog/single-tasks')
    assert response.status_code == 200
    items = response.json()
    maze = next(item for item in items if item['game_id'] == game_id)

    assert maze['attempts_finished'] == 3
    assert maze['solved_users'] == 1
    assert maze['has_score_model'] is True
    assert maze['catalog_metadata_status'] == 'ready'


def test_catalog_single_tasks_hides_draft_single_task_games(client, teacher_headers) -> None:
    created = client.post(
        '/api/v1/games',
        json={
            'slug': 'draft_hidden_single_task',
            'title': 'Draft Hidden Single Task',
            'mode': 'single_task',
            'semver': '1.0.0',
            'required_slots': [
                {
                    'key': 'agent',
                    'title': 'Agent',
                    'required': True,
                }
            ],
        },
        headers=teacher_headers,
    )
    assert created.status_code == 200
    game = created.json()
    assert game['catalog_metadata_status'] == 'draft'

    catalog = client.get('/api/v1/catalog/single-tasks')
    assert catalog.status_code == 200
    ids = {item['game_id'] for item in catalog.json()}
    assert game['game_id'] not in ids
