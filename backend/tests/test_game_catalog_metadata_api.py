def test_register_game_with_catalog_metadata(client, teacher_headers) -> None:
    response = client.post(
        '/api/v1/games',
        json={
            'slug': 'metadata_game',
            'title': 'Metadata Game',
            'mode': 'single_task',
            'semver': '1.0.0',
            'description': 'Учебная задача по графам',
            'difficulty': 'medium',
            'learning_section': 'Поиск пути BFS',
            'topics': ['графы', 'dfs'],
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

    assert response.status_code == 200
    game = response.json()
    assert game['description'] == 'Учебная задача по графам'
    assert game['difficulty'] == 'medium'
    assert game['learning_section'] == 'Поиск пути BFS'
    assert game['topics'] == ['графы', 'dfs']


def test_patch_catalog_metadata_updates_game(client, teacher_headers) -> None:
    game = client.post(
        '/api/v1/games',
        json={
            'slug': 'metadata_game_patch',
            'title': 'Metadata Game Patch',
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
    ).json()

    patched = client.patch(
        f"/api/v1/games/{game['game_id']}/catalog-metadata",
        json={
            'description': 'Обновленное описание',
            'difficulty': 'hard',
            'learning_section': 'Жадные стратегии',
            'topics': ['алгоритмы', 'оптимизация'],
        },
        headers=teacher_headers,
    )

    assert patched.status_code == 200
    payload = patched.json()
    assert payload['description'] == 'Обновленное описание'
    assert payload['difficulty'] == 'hard'
    assert payload['learning_section'] == 'Жадные стратегии'
    assert payload['topics'] == ['алгоритмы', 'оптимизация']

    fetched = client.get(f"/api/v1/games/{game['game_id']}")
    assert fetched.status_code == 200
    assert fetched.json()['topics'] == ['алгоритмы', 'оптимизация']


def test_incomplete_tasks_are_available_in_teacher_materials_and_by_student_link(client, teacher_headers) -> None:
    created = client.post(
        '/api/v1/games',
        json={
            'slug': 'incomplete_task', 'title': 'Incomplete Task',
            'mode': 'single_task', 'semver': '1.0.0',
            'required_slots': [{'key': 'agent', 'title': 'Agent'}],
            # Old clients cannot hide a task or make it a draft anymore.
            'catalog_metadata_status': 'draft', 'is_hidden': True,
        },
        headers=teacher_headers,
    )
    assert created.status_code == 200
    game = created.json()
    game_id = game['game_id']
    assert 'catalog_metadata_status' not in game
    assert 'is_hidden' not in game
    patched = client.patch(
        f'/api/v1/games/{game_id}/catalog-metadata',
        json={'description': None, 'difficulty': None, 'learning_section': None, 'topics': []},
        headers=teacher_headers,
    )
    assert patched.status_code == 200
    for role in ('teacher', 'admin'):
        session = client.post('/api/v1/auth/dev-login', json={'nickname': f'materials-{role}', 'role': role}).json()
        headers = {'X-Session-Id': session['session_id']}
        catalog = client.get('/api/v1/catalog/single-tasks', headers=headers)
        assert any(item['game_id'] == game_id for item in catalog.json())
        grouped = client.get('/api/v1/catalog/single-tasks/grouped', headers=headers)
        other = next(group for group in grouped.json() if group['learning_section'] == 'Другое')
        assert any(item['game_id'] == game_id for item in other['items'])
        summary = client.get('/api/v1/catalog/single-tasks/solved-summary', headers=headers)
        assert summary.json()['total_single_tasks'] == len(catalog.json())

    session = client.post('/api/v1/auth/dev-login', json={'nickname': 'linked-task-student', 'role': 'student'}).json()
    headers = {'X-Session-Id': session['session_id']}
    for path in ('/catalog/single-tasks', '/catalog/single-tasks/grouped', '/catalog/single-tasks/solved-summary'):
        assert client.get('/api/v1' + path, headers=headers).status_code == 403
    assert all(item['game_id'] != game_id for item in client.get('/api/v1/games', headers=headers).json())
    for suffix in ('', '/docs', '/templates', '/versions', '/topics'):
        assert client.get(f'/api/v1/games/{game_id}{suffix}', headers=headers).status_code == 200
    team = client.post('/api/v1/teams', json={'game_id': game_id, 'name': 'Linked Task', 'captain_user_id': 'ignored'}, headers=headers)
    assert team.status_code == 200
    team_id = team.json()['team_id']
    assert client.get(f'/api/v1/teams/{team_id}/workspace', headers=headers).status_code == 200
    saved = client.put(f'/api/v1/teams/{team_id}/slots/agent', json={'actor_user_id': 'ignored', 'code': 'def make_move(state): return "stay"'}, headers=headers)
    assert saved.status_code == 200
    run = client.post(f'/api/v1/single-tasks/{game_id}/run', json={'team_id': team_id, 'requested_by': 'ignored'}, headers=headers)
    assert run.status_code == 200


def test_game_catalog_mutations_require_teacher_or_admin(client) -> None:
    student = client.post(
        '/api/v1/auth/dev-login',
        json={'nickname': 'student-catalog', 'role': 'student'},
    ).json()
    headers = {'X-Session-Id': student['session_id']}

    response = client.post(
        '/api/v1/games',
        json={
            'slug': 'forbidden_catalog_mutation',
            'title': 'Forbidden Catalog Mutation',
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
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()['error']['code'] == 'forbidden'


def test_game_catalog_version_mutations_require_teacher_or_admin(client, teacher_headers) -> None:
    created = client.post(
        '/api/v1/games',
        json={
            'slug': 'rbac_version_mutations_game',
            'title': 'RBAC Version Mutations Game',
            'mode': 'small_match',
            'semver': '1.0.0',
            'required_slots': [
                {
                    'key': 'bot',
                    'title': 'Bot',
                    'required': True,
                }
            ],
        },
        headers=teacher_headers,
    ).json()

    student = client.post(
        '/api/v1/auth/dev-login',
        json={'nickname': 'student-catalog-2', 'role': 'student'},
    ).json()
    student_headers = {'X-Session-Id': student['session_id']}

    add_version = client.post(
        f"/api/v1/games/{created['game_id']}/versions",
        json={
            'semver': '1.1.0',
            'required_slots': [
                {
                    'key': 'bot',
                    'title': 'Bot',
                    'required': True,
                }
            ],
        },
        headers=student_headers,
    )
    assert add_version.status_code == 403
    assert add_version.json()['error']['code'] == 'forbidden'

    patched = client.patch(
        f"/api/v1/games/{created['game_id']}/catalog-metadata",
        json={
            'description': 'Nope',
            'difficulty': 'easy',
            'learning_section': 'Условия и выбор',
            'topics': ['test'],
        },
        headers=student_headers,
    )
    assert patched.status_code == 403
    assert patched.json()['error']['code'] == 'forbidden'

    added_by_teacher = client.post(
        f"/api/v1/games/{created['game_id']}/versions",
        json={
            'semver': '1.1.0',
            'required_slots': [
                {
                    'key': 'bot',
                    'title': 'Bot',
                    'required': True,
                }
            ],
        },
        headers=teacher_headers,
    ).json()
    next_version = next(item for item in added_by_teacher['versions'] if item['semver'] == '1.1.0')

    activate = client.post(
        f"/api/v1/games/{created['game_id']}/activate",
        json={'version_id': next_version['version_id']},
        headers=student_headers,
    )
    assert activate.status_code == 403
    assert activate.json()['error']['code'] == 'forbidden'


def test_patch_game_updates_title_and_catalog_fields(client, teacher_headers) -> None:
    created = client.post(
        '/api/v1/games',
        json={
            'slug': 'patch_game_full',
            'title': 'Patch Game Full',
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

    patched = client.patch(
        f"/api/v1/games/{game['game_id']}",
        json={
            'title': 'Patch Game Full v2',
            'description': 'Новый текст',
            'difficulty': 'medium',
            'learning_section': 'Списки и цели',
            'topics': ['api', 'metadata'],
        },
        headers=teacher_headers,
    )
    assert patched.status_code == 200
    payload = patched.json()
    assert payload['title'] == 'Patch Game Full v2'
    assert payload['description'] == 'Новый текст'
    assert payload['difficulty'] == 'medium'
    assert payload['learning_section'] == 'Списки и цели'
    assert payload['topics'] == ['api', 'metadata']


def test_patch_game_requires_teacher_or_admin(client, teacher_headers) -> None:
    created = client.post(
        '/api/v1/games',
        json={
            'slug': 'patch_game_rbac',
            'title': 'Patch Game RBAC',
            'mode': 'small_match',
            'semver': '1.0.0',
            'required_slots': [
                {
                    'key': 'bot',
                    'title': 'Bot',
                    'required': True,
                }
            ],
        },
        headers=teacher_headers,
    ).json()

    student = client.post(
        '/api/v1/auth/dev-login',
        json={'nickname': 'student-patch-game', 'role': 'student'},
    ).json()
    student_headers = {'X-Session-Id': student['session_id']}

    denied = client.patch(
        f"/api/v1/games/{created['game_id']}",
        json={'title': 'Denied change'},
        headers=student_headers,
    )
    assert denied.status_code == 403
    assert denied.json()['error']['code'] == 'forbidden'
