from shared.kernel import ExternalServiceError
from game_catalog.application.service import RegisterGameInput
from game_catalog.domain.model import GameMode, SlotDefinition


def _prepare_single_task_run(client, user_id: str = 'student-scheduler') -> str:
    games = client.get('/api/v1/games').json()
    game = next(item for item in games if item['slug'] == 'maze_escape_v1')

    team = client.post(
        '/api/v1/teams',
        json={
            'game_id': game['game_id'],
            'name': 'Queue Team',
            'captain_user_id': user_id,
        },
    ).json()

    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={'actor_user_id': user_id, 'code': "print('queue')"},
    )

    run = client.post(
        '/api/v1/runs',
        json={
            'team_id': team['team_id'],
            'game_id': game['game_id'],
            'requested_by': user_id,
            'run_kind': 'single_task',
        },
    ).json()

    return run['run_id']


class _SpyGateway:
    def __init__(self) -> None:
        self.called_with: list[tuple[str, dict[str, str] | None]] = []

    def schedule_run(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> None:
        self.called_with.append((run_id, required_worker_labels))


class _FailingGateway:
    def schedule_run(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> None:
        _ = required_worker_labels
        raise ExternalServiceError(f'scheduler down for {run_id}')


def test_queue_run_calls_scheduler_gateway(client, container):
    spy = _SpyGateway()
    container.execution._scheduler_gateway = spy

    run_id = _prepare_single_task_run(client)
    queued = client.post(f'/api/v1/runs/{run_id}/queue')

    assert queued.status_code == 200
    assert queued.json()['status'] == 'queued'
    assert spy.called_with == [(run_id, {})]


def test_queue_run_failure_marks_run_failed_and_returns_503(client, container):
    container.execution._scheduler_gateway = _FailingGateway()

    run_id = _prepare_single_task_run(client, user_id='student-scheduler-2')
    response = client.post(f'/api/v1/runs/{run_id}/queue')

    assert response.status_code == 503
    assert response.json()['error']['code'] == 'external_service_error'

    run = client.get(f'/api/v1/runs/{run_id}').json()
    assert run['status'] == 'failed'


def test_queue_run_passes_required_worker_labels_from_game_version(client, container):
    game = container.game_catalog.register_game(
        RegisterGameInput(
            slug='labeled_single_task',
            title='Labeled Single Task',
            mode=GameMode.SINGLE_TASK,
            semver='1.0.0',
            required_slots=(SlotDefinition(key='agent', title='Agent', required=True),),
            required_worker_labels={'pool': 'gpu', 'region': 'eu-mow-1'},
        )
    )

    team = client.post(
        '/api/v1/teams',
        json={
            'game_id': game.game_id,
            'name': 'Labeled Queue Team',
            'captain_user_id': 'student-labeled',
        },
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/agent",
        json={'actor_user_id': 'student-labeled', 'code': "print('gpu')"},
    )
    run = client.post(
        '/api/v1/runs',
        json={
            'team_id': team['team_id'],
            'game_id': game.game_id,
            'requested_by': 'student-labeled',
            'run_kind': 'single_task',
        },
    ).json()

    spy = _SpyGateway()
    container.execution._scheduler_gateway = spy
    queued = client.post(f"/api/v1/runs/{run['run_id']}/queue")

    assert queued.status_code == 200
    assert spy.called_with == [(run['run_id'], {'pool': 'gpu', 'region': 'eu-mow-1'})]
