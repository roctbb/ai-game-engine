# Масштабирование через удаленные Game Workers (v1)

Документ фиксирует практический контур масштабирования platform v2 за счет вынесения `game-worker` на отдельные серверы.

## 1. Цель

Обеспечить горизонтальное масштабирование исполнения запусков (`Run`) без переноса backend/scheduler на те же хосты.

Модель:
- backend API и scheduler остаются в control-plane;
- исполнение матчей и задач масштабируется за счет независимых worker-нод;
- каждая worker-нода запускает sandbox-контейнеры для engine execution.

## 2. Базовый протокол (как работает)

1. worker регистрируется в backend: `POST /api/v1/internal/workers/register`.
2. worker запрашивает задачи у scheduler: `POST /internal/workers/pull-next`.
3. scheduler выдает `Run` с lease (TTL контролируется scheduler).
   - если у `Run` заданы `required_worker_labels`, задача выдается только совместимому worker.
4. worker фиксирует прием запуска в backend: `POST /api/v1/internal/runs/{runId}/accepted`.
5. worker запускает игровой engine в sandbox (docker runner).
6. worker отправляет `started/finished/failed` в backend.
7. worker отправляет `ack-finished` в scheduler.

Обязательные свойства:
- stale `ack` не должен закрывать run;
- истекшие lease возвращаются в очередь;
- snapshot run фиксируется до постановки в очередь (`created -> queued`).
- для `draining/disabled/offline` worker не берет новые задачи (`pull-and-execute` возвращает `paused`).

## 3. Минимальные env для удаленного worker

- `SCHEDULER_URL` — адрес scheduler-service.
- `BACKEND_API_URL` — адрес backend (`.../api/v1`).
- `INTERNAL_API_TOKEN` — сервисный токен для backend `/internal/*`.
- `WORKER_ID` — уникальный ID узла.
- `HOSTNAME` — имя/алиас узла.
- `MAX_SLOTS` — емкость worker.
- `WORKER_LABELS` — JSON с метками (например, `{"region":"eu-mow-1","pool":"gpu"}`).
- `EXECUTION_MODE=docker`
- `DOCKER_BINARY=docker`
- лимиты sandbox: `DOCKER_CPU_LIMIT`, `DOCKER_MEMORY_LIMIT`, `DOCKER_PIDS_LIMIT`, `DOCKER_TMPFS_SIZE`.

## 4. Пример запуска worker на отдельном сервере

```bash
docker run -d --name agp-worker-remote-1 \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e SCHEDULER_URL=http://scheduler.example.internal:8010 \
  -e BACKEND_API_URL=http://backend.example.internal:8000/api/v1 \
  -e INTERNAL_API_TOKEN='<shared-internal-token>' \
  -e WORKER_ID=worker-remote-1 \
  -e HOSTNAME=worker-remote-1 \
  -e MAX_SLOTS=4 \
  -e WORKER_LABELS='{"region":"eu-mow-1","pool":"remote"}' \
  -e EXECUTION_MODE=docker \
  -e DOCKER_NETWORK_MODE=none \
  -e DOCKER_CPU_LIMIT=1.0 \
  -e DOCKER_MEMORY_LIMIT=256m \
  -e DOCKER_PIDS_LIMIT=128 \
  -e DOCKER_TMPFS_SIZE=64m \
  ghcr.io/your-org/ai-game-worker:latest
```

## 5. Наблюдаемость и контроль

Проверки:
- backend: `GET /api/v1/internal/workers`;
- scheduler: `GET /internal/queue/stats`.

Что мониторить:
- количество `known` run и глубину очереди;
- число активных lease по worker;
- долю `failed/timeout` run;
- latency от `queued` до `started`.
- долю `paused` ответов у worker-loop (обычно означает `draining/disabled/offline`).

Управление статусом worker:
- `PATCH /api/v1/workers/{workerId}/status` с `online|offline|draining|disabled` (только admin, `X-Session-Id`).

## 6. Операционные процедуры

### 6.1 Добавление новой ноды

1. Поднять worker с новым `WORKER_ID`.
2. Убедиться, что нода появилась в `/api/v1/internal/workers`.
3. Проверить, что scheduler выдает lease этой ноде.

### 6.2 Безопасное выключение ноды

1. Остановить внешний cron/оркестратор, который вызывает `pull-and-execute`.
   Альтернатива: сначала выставить `status=draining` через API, дождаться опустошения lease, затем остановить cron.
2. Дождаться, пока у ноды не останется активных lease (по `queue/stats`).
3. Остановить контейнер worker.

### 6.3 Аварийное падение ноды

Ожидаемое поведение:
- scheduler дождется истечения lease;
- зависшие run вернутся в очередь;
- другие воркеры подберут их повторно.

## 7. Security baseline для удаленных worker

Минимально обязательно:
- network segmentation между control-plane и worker-нодами;
- backend/scheduler должны быть доступны только из доверенного контура;
- TLS и mTLS/закрытый внутренний ingress на уровне инфраструктуры;
- sandbox-контейнеры запускаются с ограничениями (`read-only`, tmpfs, pids, cpu, memory, `--network none`);
- отдельный контур логов и аудит действий worker.

## 8. Статус текущего MVP

- label-aware scheduling реализован:
  - `scheduler-service` хранит `required_worker_labels` для `Run`;
  - `game-worker` отправляет `worker_labels` в `pull-next`;
  - `Run` назначается только на воркер с совместимыми метками (exact-match по ключам requirements).
- worker heartbeat в backend реализован как best-effort (не блокирует выполнение run при сетевых проблемах).
- autoscaling policy (HPA) не входит в MVP и настраивается внешним оркестратором.
