# Backend (FastAPI)

Новый backend-каркас с DDD-структурой и in-memory реализацией ключевых bounded-context'ов:
- `game_catalog`
- `team_workspace`
- `training_lobby`
- `execution`
- `identity` (dev-login)

Дополнительно уже реализованы доменные инварианты:
- snapshot фиксируется строго на переходе `created -> queued`;
- при смене версии игры в лобби `ready` перевалидацируется;
- `execution` валидирует `result payload` по `run_kind` (`single_task`, `training_match`, `competition_match`).
- `single_task` запрещает параллельные активные запуски для одного пользователя по всей платформе;
- активный `run` можно явно остановить через `POST /api/v1/runs/{runId}/cancel`.
- для `single_task` доступны API прогресса:
  - `POST /api/v1/single-tasks/{gameId}/run`;
  - `POST /api/v1/single-tasks/{gameId}/stop`;
  - `GET /api/v1/single-tasks/{gameId}/attempts` (фильтры: `requested_by`, `status`, `limit`, `offset`);
  - `GET /api/v1/single-tasks/{gameId}/leaderboard`;
  - `GET /api/v1/catalog/single-tasks`;
  - `GET /api/v1/catalog/single-tasks/solved-summary`.
- `single_task` поддерживает `catalog_metadata_status` (`draft|ready|archived`);
- публичный каталог `GET /api/v1/catalog/single-tasks` возвращает только задачи в статусе `ready`;
- попытка выставить `catalog_metadata_status=ready` без `description/difficulty/topics` отклоняется.
- mutation-endpoint’ы каталога игр (`POST /games`, `POST /games/{id}/versions`, `POST /games/{id}/activate`, `PATCH /games/{id}/catalog-metadata`) требуют роль `teacher/admin`.
- при `queue_run` backend вызывает `scheduler-service` (`/internal/runs/{runId}/schedule`);
- если scheduler недоступен, `run` переводится в `failed`, а API возвращает `503`.

## Scheduler integration

Настройка через env:
- `SCHEDULER_SERVICE_URL` — base URL scheduler-service (например, `http://scheduler-service:8010`).
- `DATABASE_URL_OVERRIDE` — явный DSN для backend (например, sqlite в тестах).
- `CORE_REPOSITORY_BACKEND` — `memory` или `sqlalchemy` для `game_catalog/team_workspace/training_lobby`.
- `CORE_REPOSITORY_AUTO_CREATE_TABLES` — авто-создание core-таблиц (`true|false`).
- `EXECUTION_REPOSITORY_BACKEND` — `memory` или `sqlalchemy`.
- `EXECUTION_REPOSITORY_AUTO_CREATE_TABLES` — авто-создание execution-таблиц (`true|false`).

Если переменная не задана, backend использует `NoopSchedulerGateway` (удобно для изолированных локальных тестов).
Если `EXECUTION_REPOSITORY_BACKEND` не задан, используется `memory` для execution-репозиториев.
Если `CORE_REPOSITORY_BACKEND` не задан, используется `memory` для core-контекстов.

## Run (dev)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload --app-dir src
```

## Tests

```bash
cd backend
pytest
```

## Alembic migrations (v2 backend)

```bash
cd backend
alembic -c alembic.ini upgrade head
```

Для отката:

```bash
cd backend
alembic -c alembic.ini downgrade -1
```
