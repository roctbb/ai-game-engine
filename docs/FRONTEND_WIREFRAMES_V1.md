# AI Game Platform - wireframes 5 главных экранов (v1)

## 1. Назначение документа
Этот документ описывает wireframe-уровень 5 ключевых экранов платформы и дополняет:
- [docs/SYSTEM_SPEC_V2.md](/Users/roctbb/PycharmProjects/ai-game-engine/docs/SYSTEM_SPEC_V2.md)
- [docs/FRONTEND_VISUAL_BRIEF_V1.md](/Users/roctbb/PycharmProjects/ai-game-engine/docs/FRONTEND_VISUAL_BRIEF_V1.md)

Документ нужен для:
- проектирования Vue 3 SPA;
- сборки page layout;
- проектирования компонентной библиотеки;
- последующей генерации экранов без импровизации в архитектуре UI.

## 2. Какие 5 экранов считаются главными
Для первой полноценной визуальной реализации главными считаются:

1. Каталог задач
2. Рабочее место команды
3. `single_task` run page
4. Тренировочное лобби
5. Соревнование

Именно эти 5 экранов должны стать ядром SPA и определять структуру frontend.

## 3. Общие правила wireframe

### 3.1 Общий shell
Все 5 экранов живут внутри единого `AppShell`:
- `AppSidebar`
- `TopBar`
- `ContentArea`

Desktop:
- sidebar слева;
- top bar сверху;
- основной контент в центре;
- contextual rail справа там, где нужно.

Mobile:
- top bar сверху;
- drawer вместо sidebar;
- bottom navigation;
- длинные страницы разбиваются на stacked sections;
- боковые панели превращаются в tabs, drawers или bottom sheets.

### 3.2 Общее обозначение блоков
В wireframe используются такие обозначения:
- `Header` — главный заголовок страницы
- `Toolbar` — панель быстрых действий
- `Filters` — фильтры/поиск/переключатели
- `Main` — центральное содержимое страницы
- `Rail` — боковая панель
- `Panel` — логический контейнер
- `List` — список карточек/элементов
- `Viewer` — игровая визуализация
- `Editor` — редактор кода

### 3.3 Подход к desktop layout
Для desktop предполагается условная сетка:
- sidebar: 240-280 px
- основной контент: fluid
- right rail: 320-400 px при необходимости

### 3.4 Подход к mobile layout
Для mobile:
- один главный вертикальный поток;
- sticky CTA, если действие критично;
- editor/viewer/логи не должны одновременно пытаться жить в трех колонках.

## 4. Экран 1 - Каталог задач
Маршрут:
- `/tasks`

Цель:
- помочь выбрать задачу;
- показать темы и сложность;
- дать понятную точку входа в обучение;
- показать прогресс и мотивацию.

### 4.1 Desktop wireframe
```text
+--------------------------------------------------------------------------------------+
| TopBar: Хлебные крошки | Заголовок "Задачи" | Search | User actions                  |
+--------------------------------------------------------------------------------------+
| Hero / Intro                                                                       |
| "Изучайте алгоритмы через интерактивные задачи"   [Мои темы] [Решено] [Сложность]   |
+--------------------------------------------------------------------------------------+
| Filters Row                                                                         |
| [Search input________________] [Тема v] [Сложность v] [Статус v] [Сбросить]         |
+--------------------------------------------------------------------------------------+
| Summary Strip                                                                       |
| [Решено задач: 12] [Лучшая серия] [Популярная тема: BFS] [Лидер недели]             |
+---------------------------------------------+----------------------------------------+
| Main Grid                                   | Right Rail                             |
|                                             |                                        |
| [Task Card] [Task Card] [Task Card]         | [Мой прогресс]                         |
| [Task Card] [Task Card] [Task Card]         | - Решено по темам                      |
| [Task Card] [Task Card] [Task Card]         | - Последние попытки                    |
|                                             |                                        |
| Task Card contains:                         | [Топ по решенным задачам]              |
| - title                                     | - user 1                               |
| - short description                         | - user 2                               |
| - theme tags                                | - user 3                               |
| - difficulty                                |                                        |
| - solved stats                              |                                        |
| - CTA: Открыть                              |                                        |
+---------------------------------------------+----------------------------------------+
```

### 4.2 Mobile wireframe
```text
+--------------------------------------------------+
| TopBar: Задачи                                   |
+--------------------------------------------------+
| Hero                                             |
| "Интерактивные задачи по программированию"       |
| [Решено: 12] [Темы: 5]                           |
+--------------------------------------------------+
| Search                                           |
| [__________________________]                     |
+--------------------------------------------------+
| Filter chips                                     |
| [BFS] [DP] [Easy] [Medium] [Сбросить]            |
+--------------------------------------------------+
| Task Card                                        |
| title                                            |
| short description                                |
| tags                                             |
| difficulty | solved count                        |
| [Открыть]                                        |
+--------------------------------------------------+
| Task Card                                        |
+--------------------------------------------------+
| Bottom nav                                       |
+--------------------------------------------------+
```

### 4.3 Главные компоненты
- `TasksPageHeader`
- `TasksHero`
- `TaskFiltersBar`
- `TaskSummaryStrip`
- `TaskCard`
- `TaskProgressRail`

### 4.4 Главное действие страницы
- `Открыть задачу`

### 4.5 Критичные состояния
- нет задач по фильтру;
- задача `draft` и не видна student;
- есть решенные и нерешенные задачи;
- очень длинные descriptions;
- много тем и много filter chips.

## 5. Экран 2 - Рабочее место команды
Маршрут:
- `/teams/:teamId`

Цель:
- управлять слотами/ролями команды;
- редактировать код по слотам;
- понимать состояние кода команды;
- понимать, какие snapshot будут зафиксированы, если новый запуск создать сейчас.

### 5.1 Desktop wireframe
```text
+------------------------------------------------------------------------------------------------+
| TopBar: Команды / Team Name | Game | Version | Code status | [Сохранить] [В лобби]             |
+----------------------------+------------------------------------------------+-------------------+
| Left Slot Rail             | Main Editor Area                               | Right Context Rail |
|                            |                                                |                   |
| Team summary               | Toolbar                                        | [Template panel]  |
| - team name                | [slot name] [Python] [dirty/clean]             | - template info   |
| - game                     | [Сохранить] [Сбросить] [Сравнить]              | - slot guide      |
| - captain                  |                                                |                   |
|                            | Monaco Editor                                  | [Snapshot preview]|
| Slots                      | +-------------------------------------------+   | - last snapshot   |
| [runner    filled]         | |                                           |   | - if run created |
| [defender  dirty]          | |             source code                    |   |   now, snapshots |
| [scout     empty]          | |                                           |   |   will be ...    |
|                            | +-------------------------------------------+   | [Logs / Hints]   |
| Slot status legend         |                                                | - validation msg  |
|                            |                                                | - runtime hints   |
+----------------------------+------------------------------------------------+-------------------+
| Bottom Info Strip                                                                              |
| "Если новый запуск будет создан сейчас, система зафиксирует snapshot: defender@v14, runner@v12"|
+------------------------------------------------------------------------------------------------+
```

### 5.2 Mobile wireframe
```text
+--------------------------------------------------+
| TopBar: Team Name                                |
+--------------------------------------------------+
| Team summary                                     |
| Game | Version | Code status                     |
+--------------------------------------------------+
| Slot tabs                                        |
| [runner] [defender] [scout]                      |
+--------------------------------------------------+
| Slot meta                                        |
| required | filled/dirty/empty/locked | snapshot  |
+--------------------------------------------------+
| Editor toolbar                                   |
| [Сохранить] [Сбросить]                           |
+--------------------------------------------------+
| Monaco Editor                                    |
|                                                  |
|                                                  |
+--------------------------------------------------+
| Bottom sheet tabs                                |
| [Template] [Hints] [Snapshot] [Logs]             |
+--------------------------------------------------+
```

### 5.3 Главные компоненты
- `TeamWorkspaceHeader`
- `TeamSlotRail`
- `TeamSlotCard`
- `CodeEditorPanel`
- `TemplatePanel`
- `SnapshotPreviewPanel`
- `ValidationHintsPanel`

### 5.4 Главное действие страницы
- `Сохранить код`

### 5.5 Критичные состояния
- обязательный слот пуст;
- слот заполнен, но код изменен после последнего snapshot;
- политика соревнования блокирует редактирование;
- команда не может стать `ready`;
- игра обновилась и слот стал несовместимым.

### 5.6 Доменные правила для этого экрана
- `ready` не является статусом слота и не должен так отображаться в slot rail;
- допустимые slot-state в UI: `filled`, `empty`, `dirty`, `locked`, `incompatible`;
- экран не обещает "следующий матч" как глобальный факт, потому что команда может участвовать в нескольких лобби;
- допустима только preview-формулировка: какие snapshot будут созданы, если новый запуск инициировать сейчас.

## 6. Экран 3 - `single_task` run page
Маршрут:
- `/tasks/:gameId/run`

Цель:
- дать участнику полноценное пространство для запуска, наблюдения и улучшения решения.

### 6.0 Source of truth для кода на странице `single_task`
Для `single_task` run page не существует отдельного второго хранилища кода.

Экран `/tasks/:gameId/run` обязан работать поверх canonical workspace той же однослотовой персональной команды пользователя для этой игры:
- source of truth остается `TeamSlotCode`;
- попытка `SingleTaskAttempt` использует snapshot этого canonical кода в момент перехода `created -> queued`;
- встроенный редактор на run page редактирует тот же самый код, что и специализированный workspace команды;
- если у пользователя еще нет персональной однослотовой команды для этой игры, платформа может создать ее автоматически как технический workspace.

Из этого следует:
- run page - это специализированный execution shell над тем же кодовым workspace;
- нельзя проектировать run page как отдельный независимый редактор с собственной моделью хранения.

### 6.1 Desktop wireframe
```text
+------------------------------------------------------------------------------------------------+
| TopBar: Задачи / Maze Escape | Difficulty | Theme tags | [Назад к каталогу]                    |
+------------------------------------------------------+-----------------------------------------+
| Main Viewer                                          | Run Rail                                |
|                                                      |                                         |
| +--------------------------------------------------+ | [Run controls]                          |
| |                                                  | | [Запустить]                            |
| |                GAME VIEWER                       | | [Остановить]                            |
| |                                                  | | [Сбросить шаблон]                      |
| +--------------------------------------------------+ |                                         |
|                                                      | [Current attempt status]                |
|                                                      | - created / running / timeout           |
|                                                      | - duration                              |
|                                                      | - score / success                       |
|                                                      |                                         |
|                                                      | [Result summary]                        |
+------------------------------------------------------+-----------------------------------------+
| Lower Workspace                                                                                    |
+-----------------------------------------------+----------------------------------------------------+
| Editor Area                                   | Right Stack                                         |
|                                               |                                                    |
| Toolbar: [Template] [Сохранить в workspace]   | [Attempt history timeline]                          |
| +-------------------------------------------+ | - attempt #17                                       |
| |                                           | | - attempt #16                                       |
| | Monaco: canonical single-task workspace   | |                                                    |
| |                                           | | [Logs / Events / Metrics tabs]                     |
| +-------------------------------------------+ | - stdout                                            |
|                                               | - sdk events                                        |
|                                               | - ticks / duration                                  |
+-----------------------------------------------+----------------------------------------------------+
```

### 6.2 Mobile wireframe
```text
+--------------------------------------------------+
| TopBar: Maze Escape                              |
+--------------------------------------------------+
| Viewer                                           |
|                                                  |
+--------------------------------------------------+
| Sticky Run CTA                                   |
| [Запустить] [Остановить]                         |
+--------------------------------------------------+
| Result strip                                     |
| status | score | duration                        |
+--------------------------------------------------+
| Tabs                                             |
| [Код] [История] [Логи] [Результат]               |
+--------------------------------------------------+
| Tab content                                      |
| canonical workspace / attempts / logs / result   |
+--------------------------------------------------+
```

### 6.3 Главные компоненты
- `SingleTaskHeader`
- `GameViewerPanel`
- `RunControlsPanel`
- `AttemptStatusCard`
- `AttemptHistoryTimeline`
- `AttemptLogsTabs`
- `SingleTaskWorkspaceEditorPanel`

### 6.4 Главное действие страницы
- `Запустить`

### 6.5 Критичные состояния
- активный запуск уже существует;
- run в `running`;
- run в `timeout`;
- runtime error;
- пустой код;
- viewer error;
- задача без score, но с `success_only`.

### 6.6 Доменные правила для этого экрана
- встроенный редактор здесь редактирует тот же canonical `TeamSlotCode`, а не отдельную копию;
- `Запустить` всегда создает новую попытку из текущего workspace через snapshot в момент `created -> queued`;
- если активная попытка уже существует, запуск блокируется на уровне UX и API.

## 7. Экран 4 - Тренировочное лобби
Маршрут:
- `/lobbies/:lobbyId`

Цель:
- показать состав лобби;
- показать кто готов;
- показать активные матчи;
- дать понятный путь к `ready` и к просмотру матчей.

### 7.1 Desktop wireframe
```text
+------------------------------------------------------------------------------------------------+
| TopBar: Лобби / Tanks Arena #12 | Game version | Mode: training | Status: open | [Поделиться] |
+------------------------------------------------------------------------------------------------+
| Lobby Status Banner                                                                            |
| [OPEN] Teams may join and become ready                                                         |
| [PAUSED] Matchmaking paused, actions limited                                                   |
| [UPDATING] Game version is switching, ready-state revalidation in progress                     |
| [CLOSED] Viewing only                                                                          |
+------------------------------------------------------------------------------------------------+
| Lobby Header                                                                                   |
| Title | game badge | public/private | spectator | max teams | [Join team] [Ready] [Leave]     |
| Action gating depends on lobby status and team validity                                        |
+-----------------------------------------------+------------------------------------------------+
| Teams Panel                                   | Match Panel                                    |
|                                               |                                                |
| Queue summary                                 | Active matches                                 |
| - total teams                                 | [Match card]                                   |
| - ready count                                 | - teams                                        |
| - in match count                              | - state                                        |
|                                               | - watch CTA                                    |
| Team list                                     |                                                |
| [Team row - not_ready]                        | Recent matches                                 |
| [Team row - ready]                            | [Match card]                                   |
| [Team row - blocked]                          | [Match card]                                   |
| [Team row - in_match]                         |                                                |
+-----------------------------------------------+------------------------------------------------+
| Bottom / Secondary panels                                                                        |
+-----------------------------------------------+------------------------------------------------+
| Lobby settings / description                   | Events / activity feed                         |
| - join code                                   | - team joined                                  |
| - matchmaking mode                            | - team became ready                            |
| - current game config                         | - match created                                |
+-----------------------------------------------+------------------------------------------------+
```

### 7.2 Mobile wireframe
```text
+--------------------------------------------------+
| TopBar: Лобби #12                                |
+--------------------------------------------------+
| Status banner                                    |
| OPEN / PAUSED / UPDATING / CLOSED                |
+--------------------------------------------------+
| Lobby summary                                    |
| game | version | mode | spectator                |
+--------------------------------------------------+
| Primary actions                                  |
| [Готов] [Покинуть] [Код доступа]                 |
+--------------------------------------------------+
| Queue stats                                      |
| ready | in match | waiting                       |
+--------------------------------------------------+
| Tabs                                             |
| [Команды] [Матчи] [События] [Настройки]          |
+--------------------------------------------------+
| Tab content                                      |
| team list / match cards / feed / settings        |
+--------------------------------------------------+
```

### 7.3 Главные компоненты
- `LobbyHeader`
- `LobbyStatusBanner`
- `LobbySummaryBar`
- `LobbyTeamRow`
- `LobbyQueueStats`
- `LobbyMatchCard`
- `LobbyEventsFeed`
- `LobbySettingsPanel`

### 7.4 Главное действие страницы
- `Стать ready`

### 7.5 Критичные состояния
- команда не выбрана;
- обязательные слоты пусты;
- команда blocked;
- лобби обновляется после game sync;
- матчмейкинг временно недоступен;
- spectator mode выключен.
- лобби `draft`, `paused`, `updating` или `closed`, и часть действий недоступна.

### 7.6 Доменные правила для этого экрана
- lifecycle-state лобби должен быть видимым всегда, а не только через disabled buttons;
- доступность действий `Join`, `Ready`, `Leave` определяется одновременно статусом лобби и валидностью выбранной команды;
- состояние `updating` должно явно объяснять пользователю, что идет переключение версии игры и повторная валидация `ready`.

## 8. Экран 5 - Соревнование
Маршрут:
- `/competitions/:competitionId`

Цель:
- показать структуру турнира;
- показать progression;
- дать быстрый переход к матчам;
- поддержать модерацию и spectator mode.

### 8.1 Desktop wireframe - bracket-compatible `single_elimination`
```text
+------------------------------------------------------------------------------------------------+
| TopBar: Соревнования / Spring Cup | format | status | version | [Start/Pause] [Export later]   |
+-----------------------------------------------+------------------------------------------------+
| Left/Main Area                                 | Right Rail                                     |
|                                                |                                                |
| Bracket Header                                 | Competition summary                            |
| [Round 1] [Quarter] [Semi] [Final]             | - format                                       |
|                                                | - teams                                        |
| +-------------------------------------------+  | - status                                       |
| | Bracket graph / nodes                      |  | - tie-break policy                            |
| |                                           |  |                                                |
| | [node]---[node]---[node]                  |  | Standings / entrants                           |
| | [node]---[node]---[node]                  |  | [team row]                                     |
| |                                           |  | [team row]                                     |
| +-------------------------------------------+  |                                                |
|                                                | Moderation / warnings                          |
| Round matches list                             | [warning card]                                 |
| [match row]                                    | [warning card]                                 |
| [match row]                                    |                                                |
+-----------------------------------------------+------------------------------------------------+
| Bottom Strip                                                                                   |
| "Клик по узлу сетки открывает матч или side panel"                                             |
+------------------------------------------------------------------------------------------------+
```

### 8.1.1 Wireframe для multi-team elimination node
Если формат соревнования остается elimination, но матч содержит `N > 2` команд или правило продвижения равно `top-k`, бинарный узел сетки использовать нельзя.

В таком случае node обязан выглядеть как match-card внутри сетки:

```text
+--------------------------------------+
| Match #18                            |
| Team A                               |
| Team B                               |
| Team C                               |
| Team D                               |
|--------------------------------------|
| Qualify: top-2                       |
| 1. Team C                            |
| 2. Team A                            |
| Tie-break: manual                    |
+--------------------------------------+
```

Такой node должен явно показывать:
- список всех участников матча;
- правило продвижения;
- фактически прошедшие дальше команды;
- если нужно, наличие tie-break или manual decision.

### 8.1.2 Когда bracket нельзя делать главным представлением
Если elimination-логика не читается естественно как bracket из-за:
- слишком большого числа команд в одном матче;
- `top-k` продвижения;
- частых неоднозначных tie-break;

то `CompetitionPage` должен по умолчанию открываться не в bracket view, а в `Rounds / Matches / Standings` представлении.

Bracket в этом случае может оставаться дополнительным режимом просмотра, но не единственным и не главным.

### 8.2 Desktop wireframe - `round_robin` / `swiss`
```text
+------------------------------------------------------------------------------------------------+
| TopBar: Competition Title                                                                      |
+-----------------------------------------------+------------------------------------------------+
| Main Area                                     | Right Rail                                     |
|                                               |                                                |
| View switch                                   | Summary                                        |
| [Standings] [Rounds] [Matches]                | - status                                       |
|                                               | - format                                       |
| Standings table                               | - teams                                        |
| +-------------------------------------------+ | - current round                                |
| | team | points | wins | losses | place     | |                                                |
| +-------------------------------------------+ | Moderation / warnings                          |
|                                               |                                                |
| Current round matches                         |                                                |
| [match card] [match card] [match card]        |                                                |
+-----------------------------------------------+------------------------------------------------+
```

### 8.3 Mobile wireframe
```text
+--------------------------------------------------+
| TopBar: Spring Cup                               |
+--------------------------------------------------+
| Summary                                          |
| format | status | version                        |
+--------------------------------------------------+
| Tabs                                             |
| [Сетка/Таблица] [Матчи] [Участники] [Warnings]   |
+--------------------------------------------------+
| Tab content                                      |
| bracket / standings / match list / warnings      |
+--------------------------------------------------+
| Sticky action bar for teacher/admin if needed    |
+--------------------------------------------------+
```

### 8.4 Главные компоненты
- `CompetitionHeader`
- `BracketView`
- `BracketNode`
- `MultiTeamBracketNode`
- `CompetitionStandingsTable`
- `CompetitionRoundMatches`
- `CompetitionSummaryRail`
- `SimilarityWarningsPanel`

### 8.5 Главное действие страницы
- `Открыть матч`

### 8.6 Критичные состояния
- турнир еще не стартовал;
- турнир paused из-за `tie_break_policy = manual`;
- есть banned team;
- матч завершен, но результат невалиден;
- есть warnings по схожести;
- часть матчей canceled или aborted.

### 8.7 Доменные правила для этого экрана
- bracket допустим только там, где он не искажает модель соревнования;
- для матчей с `N > 2` командами UI обязан поддерживать multi-team nodes или переключаться на rounds/table view;
- продвижение должно отображаться через реальные `placements` и `advancement_rule`, а не через неявные бинарные предположения frontend.

## 9. Как эти wireframes переводить в Vue-страницы

### 9.1 Рекомендуемое соответствие страницам
- `TasksCatalogPage`
- `TeamWorkspacePage`
- `SingleTaskRunPage`
- `TrainingLobbyPage`
- `CompetitionPage`

### 9.2 Рекомендуемое соответствие widgets/features
- `tasks/catalog-grid`
- `tasks/filters`
- `teams/slot-rail`
- `teams/editor-workspace`
- `attempts/run-controls`
- `attempts/history`
- `lobby/team-list`
- `lobby/match-list`
- `competition/bracket`
- `competition/standings`
- `competition/warnings`

### 9.3 Общий принцип сборки страниц
Сначала собирать:
1. skeleton layout
2. static states
3. loading states
4. empty states
5. populated states
6. realtime updates

Не начинать страницу с "живого API", пока не собрана ее статическая композиция.

## 10. Приоритет реализации
С точки зрения UX и ценности я бы реализовывал эти wireframes в таком порядке:

1. `TeamWorkspacePage`
2. `SingleTaskRunPage`
3. `TrainingLobbyPage`
4. `CompetitionPage`
5. `TasksCatalogPage`

Причина:
- рабочее место команды и экран запуска задачи сильнее всего определяют ощущение платформы;
- лобби и соревнование закрепляют игровой и соревновательный характер;
- каталог проще доделать после стабилизации базовых сущностей и компонентов.

## 11. Инструкция для дальнейшей генерации
При последующей генерации frontend-кода:
- не отходить от этих зон страницы без явной причины;
- держать главный CTA визуально приоритетным;
- не заменять layout таблицей, если wireframe предполагает panel/card composition;
- все 5 экранов делать сначала для desktop и mobile, а не только desktop;
- viewer и editor рассматривать как first-class layout blocks, а не как случайные вложенные widgets.
