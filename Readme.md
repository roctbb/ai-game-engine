# AI-GAME-ENGINE

## Launch engine for product:
- legacy stack removed; use v2 platform stack below

## Launch new platform stack (v2)
- execute `docker compose -f compose.yml up --build`
- backend API: `http://localhost:8000/api/v1/health`
- frontend SPA: `http://localhost:8080`
- лобби (список/создание): `http://localhost:8080/lobbies`
- соревнования (список/создание): `http://localhost:8080/competitions`
- admin game sources page: `http://localhost:8080/admin/game-sources`
- match watch page (пример): `http://localhost:8080/runs/{runId}/watch`
- replay catalog page: `http://localhost:8080/replays`
- replay API (пример): `GET http://localhost:8000/api/v1/replays/runs/{runId}`
- run stream API (SSE): `GET http://localhost:8000/api/v1/runs/{runId}/stream`
- lobby stream API (SSE): `GET http://localhost:8000/api/v1/lobbies/{lobbyId}/stream`
- competition stream API (SSE): `GET http://localhost:8000/api/v1/competitions/{competitionId}/stream`
- scheduler service: `http://localhost:8010/health`
- worker service: `http://localhost:8020/health`
- builder service: `http://localhost:8030/health`
- distributed smoke check: `python scripts/e2e_distributed_smoke.py`
- full compose smoke orchestration: `bash scripts/run_compose_e2e_smoke.sh`
- единый verify script: `bash scripts/verify_v2.sh` (или `--with-smoke` / `--with-compose-smoke`)
- регулярный CI smoke: `.github/workflows/compose-smoke-v2.yml`

## Основное ТЗ для кодогенерации
- См. `docs/SYSTEM_SPEC_V2.md`

## Визуальный дизайн-бриф frontend
- См. `docs/FRONTEND_VISUAL_BRIEF_V1.md`

## Wireframes ключевых экранов
- См. `docs/FRONTEND_WIREFRAMES_V1.md`

## Статус миграции игр на v2
- См. `docs/GAME_MIGRATION_STATUS_V1.md`

## Протокол renderer shell/iframe
- См. `docs/RENDERER_PROTOCOL_V1.md`

## Масштабирование удаленными worker-узлами
- См. `docs/REMOTE_WORKER_SCALING_V1.md`

## Операционный runbook
- См. `docs/OPERATIONS_RUNBOOK_V1.md`

## Чеклист готовности поставки
- См. `docs/DELIVERY_CHECKLIST_V1.md`

## Обзорный документ
- См. `docs/PLATFORM_REQUIREMENTS_V1.md`

## Новый код (каркас реализации)
- Backend FastAPI (DDD): `backend/`
- Frontend Vue 3 + Bootstrap 5 SPA: `frontend/`
- Выделенные сервисы scheduler/worker/builder: `services/`
