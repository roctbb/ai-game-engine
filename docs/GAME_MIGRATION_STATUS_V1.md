# Статус миграции игр на API v2

Документ фиксирует состояние миграции игровых пакетов из `games/` к контракту платформы `v2`.
Цель: иметь единый source of truth для кодогенерации и последующих доработок.

## 1) Сводка по играм

| Игра | Game Mode | Code API | Manifest v2 | Renderer v2 | Result payload v2 | Регрессии | Статус |
|---|---|---|---|---|---|---|---|
| `maze_escape_v1` | `single_task` | `script_based` | ✅ | ✅ (`renderer/index.html`, SVG) | ✅ | ✅ | ✅ ready |
| `coins_right_down_v1` | `single_task` | `script_based` | ✅ | ✅ (`renderer/index.html`, SVG) | ✅ | ✅ | ✅ ready |
| `tower_defense_v1` | `single_task` | `script_based` | ✅ | ✅ (`renderer/index.html`, SVG) | ✅ | ✅ | ✅ ready |
| `ttt_connect5_v1` | `multiplayer` | `turn_based` | ✅ | ✅ (`renderer/index.html`, SVG preview) | ✅ | ✅ | ✅ ready |
| `tanks_ctf_v1` | `multiplayer` | `turn_based` | ✅ | ✅ (`renderer/index.html`, SVG preview) | ✅ | ✅ | ✅ ready |
| `template_v1` | `multiplayer` | `turn_based` | ✅ | ✅ (`renderer/index.html`, SVG preview) | ✅ (базовый) | ✅ | ✅ ready |

## 2) Checklist миграции (на игру)

Для каждой игры должны быть выполнены пункты:

1. `manifest.yaml` соответствует v2:
   - `id`, `title`, `game_mode`, `semver`, `code_api_mode`,
   - `engine_entrypoint`,
   - `renderer_entrypoint`,
   - `player_instruction`,
   - `description` / `difficulty` / `topics` (для каталога задач и фильтрации),
   - `slots[]`.
2. Движок (`engine.py`) возвращает нормализованный payload:
   - `status`,
   - `metrics` и/или `scores`,
   - `frames[]` и `events[]` для replay-player,
   - детерминированная структура без нестабильных ключей.
3. Renderer доступен по `renderer_entrypoint` и отдает корректную страницу.
4. Для новой графики используются SVG-ассеты по умолчанию.
5. Игра проходит:
   - unit/regression тесты (если есть),
   - backend manifest-loading тесты,
   - distributed smoke (минимум 1 успешный запуск).

## 3) Legacy-игры: детали адаптации

### `tic_tac_toe` → `ttt_connect5_v1`
- Мигрировано:
  - manifest v2;
  - слот `bot` и `turn_based` контракт;
  - `renderer_entrypoint` переведен на `renderer/index.html`;
  - добавлен SVG preview (`renderer/board.svg`).
- Исправления/регрессии:
  - покрыты регрессии по правилу победы (5 в ряд, обе диагонали).

### `tanks` → `tanks_ctf_v1`
- Мигрировано:
  - manifest v2;
  - слоты `driver` (required) и `support` (optional);
  - `renderer_entrypoint` переведен на `renderer/index.html`;
  - добавлен SVG preview (`renderer/arena.svg`).
- Исправления/регрессии:
  - движок приведен к стабильному `turn_based` payload для `training_match`.
  - legacy-domain фиксы:
    - `Game.apply_move` корректно проходит полную дистанцию `speed` и не теряет исходную точку;
    - базовый `Map.init` теперь fail-fast (`NotImplementedError`) вместо молчаливого `pass`;
    - `TankMap` кладет `Coin` в `game.items` (а не в `game.objects`) и ретраит при коллизиях;
    - `BigMap` распределяет команды игроков детерминированно (`Radient/Dare`) и не пропускает игроков при коллизиях;
    - `GeneralPlayer.step` fail-safe обрабатывает нестроковые решения бота (без падения рантайма);
    - удалены устаревшие `imp`-импорты, несовместимые с Python 3.12.
  - добавлены регрессионные тесты:
    - `backend/tests/test_tanks_legacy_domain.py`;
    - `backend/tests/test_tanks_legacy_maps.py`.

### `template` → `template_v1`
- Мигрировано:
  - manifest v2 и базовый `turn_based` контракт.
  - `renderer_entrypoint` переведен на `renderer/index.html`;
  - добавлен SVG preview (`renderer/template.svg`);
  - добавлены регрессионные проверки payload для `training_match` и `competition_match`.

## 4) Что осталось по migration этапу

На текущем этапе критичных незакрытых пунктов миграции по встроенным играм нет.

Дополнительно внедрено:
- все встроенные движки теперь публикуют `frames/events` в result payload;
- для `competition_match` в сценариях ничьей движки (`ttt_connect5_v1`, `tanks_ctf_v1`) выставляют `tie_resolution="explicit_tie"` для совместимости с result contract.
- renderer всех встроенных игр обновлены до интерактивной SVG-отрисовки кадра (`agp.renderer.state.payload.frame`) и итоговых метрик (`agp.renderer.result`).
