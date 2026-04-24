def _find_game_id(client, slug: str) -> str:
    games = client.get('/api/v1/games').json()
    game = next(item for item in games if item['slug'] == slug)
    return game['game_id']


def _prepare_team(client, game_id: str, slot_key: str) -> str:
    team = client.post(
        '/api/v1/teams',
        json={
            'game_id': game_id,
            'name': 'Payload Team',
            'captain_user_id': 'captain',
        },
    ).json()

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/{slot_key}",
        json={'actor_user_id': 'captain', 'code': "print('ready')"},
    )
    return team['team_id']


def test_competition_requires_placements(client):
    game_id = _find_game_id(client, 'ttt_connect5_v1')
    team_id = _prepare_team(client, game_id, 'bot')

    run = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': 'captain',
            'run_kind': 'competition_match',
        },
    ).json()

    client.post(f"/api/v1/runs/{run['run_id']}/queue")

    response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/finished",
        json={
            'payload': {
                'status': 'finished',
                'scores': {'team-a': 12, 'team-b': 10},
                'metrics': {'duration_ms': 1000},
            }
        },
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'invariant_violation'


def test_competition_ties_require_explicit_tie_resolution(client):
    game_id = _find_game_id(client, 'ttt_connect5_v1')
    team_id = _prepare_team(client, game_id, 'bot')

    run = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': 'captain',
            'run_kind': 'competition_match',
        },
    ).json()

    client.post(f"/api/v1/runs/{run['run_id']}/queue")

    response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/finished",
        json={
            'payload': {
                'status': 'finished',
                'placements': {'team-a': 1, 'team-b': 1},
                'metrics': {'duration_ms': 1000},
            }
        },
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'invariant_violation'


def test_competition_payload_with_placements_is_accepted(client):
    game_id = _find_game_id(client, 'ttt_connect5_v1')
    team_id = _prepare_team(client, game_id, 'bot')

    run = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': 'captain',
            'run_kind': 'competition_match',
        },
    ).json()

    client.post(f"/api/v1/runs/{run['run_id']}/queue")

    response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/finished",
        json={
            'payload': {
                'status': 'finished',
                'placements': {'team-a': 1, 'team-b': 2},
                'scores': {'team-a': 12, 'team-b': 10},
                'metrics': {'duration_ms': 1000},
            }
        },
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'finished'
    assert response.json()['result_payload']['placements'] == {'team-a': 1, 'team-b': 2}


def test_training_payload_requires_scores_or_placements(client):
    game_id = _find_game_id(client, 'ttt_connect5_v1')
    team_id = _prepare_team(client, game_id, 'bot')

    run = client.post(
        '/api/v1/runs',
        json={
            'team_id': team_id,
            'game_id': game_id,
            'requested_by': 'captain',
            'run_kind': 'training_match',
        },
    ).json()

    client.post(f"/api/v1/runs/{run['run_id']}/queue")

    response = client.post(
        f"/api/v1/internal/runs/{run['run_id']}/finished",
        json={
            'payload': {
                'status': 'finished',
            }
        },
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'invariant_violation'
