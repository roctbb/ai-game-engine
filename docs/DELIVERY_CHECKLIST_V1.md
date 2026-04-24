# Delivery Checklist (v1)

Документ фиксирует текущий уровень готовности реализации относительно `docs/SYSTEM_SPEC_V2.md`.

## 1. Архитектура и стек

- [x] Backend: FastAPI + DDD bounded contexts (`backend/src/*`).
- [x] Frontend: Vue 3 SPA + Bootstrap 5 (`frontend/`).
- [x] Хранение: PostgreSQL (schema/Alembic в `backend/alembic`) + Redis в execution plane.
- [x] Alembic initial schema синхронизирован с ORM-таблицами (`competition`, `spectator_replay`, `administration`, `training_lobby` columns).
- [x] Планировщик/воркер/билдер вынесены в отдельные сервисы (`services/`).
- [x] Scheduler поддерживает label-aware назначение run (`required_worker_labels` + `worker_labels`).
- [x] Worker применяет fail-fast валидацию `execution-context` и не использует stub-fallback для неподдерживаемых `run_kind`/`code_api_mode`.
- [x] Internal run lifecycle поддерживает явный шаг `accepted` (`POST /internal/runs/{run_id}/accepted`), а `started` идемпотентен для того же worker.
- [x] Builder применяет fail-fast валидацию backend lifecycle payload (`build_id`, `status`, `image_digest`) и делает best-effort `/failed` при ошибке.

## 2. Каталог игр и метаданные

- [x] Игры и версии (`/games`, `/games/{id}/versions`, activate).
- [x] Универсальный patch игры (`PATCH /games/{id}`) для title + catalog metadata.
- [x] Read-only API каталога игр (`/games/{id}/versions/{versionId}`, `/games/{id}/topics`, `/games/{id}/templates`).
- [x] Валидация совместимости slot schema при смене версии.
- [x] `single_task` metadata lifecycle: `draft|ready|archived`.
- [x] Публичный каталог `single_task` показывает только `ready`.

## 3. Команды, код и snapshot

- [x] Команды и слоты (`/teams`, `/teams/{id}/slots/{slot}`).
- [x] Workspace как canonical source of truth для кода.
- [x] Snapshot freeze при `created -> queued`.
- [x] Snapshot boundary при нескольких `Run` одной команды покрыт регрессией (`backend/tests/test_run_snapshot_freeze.py`).
- [x] Snapshot boundary для сценария "одна команда в нескольких лобби" покрыт регрессией (`backend/tests/test_run_snapshot_freeze.py`).
- [x] Запрет `input()` и поддержка `print` в `script_based` задачах.

## 4. Лобби и соревнования

- [x] Training lobbies: join/leave/ready/matchmaking.
- [x] Lifecycle лобби: `open/paused/closed` + `updating`.
- [x] `switch-version` в training-лобби останавливает активные `training_match` run (переводит в `canceled`) перед revalidate/swap.
- [x] Отмены run выставляют диагностические причины (`canceled_by_game_update`, `manual_moderation_ban`, `manual_cancel`, `manual_stop_single_task`) в `error_message`.
- [x] Контракт reason-code для `error_message` формализован в `SYSTEM_SPEC_V2` (раздел `19.2.1`).
- [x] Соревнования: register/start/advance/pause/finish.
- [x] PATCH и read-view endpoint'ы соревнований (`/competitions/{id}`, `/bracket`, `/rounds`, `/matches`).
- [x] Multi-team матчи и `top-k` продвижение.
- [x] Tie-break flow (`awaiting_tiebreak` + manual resolve).
- [x] Бан entrant во время соревнования прерывает активные `competition_match` запуски команды (через `cancel_run`).
- [x] UI-страницы списка/создания: `/lobbies`, `/competitions`.
- [x] UI-редактирование `draft`-соревнования (title/tie-break/match_size/top-k) на странице `/competitions/:competitionId`.
- [x] UI run-таблицы лобби и соревнования показывают причину отмены единообразно (human label + raw reason code).
- [x] UI single-task страниц (`/tasks/:gameId/run`, `/tasks/:gameId/attempts`) также показывает reason-code отмен единообразно.
- [x] `MatchWatchPage` показывает reason-code отмены в metadata/result блоках тем же единым паттерном.

## 5. Безопасность и роли

- [x] Dev-login + GeekClass auth.
- [x] RBAC на mutation endpoints каталога, лобби, соревнований.
- [x] RBAC на antiplagiarism warnings (`teacher/admin`).
- [x] Участнические действия лобби требуют активную сессию.
- [x] Game source sync применяет policy-check артефактов builder (`build_id`, `image_digest`) и fail-safe переводит sync в `failed` при некорректном ответе.
- [x] Валидация `repo_url` для game sources запрещает credentials/query/fragment.

## 6. Игра-движки, renderer и SVG

- [x] Встроенные примеры всех режимов:
  - `maze_escape_v1`, `coins_right_down_v1`, `tower_defense_v1`,
  - `ttt_connect5_v1`,
  - `tanks_ctf_v1`.
- [x] Renderer-контракт `postMessage` и replay payload.
- [x] Графика примеров в формате SVG.
- [x] Миграция legacy-игр и фиксация статуса в `docs/GAME_MIGRATION_STATUS_V1.md`.
- [x] Legacy `tanks` стабилизирован под Python 3.12: map/player регрессии закрыты тестами (`test_tanks_legacy_domain.py`, `test_tanks_legacy_maps.py`).

## 7. Тестирование и smoke

- [x] Backend + services тесты проходят стабильно.
- [x] SSE run-stream покрыт terminal-сценариями для `finished` и `canceled` (`backend/tests/test_run_stream_api.py`).
- [x] Frontend build проходит.
- [x] Distributed smoke script актуализирован под RBAC и current API:
  - `scripts/e2e_distributed_smoke.py`.
- [x] Базовый CI workflow добавлен (`.github/workflows/ci-v2.yml`) и использует `scripts/verify_v2.sh`.
- [x] Полный локальный `verify_v2 --with-compose-smoke` подтвержден после очистки Docker cache (24.04.2026).

## 8. Операционный контур

- [x] Регулярный distributed compose-smoke автоматизирован workflow `compose-smoke-v2`:
  - файл: `.github/workflows/compose-smoke-v2.yml`;
  - триггеры: `schedule` (каждые 6 часов), `workflow_dispatch`, `push` в `main`.
- [x] Runbook для deployment/rollback опубликован: `docs/OPERATIONS_RUNBOOK_V1.md`.
- [x] Runbook дополнен быстрым разбором `canceled/timeout` (reason-code + stream/replay checklist).
