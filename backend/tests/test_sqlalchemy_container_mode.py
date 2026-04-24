from pathlib import Path

from fastapi.testclient import TestClient

from app.dependencies import _build_container, get_container
from app.main import app
from shared.config.settings import settings


def test_sqlalchemy_container_mode_smoke(tmp_path: Path) -> None:
    original = {
        'database_url_override': settings.database_url_override,
        'core_repository_backend': settings.core_repository_backend,
        'core_repository_auto_create_tables': settings.core_repository_auto_create_tables,
        'execution_repository_backend': settings.execution_repository_backend,
        'execution_repository_auto_create_tables': settings.execution_repository_auto_create_tables,
        'scheduler_service_url': settings.scheduler_service_url,
    }

    try:
        db_file = tmp_path / 'agp_sqlalchemy_smoke.db'
        settings.database_url_override = f'sqlite+pysqlite:///{db_file}'
        settings.core_repository_backend = 'sqlalchemy'
        settings.core_repository_auto_create_tables = True
        settings.execution_repository_backend = 'sqlalchemy'
        settings.execution_repository_auto_create_tables = True
        settings.scheduler_service_url = None

        app.dependency_overrides.clear()
        container = _build_container()
        app.dependency_overrides[get_container] = lambda: container

        with TestClient(app) as client:
            login = client.post(
                '/api/v1/auth/dev-login',
                json={'nickname': 'captain-sql', 'role': 'teacher'},
            )
            assert login.status_code == 200
            headers = {'X-Session-Id': login.json()['session_id']}
            internal_headers = {'X-Internal-Token': settings.internal_api_token}

            games = client.get('/api/v1/games', headers=headers).json()
            maze_game = next(item for item in games if item['slug'] == 'maze_escape_v1')

            team = client.post(
                '/api/v1/teams',
                json={
                    'game_id': maze_game['game_id'],
                    'name': 'SQL Team',
                    'captain_user_id': 'captain-sql',
                },
                headers=headers,
            ).json()

            client.put(
                f"/api/v1/teams/{team['team_id']}/slots/agent",
                json={'actor_user_id': 'captain-sql', 'code': "print('sql mode')"},
                headers=headers,
            )

            run = client.post(
                '/api/v1/runs',
                json={
                    'team_id': team['team_id'],
                    'game_id': maze_game['game_id'],
                    'requested_by': 'captain-sql',
                    'run_kind': 'single_task',
                },
                headers=headers,
            ).json()

            queued = client.post(f"/api/v1/runs/{run['run_id']}/queue", headers=headers)
            assert queued.status_code == 200
            assert queued.json()['status'] == 'queued'
            assert queued.json()['snapshot_id'] is not None

            worker = client.post(
                '/api/v1/internal/workers/register',
                json={
                    'worker_id': 'sql-worker-1',
                    'hostname': 'sql-host',
                    'capacity_total': 2,
                    'labels': {'zone': 'sql-test'},
                },
                headers=internal_headers,
            )
            assert worker.status_code == 200

            accepted = client.post(
                f"/api/v1/internal/runs/{run['run_id']}/accepted",
                json={'worker_id': 'sql-worker-1'},
                headers=internal_headers,
            )
            assert accepted.status_code == 200
            assert accepted.json()['status'] == 'queued'
            assert accepted.json()['worker_id'] == 'sql-worker-1'

            started = client.post(
                f"/api/v1/internal/runs/{run['run_id']}/started",
                json={'worker_id': 'sql-worker-1'},
                headers=internal_headers,
            )
            assert started.status_code == 200
            assert started.json()['status'] == 'running'

            finished = client.post(
                f"/api/v1/internal/runs/{run['run_id']}/finished",
                json={
                    'payload': {
                        'status': 'finished',
                        'metrics': {'duration_ms': 123},
                    }
                },
                headers=internal_headers,
            )
            assert finished.status_code == 200
            assert finished.json()['status'] == 'finished'

            loaded = client.get(f"/api/v1/runs/{run['run_id']}", headers=headers)
            assert loaded.status_code == 200
            assert loaded.json()['status'] == 'finished'
            assert loaded.json()['worker_id'] == 'sql-worker-1'

            replay = client.get(f"/api/v1/replays/runs/{run['run_id']}", headers=headers)
            assert replay.status_code == 200
            assert replay.json()['status'] == 'finished'
            assert replay.json()['run_id'] == run['run_id']

    finally:
        settings.database_url_override = original['database_url_override']
        settings.core_repository_backend = original['core_repository_backend']
        settings.core_repository_auto_create_tables = original['core_repository_auto_create_tables']
        settings.execution_repository_backend = original['execution_repository_backend']
        settings.execution_repository_auto_create_tables = original['execution_repository_auto_create_tables']
        settings.scheduler_service_url = original['scheduler_service_url']
        app.dependency_overrides.clear()
