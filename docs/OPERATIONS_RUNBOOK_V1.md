# Operations Runbook (v1)

Короткий runbook для локального и стендового запуска платформы `v2`.

## 1) Поднять стек

```bash
docker compose -f compose.yml up --build
```

Ключевые endpoint'ы:
- Backend API: `http://localhost:8000/api/v1/health`
- Scheduler: `http://localhost:8010/health`
- Worker: `http://localhost:8020/health`
- Builder: `http://localhost:8030/health`
- Frontend: `http://localhost:8080`

## 2) Проверка готовности

Минимальные проверки:

```bash
curl -fsS http://localhost:8000/api/v1/health
curl -fsS http://localhost:8010/health
curl -fsS http://localhost:8020/health
curl -fsS http://localhost:8030/health
```

Полный smoke:

```bash
python scripts/e2e_distributed_smoke.py
```

Единый verify (tests + build + smoke-syntax):

```bash
bash scripts/verify_v2.sh
```

С включением compose-smoke (поднимает `compose.yml`, запускает `e2e_distributed_smoke.py`, затем останавливает стек):

```bash
bash scripts/verify_v2.sh --with-compose-smoke
```

Или оркестрированный compose-smoke:

```bash
bash scripts/run_compose_e2e_smoke.sh
```

Регулярный автоматический smoke:
- GitHub Actions workflow: `.github/workflows/compose-smoke-v2.yml`
- расписание: каждые 6 часов;
- дополнительные триггеры: `workflow_dispatch` и `push` в `main`.

## 3) Базовые операционные действия

### Пауза/возобновление/остановка лобби

- Пауза: `POST /api/v1/lobbies/{lobbyId}/status {"status":"paused"}`
- Возобновление: `POST /api/v1/lobbies/{lobbyId}/status {"status":"open"}`
- Остановка без удаления: `POST /api/v1/lobbies/{lobbyId}/status {"status":"stopped"}`
- Полное удаление лобби и training-match run/replay: `DELETE /api/v1/lobbies/{lobbyId}`

Важно:
- операции доступны только `teacher/admin` (`X-Session-Id`);
- при `stopped` активные training run отменяются, команды снимаются с `ready`, лобби можно снова открыть через `open`;
- `DELETE` запрещен, если к лобби прикреплено активное или ожидающее ручного завершения соревнование.

### Изоляция проблемного worker

```bash
curl -X PATCH http://localhost:8000/api/v1/workers/{workerId}/status \
  -H 'Content-Type: application/json' \
  -H 'X-Session-Id: <teacher/admin session>' \
  -d '{"status":"disabled"}'
```

Проверить очередь:

```bash
curl -fsS http://localhost:8010/internal/queue/stats
```

### Возврат worker в пул

```bash
curl -X PATCH http://localhost:8000/api/v1/workers/{workerId}/status \
  -H 'Content-Type: application/json' \
  -H 'X-Session-Id: <teacher/admin session>' \
  -d '{"status":"online"}'
```

## 4) Диагностика

- Run stream: `GET /api/v1/runs/{runId}/stream`
- Lobby stream: `GET /api/v1/lobbies/{lobbyId}/stream`
- Competition stream: `GET /api/v1/competitions/{competitionId}/stream`
- Replay run: `GET /api/v1/replays/runs/{runId}`

### Быстрый разбор `canceled/timeout`

1. Получить состояние run:

```bash
curl -fsS http://localhost:8000/api/v1/runs/<run_id>
```

2. Для `status="canceled"` проверить `error_message` (reason-code):
- `manual_cancel`
- `manual_stop_single_task`
- `manual_moderation_ban`
- `canceled_by_game_update`

3. Для `status="timeout"` проверить последние события и terminal envelope:

```bash
curl -N "http://localhost:8000/api/v1/runs/<run_id>/stream?poll_interval_ms=250"
```

4. Проверить наличие replay для пост-мортема:

```bash
curl -fsS http://localhost:8000/api/v1/replays/runs/<run_id>
```

5. Если run завис в `queued/running` дольше SLA:
- проверить scheduler queue stats (`/internal/queue/stats`);
- проверить статус worker (`online|draining|disabled|offline`);
- при необходимости перевести проблемный worker в `disabled`, дождаться перераспределения и вернуть в `online`.

### Частая причина падения compose-smoke

Если `postgres` падает на старте с `No space left on device`:

```bash
docker system df
docker system prune -af
docker volume prune -f
```

После очистки повторить:

```bash
bash scripts/run_compose_e2e_smoke.sh
```

## 5) Rollback (базовый)

Если новая версия игры/изменение вызывает сбои:

1. Поставить затронутые training-лобби в `paused`.
2. Переключить игру на предыдущую стабильную `GameVersion` (`/games/{id}/activate`).
3. Проверить совместимость слотов и `ready`-состояния команд.
4. Выполнить smoke (`scripts/e2e_distributed_smoke.py`) по затронутым режимам.
5. Вернуть лобби в `open`.

## 6) Ограничения текущего уровня

- Автоматический rollback и canary rollout не автоматизированы.
- Политики alerting/monitoring задаются внешней инфраструктурой (Prometheus/Grafana/ELK и т.д.).
