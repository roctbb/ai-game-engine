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
- таймаут движка получает статус `timeout`, а инфраструктурные ошибки — `failed`;
- активный `run` можно явно остановить через `POST /api/v1/runs/{runId}/cancel`.
- для `single_task` доступны API прогресса:
  - `POST /api/v1/single-tasks/{gameId}/run`;
  - `POST /api/v1/single-tasks/{gameId}/stop`;
  - `GET /api/v1/single-tasks/{gameId}/attempts` (фильтры: `requested_by`, `status`, `limit`, `offset`);
  - `GET /api/v1/single-tasks/{gameId}/leaderboard`;
  - `GET /api/v1/catalog/single-tasks`;
  - `GET /api/v1/catalog/single-tasks/solved-summary`.
- материалы `GET /api/v1/catalog/single-tasks` показывают все задачи преподавателю и администратору, включая задачи без заполненных метаданных;
- ученик открывает задачу по прямой ссылке, без доступа к каталогу; состояний публикации и переключателей видимости нет.
- mutation-endpoint’ы каталога игр (`POST /games`, `POST /games/{id}/versions`, `POST /games/{id}/activate`, `PATCH /games/{id}/catalog-metadata`) требуют роль `teacher/admin`.
- при `queue_run` backend вызывает `scheduler-service` (`/internal/runs/{runId}/schedule`);
- если scheduler недоступен, `run` остается `queued`: намерение отправки сохраняется вместе с запуском и повторяется фоновым обработчиком;
- переходы запусков защищены ревизией записи, а БД запрещает две активные одиночные попытки одного пользователя;
- результаты матчей, реплеи и отмена восстанавливаются после частичного сбоя через сохраняемое состояние доставки;
- multiplayer-матч, включая турнирный, выполняется один раз для всей группы команд;
- пакет движка фиксируется по SHA-256 при постановке в очередь и выдается worker через внутренний API.

Перед миграцией остановите новые запуски и старые worker. Затем примените `alembic upgrade head`
и обновите backend, scheduler и worker вместе. Миграция возвращает незавершенные основные запуски
в очередь, в том числе потерявшие запись lease в старом scheduler.
Миграция `0015_execution_reliability` оставляет старейшую активную одиночную попытку пользователя,
а дубликаты переводит в `canceled`. Для игровых пакетов используется `GAME_PACKAGES_ROOT`;
backend API и matchmaker должны видеть один постоянный каталог (в Compose — volume `game_packages`).

Миграция `0016_lease_generation_bigint` расширяет `lease_generation` до `BIGINT` в PostgreSQL:
поколения lease используют микросекунды и не помещаются в 32-битный `INTEGER`.
Обновление с `0015` сохраняет данные и совместимо с работающими scheduler и worker.

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

Для проверки SQL-репозиториев и полного цикла запуска на PostgreSQL задайте `POSTGRES_TEST_URL`.
Тесты создают отдельные временные схемы и удаляют их после проверки. В CI PostgreSQL и Redis
доступны всегда; локально эти интеграционные проверки требуют PostgreSQL и `redis-server`.

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
