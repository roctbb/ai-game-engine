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
            'learning_section': 'Команды героя',
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
