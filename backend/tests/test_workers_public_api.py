def _register_worker(client, worker_id: str = 'worker-public-1') -> dict:
    response = client.post(
        '/api/v1/internal/workers/register',
        json={
            'worker_id': worker_id,
            'hostname': f'{worker_id}.local',
            'capacity_total': 3,
            'labels': {'pool': 'remote'},
        },
    )
    assert response.status_code == 200
    return response.json()


def _admin_headers(client) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/dev-login",
        json={
            "nickname": "admin-workers",
            "role": "admin",
        },
    )
    assert login.status_code == 200
    return {"X-Session-Id": login.json()["session_id"]}


def test_public_workers_list_and_get(client) -> None:
    headers = _admin_headers(client)
    registered = _register_worker(client, worker_id='worker-public-list')

    listed_response = client.get('/api/v1/workers', headers=headers)
    assert listed_response.status_code == 200
    listed = listed_response.json()
    row = next(item for item in listed if item['worker_id'] == registered['worker_id'])
    assert row['hostname'] == registered['hostname']
    assert row['status'] == 'online'

    get_response = client.get(f"/api/v1/workers/{registered['worker_id']}", headers=headers)
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched['worker_id'] == registered['worker_id']
    assert fetched['labels'] == {'pool': 'remote'}


def test_public_workers_status_update(client) -> None:
    headers = _admin_headers(client)
    _register_worker(client, worker_id='worker-public-status')

    update_response = client.patch(
        '/api/v1/workers/worker-public-status/status',
        json={'status': 'draining'},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()['status'] == 'draining'

    fetched = client.get('/api/v1/workers/worker-public-status', headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()['status'] == 'draining'


def test_public_workers_forbidden_for_non_admin(client) -> None:
    _register_worker(client, worker_id='worker-public-student')
    teacher_login = client.post(
        "/api/v1/auth/dev-login",
        json={
            "nickname": "teacher-workers",
            "role": "teacher",
        },
    )
    assert teacher_login.status_code == 200
    teacher_headers = {"X-Session-Id": teacher_login.json()["session_id"]}
    teacher_response = client.get('/api/v1/workers', headers=teacher_headers)
    assert teacher_response.status_code == 403
    assert teacher_response.json()["error"]["code"] == "forbidden"

    login = client.post(
        "/api/v1/auth/dev-login",
        json={
            "nickname": "student-workers",
            "role": "student",
        },
    )
    assert login.status_code == 200
    headers = {"X-Session-Id": login.json()["session_id"]}

    response = client.get('/api/v1/workers', headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
