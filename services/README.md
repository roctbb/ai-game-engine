# Services

`services/` содержит выделенные сервисы новой архитектуры:
- `scheduler`
- `worker`
- `builder`

Каждый сервис запускается отдельно через свой Dockerfile.

## Локальный запуск через Docker Compose (v2)

```bash
docker compose -f compose.yml up --build
```

Порты по умолчанию:
- backend API: `8000`
- scheduler-service: `8010`
- worker-service: `8020`
- builder-service: `8030`
- frontend SPA: `8080`

## Scheduler/Worker протокол (MVP)

Scheduler:
- `POST /internal/runs/{run_id}/schedule` — добавить run в очередь
- `POST /internal/workers/pull-next` — выдать run конкретному worker и записать lease
- `POST /internal/runs/ack-finished` — подтвердить завершение run для актуального lease
- `GET /internal/queue/stats` — текущая глубина очереди и активные lease

Важно:
- `scheduler-service` должен работать с Redis не через `localhost`, а через переменную `REDIS_URL` (в compose: `redis://redis:6379/0`).
- scheduler использует `lease_ttl_seconds`: истекший lease автоматически снимается, а run возвращается в очередь.
- `ack-finished` может вернуть:
  - `acknowledged` — run закрыт по валидному lease;
  - `stale_lease_ignored` — ack проигнорирован как устаревший.

Worker:
- `POST /internal/worker/pull-and-execute` — забрать run у scheduler и выполнить manifest-based pipeline

Примечание:
- в текущей итерации `pull-and-execute` делает lifecycle:
  - запрашивает у backend `/internal/runs/{run_id}/execution-context`;
  - валидирует `execution-context` (`run_kind`, `code_api_mode`) и работает только для поддерживаемых `code_api_mode` (`script_based`, `turn_based`) и run kinds (`single_task`, `training_match`, `competition_match`);
  - запускает `engine_entrypoint` в одноразовом Docker-контейнере (`execution_mode=docker`);
  - применяет изоляцию и лимиты (`--read-only`, `--network`, CPU/RAM/PIDs, tmpfs);
  - при неполном/некорректном `execution-context` помечает run как `failed` (fail-fast), без fallback/stub;
  - `accepted` в backend
  - `started` в backend
  - `finished` в backend с payload, который вернул engine
  - `ack-finished` в scheduler
- worker регистрируется в control plane с `capacity_total` и `labels` (через `WORKER_LABELS`), а также отправляет best-effort heartbeat в backend при idle/busy переходах;
- `local_process` оставлен только как явный режим для тестов и локальной отладки.
- в `compose.yml` worker получает доступ к Docker daemon через `/var/run/docker.sock`, чтобы запускать одноразовые game runtime containers.

Builder:
- `POST /internal/builds/start` — orchestration endpoint builder-service.
- builder-service в текущем MVP:
  - создает build job в backend (`/api/v1/internal/builds/start`);
  - вычисляет deterministic `image_digest` для game source;
  - валидирует backend lifecycle payload (`build_id`, `status`, `image_digest`) на шагах start/finished;
  - завершает build в backend (`/api/v1/internal/builds/{buildId}/finished`);
  - при ошибке best-effort отправляет `/failed`.
- в compose `builder-service` получает `BACKEND_API_URL=http://backend-api:8000/api/v1` и общий `INTERNAL_API_TOKEN`;
- backend для ручного sync game source использует `BUILDER_SERVICE_URL=http://builder-service:8030`.

## Запуск удаленных worker-узлов (горизонтальное масштабирование)

Минимальные env для удаленного worker:
- `SCHEDULER_URL` — публичный адрес scheduler-service;
- `BACKEND_API_URL` — публичный адрес backend API (`/api/v1`);
- `INTERNAL_API_TOKEN` — общий сервисный токен для backend `/internal/*`;
- `WORKER_ID` — уникальный идентификатор узла;
- `HOSTNAME` — имя узла;
- `MAX_SLOTS` — сколько запусков узел обрабатывает конкурентно;
- `WORKER_LABELS` — JSON-словарь меток, например `{"region":"eu-mow-1","pool":"remote"}`;
- `DOCKER_BINARY`, `DOCKER_IMAGE`, `DOCKER_NETWORK_MODE`, CPU/RAM/PIDs лимиты.

Ожидаемый flow:
1. worker регистрируется в backend (`/internal/workers/register`);
2. scheduler выдает run по lease (`/internal/workers/pull-next`);
3. worker подтверждает `accepted/started/finished` в backend;
4. worker подтверждает завершение lease в scheduler (`/internal/runs/ack-finished`).

Для эксплуатации:
- при выводе узла из ротации сначала прекращайте вызовы `pull-and-execute`, затем дождитесь пустых lease в scheduler;
- мониторьте `GET /api/v1/internal/workers` (backend) и `GET /internal/queue/stats` (scheduler);
- используйте разные `WORKER_LABELS` для разных пулов железа/регионов.

## End-to-end smoke via compose

```bash
bash scripts/run_compose_e2e_smoke.sh
```

Полезные опции:
- `--no-build`
- `--timeout 60`
- `--project-name my-local-e2e`
- `--keep-up`

## Локальные тесты сервисов

```bash
cd services/scheduler && pytest -q
cd services/worker && pytest -q
cd services/builder && pytest -q

# или единым прогоном из корня репозитория:
pytest -q services/scheduler/tests services/worker/tests services/builder/tests
```
