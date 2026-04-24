# Renderer Protocol v1 (`shell` ↔ `iframe`)

Документ фиксирует минимальный протокол взаимодействия frontend shell и игрового renderer в `iframe`.
Цель: единообразная интеграция встроенных и git-игр без прямого доступа renderer к auth-токенам.

## 1) Базовые правила

1. Renderer запускается в `iframe` и не получает токены платформы напрямую.
2. Обмен идет только через `window.postMessage`.
3. Все сообщения имеют поле `type` с префиксом `agp.renderer.`.
4. Все входящие/исходящие payload должны быть сериализуемыми в JSON.

## 2) Направление `shell -> iframe`

### `agp.renderer.init`

Отправляется один раз после загрузки iframe.

```json
{
  "type": "agp.renderer.init",
  "payload": {
    "gameId": "game_...",
    "gameSlug": "ttt_connect5_v1",
    "mode": "training",
    "runId": "run_..."
  }
}
```

### `agp.renderer.state`

Отправляется при каждом обновлении состояния матча/задачи.

```json
{
  "type": "agp.renderer.state",
  "payload": {
    "tick": 42,
    "phase": "running",
    "frame": { "any": "json-state" }
  }
}
```

### `agp.renderer.result`

Отправляется в терминальном состоянии.

```json
{
  "type": "agp.renderer.result",
  "payload": {
    "status": "finished",
    "scores": { "teamA": 1, "teamB": 0 },
    "metrics": { "duration_ms": 1234 }
  }
}
```

## 3) Направление `iframe -> shell`

### `agp.renderer.ready`

Renderer сообщает, что готов принимать `state`.

```json
{
  "type": "agp.renderer.ready",
  "payload": {
    "version": "1.0.0"
  }
}
```

### `agp.renderer.event`

Опциональные UI-события renderer (например, выбор узла карты).

```json
{
  "type": "agp.renderer.event",
  "payload": {
    "name": "cell.click",
    "data": { "x": 3, "y": 2 }
  }
}
```

### `agp.renderer.error`

Ошибки от renderer, не прерывающие shell.

```json
{
  "type": "agp.renderer.error",
  "payload": {
    "message": "Cannot parse frame payload"
  }
}
```

## 4) Минимальный JS-шаблон renderer

```javascript
window.parent.postMessage({ type: "agp.renderer.ready", payload: { version: "1.0.0" } }, "*");

window.addEventListener("message", (event) => {
  const message = event.data;
  if (!message || typeof message !== "object") return;
  if (message.type === "agp.renderer.state") {
    // render state
  } else if (message.type === "agp.renderer.result") {
    // render final result
  }
});
```

## 5) Рекомендованный контракт `frame` для встроенных игр

### `maze_escape_v1`

```json
{
  "position": { "x": 0, "y": 0 },
  "invalid_moves": 0,
  "steps": 0,
  "reached_exit": false,
  "score": 0
}
```

### `coins_right_down_v1`

```json
{
  "position": { "x": 0, "y": 0 },
  "coins_left": 6,
  "coins_collected": 0,
  "invalid_moves": 0,
  "reached_goal": false,
  "score": 0
}
```

### `tower_defense_v1`

```json
{
  "base_hp": 30,
  "budget": 15,
  "towers": [0, 0, 0],
  "enemies": [{ "lane": 1, "position": 4, "hp": 3 }],
  "enemies_destroyed": 2,
  "leaks": 1,
  "score": 12
}
```

### `ttt_connect5_v1`

```json
{
  "board": [[0, 1], [0, -1]],
  "turns_played": 7,
  "winner_role": 1,
  "next_role": -1,
  "draw": false
}
```

### `tanks_ctf_v1`

```json
{
  "player": { "x": 1, "y": 3 },
  "enemy": { "x": 7, "y": 3 },
  "flag": { "x": 4, "y": 3, "carrier": "none" },
  "boost_cooldown": 0,
  "winner": "none"
}
```

### `template_v1`

```json
{
  "turn": 2,
  "value": 3,
  "action": "inc"
}
```

## 6) Версионирование

1. При несовместимом изменении типов сообщений увеличивается версия протокола (например, `v2`).
2. Для MVP все встроенные renderer'ы считаются совместимыми с `v1`.
3. Актуальная версия встроенных renderer-компонентов после интерактивного обновления: `1.1.0`.
