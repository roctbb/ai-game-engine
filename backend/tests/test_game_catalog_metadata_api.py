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
    assert game['catalog_metadata_status'] == 'ready'


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
            'catalog_metadata_status': 'draft',
        },
        headers=teacher_headers,
    )

    assert patched.status_code == 200
    payload = patched.json()
    assert payload['description'] == 'Обновленное описание'
    assert payload['difficulty'] == 'hard'
    assert payload['learning_section'] == 'Жадные стратегии'
    assert payload['topics'] == ['алгоритмы', 'оптимизация']
    assert payload['catalog_metadata_status'] == 'draft'

    fetched = client.get(f"/api/v1/games/{game['game_id']}")
    assert fetched.status_code == 200
    assert fetched.json()['topics'] == ['алгоритмы', 'оптимизация']


def test_single_task_cannot_switch_to_ready_without_required_metadata(client, teacher_headers) -> None:
    game = client.post(
        '/api/v1/games',
        json={
            'slug': 'metadata_game_ready_guard',
            'title': 'Metadata Game Ready Guard',
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

    failed = client.patch(
        f"/api/v1/games/{game['game_id']}/catalog-metadata",
        json={
            'description': None,
            'difficulty': None,
            'learning_section': None,
            'topics': [],
            'catalog_metadata_status': 'ready',
        },
        headers=teacher_headers,
    )

    assert failed.status_code == 422
    assert failed.json()['error']['code'] == 'invariant_violation'


def test_single_task_can_switch_to_ready_when_metadata_filled(client, teacher_headers) -> None:
    game = client.post(
        '/api/v1/games',
        json={
            'slug': 'metadata_game_ready_ok',
            'title': 'Metadata Game Ready OK',
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
            'description': 'Описание',
            'difficulty': 'easy',
            'learning_section': 'Матрицы и координаты',
            'topics': ['графы'],
            'catalog_metadata_status': 'ready',
        },
        headers=teacher_headers,
    )

    assert patched.status_code == 200
    payload = patched.json()
    assert payload['catalog_metadata_status'] == 'ready'


def test_hidden_single_task_is_removed_from_public_catalog_and_summary(client, teacher_headers) -> None:
    game = client.post(
        '/api/v1/games',
        json={
            'slug': 'metadata_game_hidden',
            'title': 'Metadata Game Hidden',
            'mode': 'single_task',
            'semver': '1.0.0',
            'description': 'Описание',
            'difficulty': 'easy',
            'learning_section': 'Hidden Section API',
            'topics': ['visibility'],
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

    visible_catalog = client.get('/api/v1/catalog/single-tasks')
    assert visible_catalog.status_code == 200
    assert any(item['game_id'] == game['game_id'] for item in visible_catalog.json())
    visible_summary = client.get('/api/v1/catalog/single-tasks/solved-summary')
    assert visible_summary.status_code == 200
    visible_total = visible_summary.json()['total_single_tasks']

    student = client.post(
        '/api/v1/auth/dev-login',
        json={'nickname': 'hidden-task-student', 'role': 'student'},
    ).json()
    student_headers = {'X-Session-Id': student['session_id']}
    visible_student_team = client.post(
        '/api/v1/teams',
        json={'game_id': game['game_id'], 'name': 'Hidden Student', 'captain_user_id': 'ignored'},
        headers=student_headers,
    )
    assert visible_student_team.status_code == 200

    patched = client.patch(
        f"/api/v1/games/{game['game_id']}/catalog-metadata",
        json={
            'description': 'Описание',
            'difficulty': 'easy',
            'learning_section': 'Hidden Section API',
            'topics': ['visibility'],
            'catalog_metadata_status': 'ready',
            'is_hidden': True,
        },
        headers=teacher_headers,
    )

    assert patched.status_code == 200
    assert patched.json()['is_hidden'] is True

    hidden_catalog = client.get('/api/v1/catalog/single-tasks')
    assert hidden_catalog.status_code == 200
    assert all(item['game_id'] != game['game_id'] for item in hidden_catalog.json())
    hidden_summary = client.get('/api/v1/catalog/single-tasks/solved-summary')
    assert hidden_summary.status_code == 200
    assert hidden_summary.json()['total_single_tasks'] == visible_total - 1

    student_games = client.get('/api/v1/games', headers=student_headers)
    assert student_games.status_code == 200
    assert all(item['game_id'] != game['game_id'] for item in student_games.json())

    student_direct = client.get(f"/api/v1/games/{game['game_id']}", headers=student_headers)
    assert student_direct.status_code == 404

    hidden_student_team = client.post(
        '/api/v1/teams',
        json={'game_id': game['game_id'], 'name': 'Hidden Student', 'captain_user_id': 'ignored'},
        headers=student_headers,
    )
    assert hidden_student_team.status_code == 404
    hidden_workspace = client.get(
        f"/api/v1/teams/{visible_student_team.json()['team_id']}/workspace",
        headers=student_headers,
    )
    assert hidden_workspace.status_code == 404
    student_run = client.post(
        f"/api/v1/single-tasks/{game['game_id']}/run",
        json={'team_id': visible_student_team.json()['team_id'], 'requested_by': 'ignored'},
        headers=student_headers,
    )
    assert student_run.status_code == 404


def test_grouped_catalog_omits_section_when_all_its_tasks_are_hidden(client, teacher_headers) -> None:
    section = 'Hidden Group API'
    game_ids: list[str] = []
    for index in range(2):
        created = client.post(
            '/api/v1/games',
            json={
                'slug': f'metadata_game_hidden_group_{index}',
                'title': f'Metadata Game Hidden Group {index}',
                'mode': 'single_task',
                'semver': '1.0.0',
                'description': 'Описание',
                'difficulty': 'medium',
                'learning_section': section,
                'topics': ['visibility'],
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
        game_ids.append(created['game_id'])

    grouped_before = client.get('/api/v1/catalog/single-tasks/grouped')
    assert grouped_before.status_code == 200
    assert any(group['learning_section'] == section for group in grouped_before.json())

    for game_id in game_ids:
        hidden = client.patch(
            f'/api/v1/games/{game_id}/catalog-metadata',
            json={
                'description': 'Описание',
                'difficulty': 'medium',
                'learning_section': section,
                'topics': ['visibility'],
                'catalog_metadata_status': 'ready',
                'is_hidden': True,
            },
            headers=teacher_headers,
        )
        assert hidden.status_code == 200

    grouped_after = client.get('/api/v1/catalog/single-tasks/grouped')
    assert grouped_after.status_code == 200
    assert all(group['learning_section'] != section for group in grouped_after.json())


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
            'catalog_metadata_status': 'draft',
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
            'catalog_metadata_status': 'ready',
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
    assert payload['catalog_metadata_status'] == 'ready'


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
