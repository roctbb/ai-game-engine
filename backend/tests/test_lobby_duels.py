from training_lobby.domain.model import LobbyStatus


def fixture_lobby(client, teacher_headers, count=4):
    game = next(g for g in client.get('/api/v1/games').json() if g['slug'] == 'ttt_connect5_v1')
    lobby = client.post('/api/v1/lobbies', headers=teacher_headers, json={
        'game_id': game['game_id'], 'title': 'Duel test', 'kind': 'training', 'access': 'public', 'max_teams': 8,
    }).json()
    teams, headers = [], []
    for index in range(count):
        name = f'duel-{index}'
        token = client.post('/api/v1/auth/dev-login', json={'nickname': name, 'role': 'student'}).json()['session_id']
        own = {'X-Session-Id': token}
        joined = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/join", headers=own, json={})
        assert joined.status_code == 200, joined.text
        team = joined.json()['my_team_id']
        updated = client.put(f'/api/v1/teams/{team}/slots/bot', headers=own, json={
            'actor_user_id': name, 'code': 'def make_choice(field, role):\n    return 2, 2\n',
        })
        assert updated.status_code == 200, updated.text
        teams.append(team)
        headers.append(own)
    return lobby['lobby_id'], teams, headers


def duel(client, lobby, opponent, headers):
    return client.post(f'/api/v1/lobbies/{lobby}/duels', headers=headers, json={'opponent_team_id': opponent})


def finish(client, run_ids, teams, *, draw=True):
    scores = {teams[0]: .5 if draw else 1, teams[1]: .5 if draw else 0}
    payload = {'status': 'finished', 'scores': scores, 'placements': {teams[0]: 1, teams[1]: 1 if draw else 2},
               'metrics': {'draw': draw}, 'frames': [{'tick': 0, 'frame': {}}, {'tick': 1, 'frame': {}}]}
    if draw:
        payload['tie_resolution'] = 'explicit_tie'
    response = client.post(f'/api/v1/internal/runs/{run_ids[0]}/finished', json={'payload': payload})
    assert response.status_code == 200, response.text


def test_duel_uses_exact_pair_and_is_idempotent_without_changing_queue(client, container, teacher_headers):
    lobby, teams, headers = fixture_lobby(client, teacher_headers)
    container.training_lobby.set_ready(lobby, teams[2], True)
    container.training_lobby.set_ready(lobby, teams[3], True)
    container.training_lobby.mark_viewer_online(lobby, 'teacher-test')
    container.training_lobby.run_matchmaking_cycle(lobby, 'system')
    batch = container.training_lobby.get_lobby(lobby).last_scheduled_match_groups
    response = duel(client, lobby, teams[1], headers[0])
    assert response.status_code == 200, response.text
    ids = response.json()['run_ids']
    assert {container.execution.get_run(rid).team_id for rid in ids} == set(teams[:2])
    assert all(container.execution.get_run(rid).snapshot_id for rid in ids)
    assert duel(client, lobby, teams[1], headers[0]).json()['run_ids'] == ids
    assert duel(client, lobby, teams[0], headers[1]).json()['run_id'] == ids[1]
    assert container.training_lobby.get_lobby(lobby).last_scheduled_match_groups == batch
    assert not container.training_lobby.get_lobby(lobby).teams[teams[0]].ready
    assert client.get(f'/api/v1/runs/{ids[0]}/code', headers=headers[0]).status_code == 200
    assert client.get(f'/api/v1/runs/{ids[1]}/code', headers=headers[0]).status_code == 403
    assert duel(client, lobby, teams[2], headers[0]).status_code == 422
    finish(client, ids, teams[:2])
    view = client.get(f'/api/v1/lobbies/{lobby}', headers=headers[0]).json()
    assert any(set(item['run_ids']) == set(ids) for item in view['current_match_groups'])
    clock = client.get(f'/api/v1/runs/{ids[0]}/watch-context', headers=headers[0]).json()['first_show']
    assert clock['started_at'] is not None  # The unrelated training match is still queued.
    assert len(container.training_lobby.get_lobby(lobby).last_scheduled_match_groups) == 1


def test_duel_validation_and_ownership(client, container, teacher_headers):
    lobby, teams, headers = fixture_lobby(client, teacher_headers, count=2)
    assert duel(client, lobby, teams[0], headers[0]).status_code == 422
    assert duel(client, lobby, 'foreign-team', headers[0]).status_code == 404
    assert duel(client, lobby, teams[0], teacher_headers).status_code == 422
    container.training_lobby.set_status(lobby, LobbyStatus.PAUSED)
    assert duel(client, lobby, teams[1], headers[0]).status_code == 422


def test_duel_results_survive_archive_and_legacy_counts_stay_explicit(client, container, teacher_headers):
    from training_lobby.infrastructure.sqlalchemy_repository import _map_lobby_from_orm, _map_lobby_to_orm
    lobby, teams, headers = fixture_lobby(client, teacher_headers, count=2)
    for draw in [False, True]:
        response = duel(client, lobby, teams[1], headers[0])
        assert response.status_code == 200, response.text
        ids = response.json()['run_ids']
        finish(client, ids, teams, draw=draw)
        saved = container.training_lobby.get_lobby(lobby)
        runs = {rid: container.execution.get_run(rid) for rid in ids}
        container.training_lobby._add_cumulative_stats_for_match_groups(lobby=saved, groups=[ids], runs_by_id=runs)
        container.execution.delete_runs(ids)
        saved = _map_lobby_from_orm(_map_lobby_to_orm(saved))
        container.training_lobby._repository.save(saved)
        container.training_lobby._clear_lobby_derived_caches(lobby)
    view = client.get(f'/api/v1/lobbies/{lobby}', headers=headers[0]).json()
    stats = {item['team_id']: item for item in view['participant_stats']}
    assert (stats[teams[0]]['wins'], stats[teams[0]]['draws'], stats[teams[0]]['losses']) == (1, 1, 0)
    assert (stats[teams[1]]['wins'], stats[teams[1]]['draws'], stats[teams[1]]['losses']) == (0, 1, 1)
    assert stats[teams[0]]['matches_total'] == 2
    saved = container.training_lobby.get_lobby(lobby)
    saved.cumulative_stats_by_team[teams[0]] = {'matches_total': 40, 'wins': 6, 'score_sum': 6, 'score_count': 40}
    container.training_lobby._repository.save(_map_lobby_from_orm(_map_lobby_to_orm(saved)))
    container.training_lobby._clear_lobby_derived_caches(lobby)
    stat = next(item for item in client.get(f'/api/v1/lobbies/{lobby}', headers=headers[0]).json()['participant_stats'] if item['team_id'] == teams[0])
    assert stat['outcomes_unknown'] == 34 and stat['draws'] == 0 and stat['losses'] == 0


def test_matchmaker_can_schedule_others_while_duel_runs(client, container, teacher_headers):
    lobby, teams, headers = fixture_lobby(client, teacher_headers)
    ids = duel(client, lobby, teams[1], headers[0]).json()['run_ids']
    for team in teams[2:]:
        container.training_lobby.set_ready(lobby, team, True)
    container.training_lobby.mark_viewer_online(lobby, 'teacher-test')
    container.training_lobby.run_matchmaking_cycle(lobby, 'system')
    groups = container.training_lobby.get_lobby(lobby).last_scheduled_match_groups
    assert len(groups) == 1
    assert {container.execution.get_run(rid).team_id for rid in groups[0]} == set(teams[2:])
    assert not set(ids).intersection(groups[0])


def test_duel_rejects_active_competition(client, teacher_headers):
    lobby, teams, headers = fixture_lobby(client, teacher_headers, count=2)
    competition = client.post(f'/api/v1/lobbies/{lobby}/competitions/start', headers=teacher_headers, json={
        'title': 'Duels locked', 'format': 'single_elimination', 'tie_break_policy': 'manual',
        'code_policy': 'locked_on_start', 'advancement_top_k': 1, 'match_size': 2,
        'participant_selection': 'selected', 'team_ids': teams,
    })
    assert competition.status_code == 200, competition.text
    response = duel(client, lobby, teams[1], headers[0])
    assert response.status_code == 422
    assert 'соревнования' in response.json()['error']['message']


def test_duels_do_not_require_or_remove_queue_readiness(client, container, teacher_headers):
    lobby, teams, headers = fixture_lobby(client, teacher_headers, count=2)
    for team in teams:
        container.training_lobby.set_ready(lobby, team, True)
    response = duel(client, lobby, teams[1], headers[0])
    assert response.status_code == 200, response.text
    assert all(container.training_lobby.get_lobby(lobby).teams[team].ready for team in teams)
    assert client.get(f'/api/v1/lobbies/{lobby}', headers=headers[0]).json()['cycle_phase_label'] == 'Дуэль выполняется'


def test_duel_rejects_games_requiring_more_players(client, container, teacher_headers):
    lobby, teams, headers = fixture_lobby(client, teacher_headers, count=2)
    game = container.game_catalog.get_game(container.training_lobby.get_lobby(lobby).game_id)
    game.min_players_per_match = 3
    game.max_players_per_match = 4
    container.game_catalog._repository.save(game)
    response = duel(client, lobby, teams[1], headers[0])
    assert response.status_code == 422
    assert 'двух игроков' in response.json()['error']['message']
