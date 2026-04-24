def _register_worker(client, *, worker_id: str = 'w-1', hostname: str = 'host-1', capacity_total: int = 2, labels: dict | None = None) -> dict:
    response = client.post(
        '/api/v1/internal/workers/register',
        json={
            'worker_id': worker_id,
            'hostname': hostname,
            'capacity_total': capacity_total,
            'labels': labels or {},
        },
    )
    assert response.status_code == 200
    return response.json()


def _set_status(client, worker_id: str, status: str) -> dict:
    response = client.patch(
        f'/api/v1/internal/workers/{worker_id}/status',
        json={'status': status},
    )
    assert response.status_code == 200
    return response.json()


def _heartbeat(client, worker_id: str, capacity_available: int) -> dict:
    response = client.post(
        f'/api/v1/internal/workers/{worker_id}/heartbeat',
        json={'capacity_available': capacity_available},
    )
    assert response.status_code == 200
    return response.json()


def test_worker_status_draining_and_disabled_are_preserved_on_heartbeat(client) -> None:
    worker = _register_worker(client, worker_id='worker-status-1')
    assert worker['status'] == 'online'

    worker = _set_status(client, 'worker-status-1', 'draining')
    assert worker['status'] == 'draining'

    worker = _heartbeat(client, 'worker-status-1', 1)
    assert worker['status'] == 'draining'
    assert worker['capacity_available'] == 1

    worker = _set_status(client, 'worker-status-1', 'disabled')
    assert worker['status'] == 'disabled'

    worker = _heartbeat(client, 'worker-status-1', 0)
    assert worker['status'] == 'disabled'
    assert worker['capacity_available'] == 0


def test_worker_status_offline_returns_to_online_on_heartbeat(client) -> None:
    _register_worker(client, worker_id='worker-status-2')

    worker = _set_status(client, 'worker-status-2', 'offline')
    assert worker['status'] == 'offline'

    worker = _heartbeat(client, 'worker-status-2', 2)
    assert worker['status'] == 'online'


def test_register_does_not_reset_disabled_worker_status(client) -> None:
    _register_worker(
        client,
        worker_id='worker-status-3',
        hostname='host-before',
        capacity_total=3,
        labels={'pool': 'default'},
    )
    _set_status(client, 'worker-status-3', 'disabled')

    second_register = _register_worker(
        client,
        worker_id='worker-status-3',
        hostname='host-after',
        capacity_total=5,
        labels={'pool': 'remote', 'region': 'eu'},
    )
    assert second_register['status'] == 'disabled'
    assert second_register['hostname'] == 'host-after'
    assert second_register['capacity_total'] == 5
    assert second_register['labels'] == {'pool': 'remote', 'region': 'eu'}


def test_list_workers_contains_updated_status(client) -> None:
    _register_worker(client, worker_id='worker-status-4')
    _set_status(client, 'worker-status-4', 'draining')

    listed = client.get('/api/v1/internal/workers')
    assert listed.status_code == 200
    workers = listed.json()
    row = next(item for item in workers if item['worker_id'] == 'worker-status-4')
    assert row['status'] == 'draining'
