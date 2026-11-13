<template>
  <section class="agp-grid lobby-page" :class="{ 'lobby-page--game': activeTab === 'game', 'lobby-page--workspace': activeTab === 'code', 'lobby-page--field': lobbyMobilePane === 'field' }">
    <header v-if="activeTab === 'code'" class="arena-lobby-workbar"><button class="agp-back-link" aria-label="К лобби" @click="activeTab = 'lobby'"><AppIcon name="back" /></button><h1>{{ lobby?.title }}</h1><span class="small text-muted">{{ isSavingCode ? 'Сохраняем…' : isDirty ? 'Черновик' : formatTime(activeSlot?.updated_at) }}</span><button class="btn btn-outline-secondary" :aria-pressed="rulesOpen" @click="toggleEditorReference">Условие</button><button v-if="showStopAction" class="btn btn-outline-danger" :disabled="!canStop || isBusy" @click="stop">Выйти из очереди</button><button v-else class="btn btn-primary" :disabled="!canPlay || isBusy" @click="play">В очередь</button></header>
    <header v-else-if="activeTab === 'game'" class="arena-live-workbar">
      <button class="agp-back-link" aria-label="К лобби" @click="activeTab = 'lobby'"><AppIcon name="back" /></button>
      <h1>{{ lobby?.title || 'Трансляция' }}</h1>
      <div v-if="currentReplayChoices.length" class="arena-live-switcher">
        <button class="btn btn-outline-secondary" aria-label="Предыдущий текущий матч" :disabled="currentReplayChoices.length < 2" @click="stepCurrentMatch(-1)">←</button>
        <select class="form-select" aria-label="Текущий матч" :value="displayedGameRunId" @change="selectReplayChoice(($event.target as HTMLSelectElement).value)"><option v-for="choice in currentReplayChoices" :key="choice.run_id" :value="choice.run_id">{{ choice.label }} · {{ participantCountLabel(choice.player_count) }}</option></select>
        <button class="btn btn-outline-secondary" aria-label="Следующий текущий матч" :disabled="currentReplayChoices.length < 2" @click="stepCurrentMatch(1)">→</button>
      </div>
      <span v-else class="small text-muted">Ожидание следующего матча</span>
      <button class="btn btn-outline-secondary arena-live-players" @click="liveStatsOpen = true">Участники</button>
      <button v-if="activeCompetition?.broadcast && selectedCompetitionRunId" class="btn btn-primary" @click="selectedCompetitionRunId = ''; router.replace({ query: { ...route.query, match: undefined } })">К показу</button>
      <RouterLink v-if="displayedGameRunId" class="btn btn-sm btn-outline-secondary" :to="{ name: 'run-watch', params: { runId: displayedGameRunId }, query: { back: route.fullPath } }">Разобрать</RouterLink>
    </header>
    <header v-else class="lobby-overview-head">
      <div>
        <h1>{{ lobby?.title || 'Лобби' }}</h1>
        <p v-if="lobby">{{ game?.title }} · {{ participantCountLabel(lobby.teams.length) }} · {{ lobby.teams.filter(team => team.online).length }} онлайн</p>
      </div>
      <div v-if="lobby && !joinRequired" class="lobby-overview-actions">
        <button v-if="canSeeCodeTab && !canManage" class="btn btn-outline-secondary" @click="activeTab = 'code'">Мой код</button>
        <button v-if="canManage" class="btn btn-outline-secondary" :aria-expanded="inviteOpen" @click="inviteOpen = !inviteOpen">Пригласить</button>
        <button v-if="canManage && !activeCompetition" class="btn btn-primary" :disabled="isBusy" aria-label="Начать соревнование" @click="showCompetitionDialog = true"><span class="lobby-label-wide">Создать соревнование</span><span class="lobby-label-compact">Создать турнир</span></button>
        <button v-if="hasPlayerInLobby && showPlayAction" class="btn" :class="canManage ? 'btn-outline-secondary' : 'btn-primary'" :disabled="!canPlay || isBusy" @click="play">Готов к игре</button>
        <button v-if="hasPlayerInLobby && showStopAction" class="btn btn-outline-secondary" :disabled="!canStop || isBusy" @click="stop">Снять готовность</button>
        <ActionMenu v-if="canManage || canLeaveAsPlayer" label="Действия лобби" :items="lobbyMenuItems" @select="handleLobbyMenu" />
      </div>
    </header>

    <section v-if="inviteOpen && lobby && !['code', 'game'].includes(activeTab)" class="agp-card lobby-invite" aria-label="Приглашение">
      <span>{{ lobby.access === 'code' ? 'По коду' : 'Открытое лобби' }}</span>
      <input :value="inviteUrl" class="form-control" readonly aria-label="Ссылка на лобби" @focus="($event.target as HTMLInputElement).select()" />
      <button class="btn btn-outline-secondary" @click="copyInvite">{{ inviteCopied ? 'Скопировано' : 'Копировать' }}</button>
      <button class="lobby-dialog-close" aria-label="Закрыть приглашение" @click="inviteOpen = false"><AppIcon name="close" /></button>
    </section>

    <nav v-if="activeTab === 'code'" class="arena-lobby-mobile-tabs" aria-label="Рабочая панель"><button :aria-pressed="lobbyMobilePane === 'code'" @click="lobbyMobilePane = 'code'">Код</button><button :aria-pressed="lobbyMobilePane === 'field'" @click="lobbyMobilePane = 'field'">Поле</button></nav>
    <article v-if="queueExpired" class="agp-card p-3 arena-queue-notice" role="status"><span>Вы вышли из очереди после 10 минут офлайн.</span><button class="btn btn-outline-primary" :disabled="!canPlay || isBusy" @click="play">Снова готов</button></article>
    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <LoadingSkeleton v-if="isLoading" :count="activeTab === 'code' ? 2 : 3" :layout="activeTab === 'code' ? 'workspace' : 'list'" :style="activeTab === 'code' ? { '--agp-skeleton-workspace-columns': '52fr 48fr' } : undefined" label="Загрузка лобби…" />

    <article v-else-if="joinRequired" class="agp-card p-4 lobby-access-card">
      <div>
        <h2 class="h6 mb-1">Нужен код входа</h2>
        <p class="small text-muted mb-0">Введите код, который дал преподаватель.</p>
      </div>
      <div class="lobby-access-form">
        <input
          v-model.trim="lobbyAccessCode"
          class="form-control"
          autocomplete="off"
          autofocus
          @keyup.enter="submitLobbyAccessCode"
        />
        <button class="btn btn-dark" :disabled="!lobbyAccessCode || isBusy" @click="submitLobbyAccessCode">
          {{ isBusy ? 'Проверяем...' : 'Войти' }}
        </button>
      </div>
    </article>

    <template v-else-if="lobby">
      <article v-if="activeCompetition && !['code', 'game'].includes(activeTab)" class="agp-card lobby-competition-banner">
        <div>
          <strong>{{ cleanCompetitionTitle(activeCompetition.title) }}</strong>
          <div class="small text-muted">
            {{ competitionBannerText }}
          </div>
        </div>
        <RouterLink class="btn btn-sm btn-primary" :to="`/competitions/${activeCompetition.competition_id}`">Открыть турнир</RouterLink>
      </article>
      <div v-else-if="!['code', 'game'].includes(activeTab) && hasPlayerInLobby && showStopAction" class="lobby-queue-banner" role="status">
        <SnakeLoader :label="readyStatusLabel" /><button v-if="bannerMatchRunId" class="btn btn-sm btn-outline-secondary" @click="openCurrentMatch(bannerMatchRunId)">Смотреть</button>
      </div>
      <div v-else-if="!['code', 'game'].includes(activeTab) && canManage && canStartLobby" class="lobby-pause-banner">
        <span>Новые матчи на паузе</span>
        <button class="btn btn-sm btn-outline-secondary" :disabled="isBusy" @click="startLobbyByTeacher">Возобновить подбор</button>
      </div>

      <nav v-if="!['code', 'game'].includes(activeTab)" class="lobby-overview-tabs" aria-label="Разделы лобби">
        <button :aria-current="activeTab === 'lobby' ? 'page' : undefined" @click="activeTab = 'lobby'">Игры</button>
        <button aria-label="Участники и таблица" :aria-current="activeTab === 'participants' ? 'page' : undefined" @click="activeTab = 'participants'"><span class="lobby-label-wide">Участники и таблица</span><span class="lobby-label-compact">Участники</span></button>
        <button aria-label="Условие и правила" :aria-current="activeTab === 'rules' ? 'page' : undefined" @click="activeTab = 'rules'"><span class="lobby-label-wide">Условие и правила</span><span class="lobby-label-compact">Правила</span></button>
        <button :aria-current="activeTab === 'archive' ? 'page' : undefined" @click="activeTab = 'archive'">Архив · {{ competitionArchive.length }}</button>
      </nav>

      <Teleport to="body">
        <div v-if="showCompetitionDialog" class="lobby-modal-backdrop" @click.self="showCompetitionDialog = false">
          <article class="lobby-competition-dialog" v-dialog-focus="() => showCompetitionDialog = false" role="dialog" aria-modal="true" aria-labelledby="competition-dialog-title">
            <header class="lobby-dialog-head">
              <div>
                <h2 id="competition-dialog-title" class="h5 mb-0">Начать соревнование</h2>

              </div>
              <button
                class="lobby-dialog-close"
                type="button"
                aria-label="Закрыть"
                :disabled="isBusy"
                @click="showCompetitionDialog = false"
              >
                <AppIcon name="close" />
              </button>
            </header>

            <fieldset class="arena-roster-picker"><legend>Участники</legend><label><input v-model="competitionRosterMode" type="radio" value="queue" />Все в очереди · {{ lobby.teams.filter(t => t.ready).length }}</label><label><input v-model="competitionRosterMode" type="radio" value="selected" />Выбрать игроков</label><div v-if="competitionRosterMode === 'selected'"><button class="btn btn-sm btn-outline-secondary" type="button" @click="competitionSelectedTeams = lobby.teams.map(t => t.team_id)">Выбрать всех</button><label v-for="player in lobby.teams" :key="player.team_id"><input v-model="competitionSelectedTeams" type="checkbox" :value="player.team_id" />{{ teamLabel(player.team_id) }}<span class="text-muted">{{ player.is_bot ? 'Бот' : player.online ? 'Онлайн' : 'Офлайн' }}</span></label></div></fieldset>
            <div class="lobby-competition-settings-grid">
              <label class="lobby-competition-setting">
                <span>{{ competitionMatchSizeLabel }}</span>
                <input
                  v-model.number="competitionMatchSize"
                  class="form-control form-control-sm"
                  type="number"
                  :min="competitionMinMatchSize"
                  :max="competitionMaxMatchSize"
                  :disabled="competitionMatchSizeFixed"
                />
                <small class="text-muted">{{ competitionMatchSizeHint }}</small>
              </label>
              <label class="lobby-competition-setting">
                <span>Проходят</span>
                <input
                  v-model.number="competitionAdvanceTopK"
                  class="form-control form-control-sm"
                  type="number"
                  min="1"
                  :max="competitionMatchSize"
                />
              </label>
              <label class="lobby-competition-setting lobby-competition-setting--wide">
                <span>Показ матчей</span>
                <select v-model="competitionPresentationMode" class="form-select form-select-sm">
                  <option value="sequential">Матчи по очереди</option>
                  <option value="instant">Сразу результаты</option>
                </select>
              </label>
              <label class="lobby-competition-setting lobby-competition-setting--wide">
                <span>При ничьей</span>
                <select v-model="competitionTieBreakPolicy" class="form-select form-select-sm">
                  <option value="manual">Ручное решение</option>
                  <option value="shared_advancement">Пропустить всех с равным результатом</option>
                  <option v-if="game?.slug === 'ttt_connect5_v1'" value="replay_then_shared">До 3 партий, затем проходят оба</option>
                </select>
              </label>
              <label class="lobby-competition-setting lobby-competition-setting--wide">
                <span>Код</span>
                <select v-model="competitionCodePolicy" class="form-select form-select-sm">
                  <option value="locked_on_start">Заблокировать на старте</option>
                  <option value="allowed_between_matches">Разрешить между матчами</option>
                  <option value="locked_on_registration">Заблокировать при регистрации</option>
                </select>
              </label>
            </div>

            <footer class="lobby-dialog-actions">
              <button class="btn btn-outline-secondary" type="button" :disabled="isBusy" @click="showCompetitionDialog = false">
                Отмена
              </button>
              <button
                class="btn btn-dark"
                type="button"
                :disabled="isBusy || Boolean(activeCompetition) || (competitionRosterMode === 'queue' ? lobby.teams.filter(t => t.ready).length : competitionSelectedTeams.length) < competitionMinMatchSize"
                @click="startCompetitionFromLobby"
              >
                {{ isBusy ? 'Запускаем...' : 'Начать соревнование' }}
              </button>
            </footer>
          </article>
        </div>
      </Teleport>

      <Teleport to="body">
        <div v-if="showLobbySettingsDialog" class="lobby-modal-backdrop" @click.self="showLobbySettingsDialog = false">
          <article class="lobby-settings-dialog" v-dialog-focus="() => showLobbySettingsDialog = false" role="dialog" aria-modal="true" aria-labelledby="lobby-settings-dialog-title">
            <header class="lobby-dialog-head">
              <div>
                <h2 id="lobby-settings-dialog-title" class="h5 mb-0">Настройки лобби</h2>
              </div>
              <button
                class="lobby-dialog-close"
                type="button"
                aria-label="Закрыть"
                :disabled="isSavingLobbySettings"
                @click="showLobbySettingsDialog = false"
              >
                <AppIcon name="close" />
              </button>
            </header>

            <div class="lobby-settings-grid">
              <label class="lobby-competition-setting lobby-competition-setting--wide">
                <span>Название</span>
                <input
                  v-model.trim="lobbySettingsTitle"
                  class="form-control form-control-sm"
                  maxlength="120"
                  @input="lobbySettingsTouched = true"
                />
              </label>
              <label class="lobby-competition-setting">
                <span>Доступ</span>
                <select
                  v-model="lobbySettingsAccess"
                  class="form-select form-select-sm"
                  @change="lobbySettingsTouched = true"
                >
                  <option value="public">Открытое</option>
                  <option value="code">По коду</option>
                </select>
              </label>
              <label class="lobby-competition-setting">
                <span>Лимит игроков</span>
                <input
                  v-model.trim="lobbySettingsMaxTeams"
                  class="form-control form-control-sm mono"
                  type="number"
                  min="1"
                  max="512"
                  @input="lobbySettingsTouched = true"
                />
              </label>
              <label v-if="lobbySettingsAccess === 'code'" class="lobby-competition-setting lobby-competition-setting--wide">
                <span>Код входа</span>
                <input
                  v-model.trim="lobbySettingsAccessCode"
                  class="form-control form-control-sm mono"
                  maxlength="120"
                  :placeholder="lobby?.access === 'code' ? 'оставить текущий код' : 'код для входа'"
                  @input="lobbySettingsTouched = true"
                />
              </label>
            </div>

            <footer class="lobby-dialog-actions">
              <button class="btn btn-outline-secondary" type="button" :disabled="isSavingLobbySettings" @click="showLobbySettingsDialog = false">
                Закрыть
              </button>
              <button class="btn btn-primary" type="button" :disabled="!canSaveLobbySettings" @click="saveLobbySettings">
                {{ isSavingLobbySettings ? 'Сохраняем...' : 'Сохранить' }}
              </button>
            </footer>
          </article>
        </div>
      </Teleport>

      <Teleport to="body">
        <div v-if="showPlayerCodeDialog" class="lobby-modal-backdrop" @click.self="closePlayerCodeDialog">
          <article class="lobby-player-code-dialog" v-dialog-focus="closePlayerCodeDialog" role="dialog" aria-modal="true" aria-labelledby="player-code-dialog-title">
            <header class="lobby-dialog-head">
              <div>
                <h2 id="player-code-dialog-title" class="h5 mb-1">Код игрока</h2>
                <p class="small text-muted mb-0">{{ selectedCodePlayerName }}</p>
              </div>
              <button
                class="lobby-dialog-close"
                type="button"
                aria-label="Закрыть"
                :disabled="isSavingCode"
                @click="closePlayerCodeDialog"
              >
                <AppIcon name="close" />
              </button>
            </header>

            <div v-if="workspace" class="lobby-code-layout lobby-code-layout--modal">
              <aside class="agp-card p-3 lobby-roles">
                <div class="lobby-roles-head">
                  <div>
                    <strong>{{ selectedCodePlayerName }}</strong>
                    <span>{{ filledRequiredSlots }}/{{ requiredSlotCount }} обязательных</span>
                  </div>
                  <div class="lobby-role-progress" aria-hidden="true">
                    <i :style="{ width: `${roleProgressPercent}%` }"></i>
                  </div>
                </div>
                <button
                  v-for="slot in slotStates"
                  :key="slot.slot_key"
                  class="lobby-role-button"
                  :class="{ active: activeSlotKey === slot.slot_key, filled: Boolean(slot.code?.trim()), required: slot.required }"
                  @click="selectSlot(slot.slot_key)"
                >
                  <span>
                    <i aria-hidden="true"></i>
                    {{ slot.slot_key }}
                  </span>
                  <small>{{ slot.code?.trim() ? 'заполнено' : slot.required ? 'нужно заполнить' : 'необязательная' }}</small>
                </button>
              </aside>

              <article class="agp-card p-3 lobby-editor">
                <div class="lobby-editor-toolbar">
                  <div>
                    <h3 class="h6 mb-1">{{ activeSlotKey || 'Код' }}</h3>
                    <p class="small mb-0">{{ codeStateLabel }}</p>
                  </div>
                  <span class="small text-muted">Только чтение</span>
                </div>
                <CodeEditor :model-value="editorCode" readonly />
              </article>
            </div>
            <div v-else class="agp-loading-state agp-loading-state--compact">Загрузка кода...</div>
          </article>
        </div>
      </Teleport>

      <section v-if="canSeeCodeTab && workspace" v-show="activeTab === 'code'" class="lobby-code-layout" :class="{ 'lobby-code-layout--single-slot': slotStates.length === 1 }">
        <aside class="agp-card p-3 lobby-roles">
          <div class="lobby-roles-head">
            <div>
              <strong>{{ selectedCodePlayerName }}</strong>
              <span>{{ filledRequiredSlots }}/{{ requiredSlotCount }} обязательных</span>
            </div>
            <div class="lobby-role-progress" aria-hidden="true">
              <i :style="{ width: `${roleProgressPercent}%` }"></i>
            </div>
          </div>
          <button
            v-for="slot in slotStates"
            :key="slot.slot_key"
            class="lobby-role-button"
            :class="{ active: activeSlotKey === slot.slot_key, filled: Boolean(slot.code?.trim()), required: slot.required }"
            @click="selectSlot(slot.slot_key)"
          >
            <span>
              <i aria-hidden="true"></i>
              {{ slot.slot_key }}
            </span>
            <small>{{ slot.code?.trim() ? 'заполнено' : slot.required ? 'нужно заполнить' : 'необязательная' }}</small>
          </button>
          <RouterLink
            v-if="docs?.links.length"
            class="btn btn-sm btn-outline-secondary mt-3 w-100"
            :to="{
              name: 'game-docs',
              params: { gameId: lobby.game_id },
              query: { from: 'lobby', lobby_id: lobby.lobby_id },
            }"
            target="_blank"
            rel="noopener noreferrer"
          >
            Документация
          </RouterLink>
        </aside>

        <article class="agp-card p-3 lobby-editor">
          <div class="lobby-editor-toolbar arena-lobby-editor-head"><select v-if="slotStates.length > 1" :value="activeSlotKey" class="form-select form-select-sm" aria-label="Файл бота" @change="selectSlot(($event.target as HTMLSelectElement).value)"><option v-for="slot in slotStates" :key="slot.slot_key" :value="slot.slot_key">{{ slot.slot_key }}</option></select><strong v-else>strategy.py</strong><details class="arena-file-menu"><summary aria-label="Меню файла">⋯</summary><div><button :disabled="!activeTemplate || !canEditSelectedCode" @click="applyTemplate">Вставить шаблон</button><button v-if="replacementUndo !== null" @click="undoCodeReplacement">Отменить замену</button><button v-if="canUseDemoStrategy" :disabled="!activeDemoStrategy || !canEditSelectedCode" @click="applyDemoStrategy">Пример стратегии</button><button :disabled="!canSaveCode" @click="saveCode">Сохранить</button></div></details></div>
          <CodeEditor v-model="editorCode" :readonly="activeTab !== 'code' || !activeSlotKey || !canEditSelectedCode" @run="play" />
        </article>
      </section>
      <section v-if="canSeeCodeTab && !workspace" v-show="activeTab === 'code'" class="agp-card p-4 lobby-code-empty">
        <h2 class="h5 mb-2">Код пока недоступен</h2>
        <p class="text-muted mb-0">
          Рабочее место появится после присоединения к лобби как игрок.
        </p>
      </section>

      <section v-if="activeTab === 'rules'" class="agp-card p-4">
        <h2>{{ game?.title }}</h2>
        <template v-if="docs?.links.some(link => link.content)">
          <MarkdownContent v-for="(link, index) in docs.links.filter(link => link.content)" :key="link.path" :source="index === 0 ? link.content!.replace(/^# [^\n]+\n+/, '') : link.content!" />
        </template>
        <MarkdownContent v-else :source="docs?.player_instruction || game?.description || ''" />
      </section>
      <section v-show="activeTab === 'lobby'" class="lobby-games">
        <section class="lobby-current-games" aria-labelledby="lobby-current-title">
          <header class="lobby-list-heading">
            <h2 id="lobby-current-title">{{ activeCompetition ? 'Матчи текущего раунда' : 'Сейчас идут' }} <span class="lobby-section-count">{{ currentReplayChoices.length }}</span></h2>
            <div class="lobby-list-filters">
              <button v-if="canManage && !activeCompetition && canPauseLobby" class="btn btn-sm btn-outline-secondary" :disabled="isBusy" @click="pauseLobbyByTeacher">Пауза подбора</button>
              <button v-if="currentReplayChoices.length" class="btn btn-sm btn-outline-secondary" @click="openCurrentMatch()">Смотреть</button>
            </div>
          </header>
          <div v-if="currentReplayChoices.length" class="agp-card lobby-live-list">
            <article v-for="choice in currentReplayChoices" :key="choice.run_id" class="lobby-live-row">
              <div><strong>{{ choice.label }}</strong><span v-if="choice.player_count <= 5" class="small text-muted">{{ participantCountLabel(choice.player_count) }}</span></div>
              <span class="lobby-live-names">{{ choice.player_count <= 5 ? choice.meta : participantCountLabel(choice.player_count) }}</span>
              <button class="btn btn-sm btn-outline-secondary" :aria-label="'Смотреть ' + choice.label.toLowerCase()" @click="openCurrentMatch(choice.run_id)">Смотреть</button>
            </article>
          </div>
          <div v-else class="agp-card lobby-live-empty">Ⅱ {{ activeCompetition ? 'Ожидание раунда' : 'Сейчас матчей нет' }}</div>
        </section>
        <section v-if="queuedDuelGroups.length" class="lobby-queued-duels" aria-label="Дуэли в очереди">
          <header class="lobby-list-heading"><h2>Дуэли в очереди <span class="lobby-section-count">{{ queuedDuelGroups.length }}</span></h2></header>
          <div class="agp-card lobby-live-list">
            <article v-for="group in queuedDuelGroups" :key="group.group_id" class="lobby-live-row">
              <div><strong>Дуэль</strong><span class="small text-muted">В очереди</span></div>
              <span class="lobby-live-names">{{ group.runs.map(run => teamLabel(run.team_id)).join(' · ') }}</span>
              <RouterLink class="btn btn-sm btn-outline-secondary" :to="{ name: 'run-watch', params: { runId: primaryRunId(group) }, query: { back: route.fullPath } }">Смотреть</RouterLink>
            </article>
          </div>
        </section>
        <header class="lobby-list-heading lobby-history-heading">
          <h2>{{ canManage ? 'История игр' : 'Мои прошедшие игры' }} <span class="lobby-section-count">{{ filteredTrainingMatchGroups.length }}</span></h2>
        </header>
        <div class="lobby-history-toolbar">
          <input v-model="matchSearch" class="form-control form-control-sm" type="search" aria-label="Поиск по истории игр" placeholder="Участник или время" />
          <label v-if="canManage" class="visually-hidden" for="lobby-match-player">Матчи участника</label>
          <select v-if="canManage" id="lobby-match-player" v-model="matchPlayerFilter" class="form-select form-select-sm">
            <option value="">Все участники</option>
            <option v-for="stat in lobbyLeaderboard" :key="stat.team_id" :value="stat.team_id">{{ teamLabel(stat.team_id) }}</option>
          </select>
          <details class="lobby-history-dates"><summary class="btn btn-sm btn-outline-secondary">Даты<span v-if="matchDateFrom || matchDateTo" aria-label="Фильтр дат включён"> ·</span></summary><div><label>С<input v-model="matchDateFrom" type="date" class="form-control form-control-sm" aria-label="История игр с даты" /></label><label>По<input v-model="matchDateTo" type="date" class="form-control form-control-sm" aria-label="История игр по дату" /></label></div></details>
          <label class="lobby-check"><input v-model="onlyProblemMatches" type="checkbox" /> С ошибками</label>
          <button v-if="matchSearch || matchPlayerFilter || matchDateFrom || matchDateTo || onlyProblemMatches" class="btn btn-sm btn-outline-secondary" @click="resetHistoryFilters">Сбросить</button>
        </div>
        <div class="agp-card lobby-game-list">
          <article v-for="group in pagedTrainingMatchGroups" :key="group.group_id" class="lobby-game-entry">
            <div class="lobby-game-row" :class="{ 'lobby-game-row--own': !canManage && lobby.my_team_id }">
              <div class="lobby-game-identity">
                <div><strong>Матч</strong><span v-if="trainingMatchHasError(group)" class="agp-pill agp-pill--danger">С ошибкой</span></div>
                <time>{{ formatMatchDate(group) }}</time>
              </div>
              <div class="lobby-game-result">
                <span>{{ trainingMatchSummary(group) }}</span>
                <button class="lobby-text-action" :aria-expanded="expandedMatches.has(group.group_id)" @click="toggleMatchRoster(group.group_id)">{{ participantCountLabel(matchGroupTeamIds(group).length) }} <span aria-hidden="true">{{ expandedMatches.has(group.group_id) ? '▴' : '▾' }}</span></button>
              </div>
              <strong v-if="!canManage && lobby.my_team_id" class="lobby-own-result">{{ trainingOwnResult(group) }}</strong>
              <RouterLink class="btn btn-sm btn-outline-secondary lobby-game-watch" :to="{ name: 'run-watch', params: { runId: primaryRunId(group) }, query: { back: route.fullPath } }">Разобрать</RouterLink>
            </div>
            <div v-if="expandedMatches.has(group.group_id)" class="lobby-game-expanded">
              <table class="table mb-0">
                <thead><tr><th>Участник</th><th class="text-end">Очки</th></tr></thead>
                <tbody><tr v-for="teamId in matchGroupTeamIds(group)" :key="teamId" :class="{ 'lobby-table-self': teamId === lobby.my_team_id }"><td>{{ teamLabel(teamId) }}<span v-if="teamId === lobby.my_team_id" class="text-muted"> · вы</span><span v-if="matchPlayerIsVisibleWinner(group, teamId)" class="text-success" aria-label="Победитель"> ✓</span></td><td class="text-end font-monospace">{{ shouldHideMatchWinner(group) ? '—' : matchPlayerScoreLabel(group, teamId) || '—' }}</td></tr></tbody>
              </table>
            </div>
          </article>
          <div v-if="!filteredTrainingMatchGroups.length" class="agp-empty-state agp-empty-state--compact">{{ trainingMatchSections.history.length ? 'По выбранным фильтрам игр нет.' : 'Прошедших игр пока нет.' }}</div>
          <footer v-if="matchPageCount > 1" class="lobby-match-pagination">
            <button class="btn btn-sm btn-outline-secondary" :disabled="matchPage === 1" @click="matchPage -= 1">Назад</button>
            <span class="small text-muted">Страница {{ matchPage }} из {{ matchPageCount }}</span>
            <button class="btn btn-sm btn-outline-secondary" :disabled="matchPage === matchPageCount" @click="matchPage += 1">Вперёд</button>
          </footer>
        </div>
      </section>

      <section v-if="activeTab === 'participants'" class="agp-card lobby-participants">
        <header class="lobby-list-heading">
          <div><h2>Участники тренировки</h2><p>{{ lobby.teams.filter(team => team.online).length }} онлайн · {{ lobby.teams.filter(team => team.ready).length }} в очереди</p></div>
          <div class="lobby-list-filters">
            <input v-model="playerSearch" class="form-control form-control-sm" type="search" aria-label="Найти участника" placeholder="Найти участника" />
            <select v-model="participantSort" class="form-select form-select-sm" aria-label="Сортировка участников">
              <option value="score">По среднему счёту</option>
              <option value="name">По имени</option>
            </select>
            <label class="lobby-check"><input v-model="onlyQueuedPlayers" type="checkbox" /> В очереди</label>
            <ActionMenu v-if="canUseAdminBots" compact label="Действия с участниками" :items="[{ id: 'add-bot', label: 'Добавить бота', disabled: isBusy || !canAddBot }]" @select="addDemoBot" />
          </div>
        </header>
        <table class="table align-middle mb-0 lobby-participant-table">
          <thead><tr><th scope="col" class="lobby-participant-place">Место</th><th>Участник</th><th>Присутствие</th><th>Очередь</th><th class="text-end">Победы</th><th class="text-end">Ничьи</th><th class="text-end">Поражения</th><th class="text-end">Игры</th><th class="text-end">Средний счёт</th><th v-if="canManage || canDuel"></th></tr></thead>
          <tbody>
            <tr v-for="stat in filteredLeaderboard" :key="stat.team_id" :class="{ 'lobby-table-self': stat.team_id === lobby.my_team_id, 'lobby-participant-row--duel': canDuel && stat.team_id !== lobby.my_team_id }">
              <td class="lobby-participant-place" :aria-label="stat.place === null ? 'Место не определено' : 'Место ' + stat.place">{{ stat.place ?? '—' }}</td>
              <td class="lobby-participant-identity"><button v-if="canManage" class="lobby-text-action lobby-participant-name" @click="showPlayerMatches(stat.team_id)">{{ teamLabel(stat.team_id) }}</button><span v-else>{{ teamLabel(stat.team_id) }}</span><span v-if="stat.team_id === lobby.my_team_id" class="small text-muted"> · вы</span></td>
              <td class="lobby-participant-presence">{{ participantPresence(stat.team_id) }}</td>
              <td class="lobby-participant-queue"><span class="agp-pill" :class="participantQueueTone(stat.team_id)">{{ participantQueueLabel(stat.team_id) }}</span></td>
              <td class="text-end lobby-stat-cell" data-label="Победы">{{ stat.wins }}</td>
              <td class="text-end lobby-stat-cell" data-label="Ничьи" :title="outcomeCountHint(stat)">{{ outcomeCountLabel(stat, 'draws') }}</td>
              <td class="text-end lobby-stat-cell" data-label="Поражения" :title="outcomeCountHint(stat)">{{ outcomeCountLabel(stat, 'losses') }}</td>
              <td class="text-end lobby-stat-cell" data-label="Игры">{{ stat.matches_total }}</td><td class="text-end lobby-stat-cell" data-label="Средний счёт">{{ stat.matches_total ? averageScoreLabel(stat.average_score) : '—' }}</td>
              <td v-if="canManage || canDuel" class="lobby-participant-actions" :class="{ 'lobby-participant-actions--duel': canDuel && stat.team_id !== lobby.my_team_id }"><div class="d-flex gap-2 justify-content-end"><button v-if="canDuel && stat.team_id !== lobby.my_team_id" class="btn btn-sm btn-outline-secondary" :disabled="isBusy" @click="startDuel(stat.team_id)">{{ duelOpponent === stat.team_id ? 'Запуск…' : 'Дуэль' }}</button><ActionMenu v-if="canManage" compact :label="'Действия участника ' + teamLabel(stat.team_id)" :items="participantActions(stat)" @select="handleParticipantAction($event, stat)" /></div></td>
            </tr>
          </tbody>
        </table>
        <div v-if="!filteredLeaderboard.length" class="agp-empty-state agp-empty-state--compact">{{ lobby.teams.length ? 'Участники не найдены.' : 'Участников пока нет.' }}</div>
      </section>

      <section v-if="activeTab === 'game' || activeTab === 'code'" class="lobby-game-layout">
        <article class="lobby-game-view"><GameReference v-if="editorReferenceVisible" :title="game?.title || ''" :description="game?.description" :instruction="docs?.player_instruction" :template="activeTemplate" :docs="docs" :frame="{}" :is-actual="false" @close="closeEditorReference" />
          <iframe
            v-if="displayedGameRunId" v-show="!editorReferenceVisible"
            :key="displayedGameWatchUrl"
            :src="displayedGameWatchUrl"
            title="Текущая игра"
          ></iframe>
          <div v-if="!editorReferenceVisible && replayFinishedInViewer" class="lobby-game-finished-overlay">
            <div class="lobby-game-finished-card">
              <strong>Игра завершена</strong>
              <span>{{ currentGameIsDraw ? 'Ничья' : 'Победитель: ' + currentGameWinnerLabel }}</span>
              <small>Ожидайте следующей игры</small>
            </div>
          </div>
          <div v-if="!displayedGameRunId && !editorReferenceVisible" class="lobby-empty">
            <SnakeLoader v-if="lobby.my_status === 'queued'" label="Подбираем матч" /><h2 v-else class="h6">Ⅱ {{ activeCompetition ? 'Ожидаем раунд' : 'Матч ещё не начался' }}</h2>
          </div>
        </article>
        <aside v-if="activeTab === 'game'" class="agp-card lobby-live-stats">
          <header><h2>Участники · {{ currentGameStats.length }}</h2><span class="small text-muted">{{ currentGamePhaseLabel }}</span></header>
          <LiveMatchScoreboard :players="currentGameStats" />
        </aside>
      </section>

      <Teleport to="body"><div v-if="liveStatsOpen" class="lobby-modal-backdrop" @click.self="liveStatsOpen = false"><section class="lobby-settings-dialog" role="dialog" aria-modal="true" aria-label="Участники матча" v-dialog-focus="() => liveStatsOpen = false"><header class="lobby-dialog-head"><h2 class="h6 mb-0">Участники матча</h2><button class="lobby-dialog-close" aria-label="Закрыть участников" @click="liveStatsOpen = false"><AppIcon name="close" /></button></header><LiveMatchScoreboard :players="currentGameStats" /></section></div></Teleport>

      <section v-show="activeTab === 'archive'" class="agp-card p-3 lobby-archive">
        <h2 class="h6 mb-3">Архив соревнований</h2>
        <div v-if="!competitionArchive.length" class="agp-empty-state agp-empty-state--compact">Соревнований пока нет.</div>
        <div class="lobby-match-list">
          <RouterLink
            v-for="item in competitionArchive"
            :key="item.competition_id"
            class="lobby-match-row"
            :to="`/competitions/${item.competition_id}`"
          >
            <span>
              <strong>{{ cleanCompetitionTitle(item.title) }}</strong><small class="text-muted">{{ formatTime(item.created_at) }} · {{ item.participant_count }} игроков</small>
              <small class="text-muted">
                {{ item.winner_team_ids.length > 1 ? 'Победители' : 'Победитель' }}: {{ archiveCompetitionWinnerLabel(item) }}
              </small>
            </span>
            <strong>{{ competitionStatusLabel(item.status) }}</strong>
          </RouterLink>
        </div>
      </section>

    </template>
  </section>
</template>

<script setup lang="ts">
import { isMatchDraw, matchScoreLabel } from '../lib/matchOutcome';
import { sortLobbyParticipants, type LobbyParticipantSort } from '../lib/lobbyLeaderboard';
import { matchesHistoryQuery, splitTrainingMatches } from '../lib/lobbyHistory';
import ActionMenu, { type ActionMenuItem } from "../components/ActionMenu.vue";
import AppIcon from '../components/AppIcon.vue';
import { statusPillClass } from '../lib/statusTone';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';

import { formatTime } from '../lib/attemptPresentation';
import { ownTrainingEditorRun, ownCompetitionEditorRun, ownCurrentMatchRun } from '../lib/lobbyEditorRun';
import SnakeLoader from '../components/SnakeLoader.vue';
import LiveMatchScoreboard from '../components/LiveMatchScoreboard.vue';
import GameReference from '../components/GameReference.vue';
import MarkdownContent from '../components/MarkdownContent.vue';
import CodeEditor from '../components/CodeEditor.vue';
import {
  addLobbyDemoBot,
  deleteLobby,
  getGame,
  getGameDocs,
  getGameTemplates,
  getLobby,
  getWorkspace,
  joinLobby,
  joinLobbyAsUser,
  leaveLobby,
  listCompetitions,
  listCompetitionRuns,
  listLobbyCompetitionArchive,
  listRuns,
  playLobby,
  createLobbyDuel,
  setLobbyReady,
  setLobbyStatus,
  startLobbyCompetition,
  stopLobby,
  updateLobby,
  updateSlotCode,
  updateSlotCodeKeepalive,
  type CompetitionCodePolicy,
  type CompetitionDto,
  type CompetitionMatchDto,
  type CompetitionMatchStatus,
  type CompetitionRoundStatus,
  type CompetitionRunItemDto,
  type CompetitionStatus,
  type GameDocumentationDto,
  type GameDto,
  type GameTemplatesDto,
  type LobbyCompetitionDto,
  type LobbyAccess,
  type LobbyDto,
  type LobbyMatchGroupDto,
  type LobbyParticipantStatsDto,
  type RunDto,
  type SlotStateDto,
  type StreamEnvelopeDto,
  type TeamWorkspaceDto,
  type TieBreakPolicy,
} from '../lib/api';
import { createResilientSSE } from '../lib/resilientSSE';
import { useSessionStore } from '../stores/session';

interface TrainingRunLink {
  run_id: string;
  team_id: string;
}

interface TrainingMatchGroup {
  group_id: string;
  batch_id: string;
  archived: boolean;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  replay_frame_count: number;
  replay_frame_index: number;
  winner_team_ids: string[];
  scores_by_team: Record<string, number>;
  runs: TrainingRunLink[];
}

interface CurrentGameStatRow {
  run_id: string;
  team_id: string;
  display_name: string;
  status: string;
  score: string;
  scoreValue: number | null;
  lifePercent: number;
  shieldPercent: number;
  meta: string;
  isSelf: boolean;
}

interface EmbeddedGamePlayerStat {
  id: string;
  name: string;
  team_id: string;
  score: number | null;
  score_label: string;
  life_percent: number;
  shield_percent: number;
  alive: boolean;
  is_self: boolean;
  detail_label: string;
}

interface EmbeddedGameFrame {
  runId: string;
  status: RunDto['status'];
  tick: number;
  phase: string;
  frame: unknown;
  replayFrameIndex: number;
  replayFrameCount: number;
  firstShowActive: boolean;
  firstShowWaiting: boolean;
  participants: Array<{
    run_id: string;
    team_id: string;
    display_name: string;
    captain_user_id: string;
    is_current: boolean;
  }>;
  players: EmbeddedGamePlayerStat[];
}

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();

const lobby = ref<LobbyDto | null>(null);
const game = ref<GameDto | null>(null);
const workspace = ref<TeamWorkspaceDto | null>(null);
const templates = ref<GameTemplatesDto | null>(null);
const docs = ref<GameDocumentationDto | null>(null);
const activeCompetition = ref<CompetitionDto | null>(null);
const competitionRuns = ref<CompetitionRunItemDto[]>([]);
const trainingRuns = ref<RunDto[]>([]);
const competitionArchive = ref<LobbyCompetitionDto[]>([]);
type LobbyTab = 'code' | 'lobby' | 'participants' | 'game' | 'competition' | 'archive' | 'rules';
function routeTab(): LobbyTab { const tab = String(route.query.tab || 'lobby'); return ['code','lobby','participants','game','competition','archive','rules'].includes(tab) ? tab as LobbyTab : 'lobby'; }
const activeTab = ref<LobbyTab>(routeTab());
watch(() => route.query.tab, () => { activeTab.value = routeTab(); });
const activeSlotKey = ref('');
const queueExpired = computed(() => lobby.value?.teams.find(team => team.team_id === lobby.value?.my_team_id)?.blocker_reason?.includes('10 минут') ?? false);
const rulesOpen = ref(false);
const editorReferenceOpenedAutomatically = ref(false);
const editorReferenceVisible = computed(() => activeTab.value === 'code' && rulesOpen.value);
function toggleEditorReference(): void {
  editorReferenceOpenedAutomatically.value = false;
  const mobileCodePane = window.matchMedia('(max-width: 900px)').matches && lobbyMobilePane.value === 'code';
  rulesOpen.value = mobileCodePane || !rulesOpen.value;
  lobbyMobilePane.value = 'field';
}
function closeEditorReference(): void {
  editorReferenceOpenedAutomatically.value = false;
  rulesOpen.value = false;
}
const lobbyMobilePane = ref<'code' | 'field'>('code');
const liveStatsOpen = ref(false);
const competitionRosterMode = ref<'queue' | 'selected'>('queue');
const competitionSelectedTeams = ref<string[]>([]);
const editorCode = ref('');
const replacementUndo = ref<string | null>(null);
function undoCodeReplacement(): void { if (replacementUndo.value !== null) { editorCode.value = replacementUndo.value; replacementUndo.value = null; } }
const savedCode = ref('');
const selectedCodeTeamId = ref('');
const isHydratingEditor = ref(false);
const isLoading = ref(false);
const isBusy = ref(false);
const isSavingCode = ref(false);
const isSavingLobbySettings = ref(false);
const errorMessage = ref('');
const joinRequired = ref(false);
const lobbyAccessCode = ref('');
const lobbySettingsTitle = ref('');
const lobbySettingsAccess = ref<LobbyAccess>('public');
const lobbySettingsAccessCode = ref('');
const lobbySettingsMaxTeams = ref('');
const lobbySettingsTouched = ref(false);
const competitionMatchSize = ref(2);
const competitionAdvanceTopK = ref(1);
const competitionTieBreakPolicy = ref<TieBreakPolicy>('manual');
watch(() => game.value?.slug, slug => { competitionTieBreakPolicy.value = slug === 'ttt_connect5_v1' ? 'replay_then_shared' : 'manual'; });
const competitionCodePolicy = ref<CompetitionCodePolicy>('locked_on_start');
const competitionPresentationMode = ref<'instant' | 'sequential'>('sequential');
const lastGameRunId = ref('');
const selectedTrainingRunId = ref('');
const selectedCompetitionRunId = ref('');
const displayedGameWatchUrl = ref('');
const displayedGameWatchKey = ref('');
function updateHistoryQuery(values: Record<string, string | undefined>, resetPage = true): void {
  void router.replace({ query: { ...route.query, ...(resetPage ? { page: undefined } : {}), ...values } });
}
function historyTextQuery(key: string) {
  return computed({ get: () => typeof route.query[key] === 'string' ? route.query[key] as string : '',
    set: (value: string) => updateHistoryQuery({ [key]: value || undefined }) });
}
const matchPage = computed({ get: () => Math.max(1, Number(route.query.page) || 1),
  set: (page: number) => updateHistoryQuery({ page: page > 1 ? String(page) : undefined }, false) });
const matchSearch = historyTextQuery('search');
const matchDateFrom = historyTextQuery('after');
const matchDateTo = historyTextQuery('before');
const matchesPerPage = 8;
const matchPlayerFilter = historyTextQuery('player');
const expandedMatches = ref(new Set<string>());
const inviteOpen = ref(false);
const inviteCopied = ref(false);
const inviteUrl = computed(() => new URL(router.resolve({ name: 'lobby', params: { lobbyId: route.params.lobbyId } }).href, window.location.origin).href);
const onlyProblemMatches = computed({ get: () => route.query.errors === '1', set: (value: boolean) => updateHistoryQuery({ errors: value ? '1' : undefined }) });
const playerSearch = ref('');
const onlyQueuedPlayers = ref(false);
const participantSort = computed<LobbyParticipantSort>({
  get: () => route.query.sort === 'name' ? 'name' : 'score',
  set: sort => { void router.replace({ query: { ...route.query, sort: sort === 'name' ? 'name' : undefined } }); },
});
const filteredLeaderboard = computed(() => lobbyLeaderboard.value.filter(stat =>
  (!onlyQueuedPlayers.value || lobby.value?.queued_team_ids.includes(stat.team_id)) &&
  teamLabel(stat.team_id).toLocaleLowerCase('ru-RU').includes(playerSearch.value.trim().toLocaleLowerCase('ru-RU'))));
const embeddedGameFrame = ref<EmbeddedGameFrame | null>(null);
const showCompetitionDialog = ref(false);
const showPlayerCodeDialog = ref(false);
const showLobbySettingsDialog = ref(false);
const trainingRunsRefreshSignature = ref('');
let isRefreshingTrainingRuns = false;
let pendingTrainingRunsRefresh = false;
let lobbyRefreshSequence = 0;
let competitionRefreshSequence = 0;
let codeAutosaveHandle: ReturnType<typeof setTimeout> | null = null;
let lobbyEventSource: EventSource | null = null;
let pollingHandle: ReturnType<typeof setInterval> | null = null;
let competitionPollingHandle: ReturnType<typeof setInterval> | null = null;
const CODE_DRAFT_STORAGE_PREFIX = 'agp_lobby_code_draft';

const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const canUseAdminBots = computed(() => sessionStore.role === 'admin');
const competitionMinMatchSize = computed(() => game.value?.min_players_per_match ?? 2);
const competitionMaxMatchSize = computed(() => game.value?.max_players_per_match ?? 64);
const competitionMatchSizeFixed = computed(() => competitionMinMatchSize.value === competitionMaxMatchSize.value);
const competitionMatchSizeLabel = computed(() =>
  competitionMatchSizeFixed.value ? 'Размер матча' : 'Максимум в матче',
);
const competitionMatchSizeHint = computed(() => {
  if (competitionMatchSizeFixed.value) return `Задано игрой: ${competitionMaxMatchSize.value}.`;
  return `Игра разрешает от ${competitionMinMatchSize.value} до ${competitionMaxMatchSize.value} игроков.`;
});
const canUseDemoStrategy = computed(() => canManage.value);
const hasPlayerInLobby = computed(() => Boolean(lobby.value?.my_team_id));
const canSeeCodeTab = computed(() => hasPlayerInLobby.value);
const duelOpponent = ref('');
const canDuel = computed(() => Boolean(hasPlayerInLobby.value && game.value && game.value.mode !== 'single_task' &&
  (game.value.min_players_per_match ?? 2) <= 2 && (game.value.max_players_per_match ?? 64) >= 2 &&
  !activeCompetition.value && lobby.value && ['open', 'running'].includes(lobby.value.status)));
async function startDuel(opponent: string): Promise<void> {
  if (!lobby.value || isBusy.value) return;
  isBusy.value = true; duelOpponent.value = opponent; errorMessage.value = '';
  try {
    await flushCodeAutosave();
    const duel = await createLobbyDuel(lobby.value.lobby_id, opponent);
    await router.push({ name: 'run-watch', params: { runId: duel.run_id }, query: { back: route.fullPath } });
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : 'Не удалось начать дуэль'; }
  finally { isBusy.value = false; duelOpponent.value = ''; }
}
function outcomeCountLabel(stat: LobbyParticipantStatsDto, key: 'draws' | 'losses'): string {
  const count = stat[key] ?? 0;
  return stat.outcomes_unknown ? (count ? `≥ ${count}` : '—') : String(count);
}
function outcomeCountHint(stat: LobbyParticipantStatsDto): string | undefined {
  return stat.outcomes_unknown ? `У ${stat.outcomes_unknown} старых матчей исход не сохранился. Показано известное число.` : undefined;
}

const codeWorkspaceTeamId = computed(() => {
  if (canManage.value && selectedCodeTeamId.value) return selectedCodeTeamId.value;
  return lobby.value?.my_team_id ?? '';
});
const selectedCodePlayerName = computed(() => {
  const teamId = codeWorkspaceTeamId.value;
  if (!teamId) return 'Игрок';
  return teamLabel(teamId);
});
const slotStates = computed(() => workspace.value?.slot_states ?? []);
const activeSlot = computed(() => slotStates.value.find((slot) => slot.slot_key === activeSlotKey.value) ?? null);
const requiredSlotStates = computed(() => slotStates.value.filter((slot) => slot.required));
const gameRequiredSlotKeys = computed(
  () => game.value?.versions.find((version) => version.version_id === game.value?.active_version_id)?.required_slot_keys ?? [],
);
const requiredSlotCount = computed(() => requiredSlotStates.value.length);
const filledRequiredSlots = computed(() => requiredSlotStates.value.filter((slot) => Boolean(slot.code?.trim())).length);
const roleProgressPercent = computed(() =>
  requiredSlotCount.value ? Math.round((filledRequiredSlots.value / requiredSlotCount.value) * 100) : 0
);
const isDirty = computed(() => editorCode.value !== savedCode.value);
const activeTemplate = computed(() => templates.value?.templates.find((item) => item.slot_key === activeSlotKey.value)?.code ?? '');
const activeDemoStrategy = computed(
  () => templates.value?.demo_strategies.find((item) => item.slot_key === activeSlotKey.value) ?? null,
);
const canSaveCode = computed(() =>
  Boolean(
    codeWorkspaceTeamId.value &&
      activeSlotKey.value &&
      isDirty.value &&
      !isSavingCode.value &&
      canEditSelectedCode.value,
  ),
);
const canUseTrainingQueue = computed(() =>
  Boolean(lobby.value && ['draft', 'open', 'running'].includes(lobby.value.status) && !activeCompetition.value),
);
const lobbyStatusLabel = computed(() => lobbyStatusText(lobby.value?.status ?? 'open'));
const lobbyStatusPillClass = computed(() => lobbyStatusClass(lobby.value?.status ?? 'open'));
const lobbySettingsPayload = computed(() => {
  const maxTeams = Number(lobbySettingsMaxTeams.value);
  return {
    title: lobbySettingsTitle.value.trim(),
    access: lobbySettingsAccess.value,
    access_code: lobbySettingsAccess.value === 'code' && lobbySettingsAccessCode.value.trim() ? lobbySettingsAccessCode.value.trim() : null,
    max_teams: maxTeams,
  };
});
const lobbySettingsValid = computed(() => {
  const payload = lobbySettingsPayload.value;
  if (payload.title.length < 2) return false;
  if (!Number.isFinite(payload.max_teams) || payload.max_teams < 1 || payload.max_teams > 512) return false;
  if (payload.access === 'code' && lobby.value?.access !== 'code' && !payload.access_code) return false;
  return true;
});
const lobbySettingsChanged = computed(() => {
  const current = lobby.value;
  if (!current) return false;
  const payload = lobbySettingsPayload.value;
  return (
    payload.title !== current.title ||
    payload.access !== current.access ||
    (payload.access === 'code' && payload.access_code !== null) ||
    payload.max_teams !== current.max_teams
  );
});
const canSaveLobbySettings = computed(() =>
  Boolean(canManage.value && lobby.value && lobbySettingsTouched.value && lobbySettingsValid.value && lobbySettingsChanged.value && !isSavingLobbySettings.value),
);
const canPlay = computed(() =>
  Boolean(
    lobby.value?.my_team_id &&
      canUseTrainingQueue.value &&
      lobby.value.my_status !== 'queued' &&
      lobby.value.my_status !== 'playing' &&
      requiredSlotCount.value > 0 &&
      (filledRequiredSlots.value === requiredSlotCount.value || (requiredSlotCount.value === 1 && Boolean(editorCode.value.trim()))),
  ),
);
const canStop = computed(
  () => canUseTrainingQueue.value && (lobby.value?.my_status === 'queued' || lobby.value?.my_status === 'playing'),
);
const showPlayAction = computed(() =>
  canUseTrainingQueue.value && lobby.value?.my_status !== 'queued' && lobby.value?.my_status !== 'playing',
);
const showStopAction = computed(() =>
  canUseTrainingQueue.value && (lobby.value?.my_status === 'queued' || lobby.value?.my_status === 'playing'),
);
const canLeaveAsPlayer = computed(() =>
  Boolean(lobby.value?.my_team_id && !activeCompetition.value && lobby.value.status !== 'closed'),
);
const canStartLobby = computed(() => Boolean(canManage.value && lobby.value && ['paused', 'stopped'].includes(lobby.value.status)));
const canPauseLobby = computed(() => Boolean(canManage.value && lobby.value && ['open', 'running'].includes(lobby.value.status)));
const canStopLobbyByTeacher = computed(() => Boolean(canManage.value && lobby.value?.status === 'paused'));
const canDeleteLobby = computed(() => Boolean(canManage.value && lobby.value?.status === 'stopped'));
const canAddBot = computed(() =>
  Boolean(
    canUseAdminBots.value &&
      lobby.value &&
      !activeCompetition.value &&
      ['draft', 'open', 'running'].includes(lobby.value.status) &&
      lobby.value.teams.length < lobby.value.max_teams &&
      gameRequiredSlotKeys.value.length > 0,
  ),
);

function lobbyStatusText(status: LobbyDto['status']): string {
  const labels: Record<LobbyDto['status'], string> = {
    draft: 'готовится',
    open: 'открыто',
    running: 'игра идет',
    paused: 'пауза',
    stopped: 'остановлено',
    updating: 'обновляется',
    closed: 'закрыто',
  };
  return labels[status] ?? status;
}

function lobbyStatusClass(status: LobbyDto['status']): string {
  return statusPillClass(status);
}

function participantPresence(teamId: string): string {
  const state = lobby.value?.teams.find(team => team.team_id === teamId);
  return state?.is_bot ? 'Бот' : state?.online ? 'Онлайн' : 'Офлайн';
}
function participantQueueLabel(teamId: string): string {
  if (lobby.value?.playing_team_ids.includes(teamId)) return 'Играет';
  if (queuedDuelGroups.value.some(group => group.runs.some(run => run.team_id === teamId))) return 'Дуэль в очереди';
  return lobby.value?.teams.find(team => team.team_id === teamId)?.ready ? 'В очереди' : 'Не в очереди';
}
function participantQueueTone(teamId: string): string {
  return lobby.value?.playing_team_ids.includes(teamId) ? 'agp-pill--success'
    : (lobby.value?.teams.find(team => team.team_id === teamId)?.ready || queuedDuelGroups.value.some(group => group.runs.some(run => run.team_id === teamId))) ? 'agp-pill--primary' : 'agp-pill--neutral';
}
function participantActions(stat: LobbyParticipantStatsDto): ActionMenuItem[] {
  const items: ActionMenuItem[] = [
    { id: 'code', label: 'Код игрока', disabled: isBusy.value },
    { id: 'games', label: 'Игры участника' },
  ];
  if (canUseAdminBots.value) items.push({ id: 'remove', label: 'Удалить из лобби', danger: true, disabled: isBusy.value || Boolean(activeCompetition.value) });
  return items;
}
function handleParticipantAction(action: string, stat: LobbyParticipantStatsDto): void {
  if (action === 'code') void openPlayerCode(stat);
  if (action === 'games') showPlayerMatches(stat.team_id);
  if (action === 'remove') void removeTeamFromLobby(stat);
}
function showPlayerMatches(teamId: string): void {
  void router.replace({ query: { ...route.query, tab: undefined, player: teamId, search: undefined, page: undefined } });
}
function toggleMatchRoster(groupId: string): void {
  const next = new Set(expandedMatches.value);
  if (next.has(groupId)) next.delete(groupId); else next.add(groupId);
  expandedMatches.value = next;
}
async function copyInvite(): Promise<void> {
  try {
    await navigator.clipboard.writeText(inviteUrl.value);
    inviteCopied.value = true;
  } catch {
    errorMessage.value = 'Не удалось скопировать ссылку';
  }
}

function syncLobbySettings(force = false): void {
  if (!lobby.value || (!force && lobbySettingsTouched.value)) return;
  lobbySettingsTitle.value = lobby.value.title;
  lobbySettingsAccess.value = lobby.value.access;
  lobbySettingsAccessCode.value = '';
  lobbySettingsMaxTeams.value = String(lobby.value.max_teams);
  lobbySettingsTouched.value = false;
}

function clampCompetitionSettingsToGame(): void {
  const minSize = competitionMinMatchSize.value;
  const maxSize = competitionMaxMatchSize.value;
  competitionMatchSize.value = Math.max(minSize, Math.min(maxSize, Number(competitionMatchSize.value) || maxSize));
  competitionAdvanceTopK.value = Math.max(1, Math.min(competitionMatchSize.value, Number(competitionAdvanceTopK.value) || 1));
}

watch(
  () => lobby.value?.lobby_id,
  () => syncLobbySettings(true),
);

watch(
  () =>
    lobby.value
      ? [
          lobby.value.title,
          lobby.value.access,
          lobby.value.max_teams,
        ].join('|')
      : '',
  () => syncLobbySettings(false),
);

watch(
  () => [competitionMinMatchSize.value, competitionMaxMatchSize.value, competitionMatchSize.value, competitionAdvanceTopK.value].join('|'),
  clampCompetitionSettingsToGame,
);
const readyStatusLabel = computed(() => {
  if (lobby.value?.my_status !== 'playing' && queuedDuelGroups.value.some(group => group.runs.some(run => run.team_id === lobby.value?.my_team_id))) return 'Дуэль в очереди';
  if (isWaitingForReplay.value) return lobby.value?.cycle_phase_label || 'Показ реплея';
  if (lobby.value?.my_status === 'playing') return 'Вы играете';
  if (lobby.value?.my_status === 'queued') return 'Вы в очереди';
  if (codeLockedByCompetition.value) return 'Код заблокирован';
  if (isDirty.value) return 'Есть изменения';
  if (requiredSlotCount.value === 0) return 'Нет ролей';
  if (filledRequiredSlots.value < requiredSlotCount.value) return 'Код не готов';
  return 'Можно играть';
});
const readyStatusHint = computed(() => {
  if (!canUseTrainingQueue.value && activeCompetition.value) return 'Во время соревнования обычная очередь отключена.';
  if (!canUseTrainingQueue.value) return 'Очередь сейчас недоступна.';
  if (isWaitingForReplay.value) return 'Система дожидается окончания реплея перед следующей игрой.';
  if (lobby.value?.my_status === 'playing') return 'Кнопка “Не готов” остановит участие после текущего состояния.';
  if (lobby.value?.my_status === 'queued') return 'Матч начнется автоматически, когда найдутся соперники.';
  if (codeLockedByCompetition.value) return 'Политика соревнования запрещает менять код.';
  if (isDirty.value) return 'Сохраните код, чтобы встать в очередь.';
  if (requiredSlotCount.value === 0) return 'Игра не описала обязательные роли.';
  if (filledRequiredSlots.value < requiredSlotCount.value) {
    return `Заполнено ${filledRequiredSlots.value} из ${requiredSlotCount.value} обязательных ролей.`;
  }
  return 'Нажмите “Готов”, чтобы встать в очередь.';
});
const managerCycleStatusLabel = computed(() => lobby.value?.cycle_phase_label || gameSignalLabel.value);
const managerCycleStatusHint = computed(() => {
  const phase = lobby.value?.cycle_phase;
  if (phase === 'replay') return 'Игроки сейчас смотрят реплей своего матча.';
  if (phase === 'result') return 'Показан победитель, затем лобби вернется к ожиданию.';
  if (phase === 'simulation') return 'Матчи выполняются в фоне.';
  if (phase === 'waiting_viewer') return 'Система ждет зрителя перед стартом матча.';
  if (lobby.value?.status === 'paused') return 'Лобби на паузе. Возобновите запуск, когда участники будут готовы.';
  if (lobby.value?.status === 'stopped') return 'Запуск лобби остановлен.';
  return 'Матч начнётся автоматически после набора готовых игроков.';
});
const currentCompetitionRound = computed(() => {
  const competition = activeCompetition.value;
  if (!competition) return null;
  return competition.rounds.find((round) => round.round_index === (competition.broadcast?.round_index ?? competition.current_round_index)) ?? null;
});
const visibleCompetitionMatches = computed(() =>
  currentCompetitionRound.value?.matches.filter(match => competitionMatchHasWatchableRun(match) && Boolean(matchPrimaryRunId(match))) ?? [],
);
const currentCompetitionMatch = computed(() => {
  const selected = selectedCompetitionRunId.value;
  if (selected) {
    const selectedMatch = visibleCompetitionMatches.value.find(
      (match) => Object.values(match.run_ids_by_team).includes(selected),
    );
    if (selectedMatch) return selectedMatch;
  }
  const broadcasting = activeCompetition.value?.broadcast?.match_id;
  if (broadcasting) return visibleCompetitionMatches.value.find(match => match.match_id === broadcasting) ?? null;
  return visibleCompetitionMatches.value[0] ?? null;
});
const currentCompetitionRun = computed(() => {
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!activeCompetition.value) return null;
  if (
    selectedCompetitionRunId.value &&
    visibleCompetitionMatches.value.some((match) => Object.values(match.run_ids_by_team).includes(selectedCompetitionRunId.value))
  ) {
    return competitionRunsById.value[selectedCompetitionRunId.value] ?? null;
  }
  if (activeCompetition.value.broadcast) return competitionRunsById.value[activeCompetition.value.broadcast.run_id] ?? null;
  const match = currentCompetitionMatch.value;
  if (match && myTeamId) {
    const runId = match.run_ids_by_team[myTeamId] ?? '';
    return runId ? competitionRunsById.value[runId] ?? null : null;
  }
  if (match) {
    const runId = matchPrimaryRunId(match);
    return runId ? competitionRunsById.value[runId] ?? null : null;
  }
  return null;
});
const currentCompetitionRunId = computed(() => {
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!activeCompetition.value) return '';
  if (
    selectedCompetitionRunId.value &&
    visibleCompetitionMatches.value.some((match) => Object.values(match.run_ids_by_team).includes(selectedCompetitionRunId.value))
  ) {
    return selectedCompetitionRunId.value;
  }
  if (activeCompetition.value.broadcast) return activeCompetition.value.broadcast.run_id;
  if (currentCompetitionRun.value) return currentCompetitionRun.value.run_id;
  if (currentCompetitionMatch.value && myTeamId) return currentCompetitionMatch.value.run_ids_by_team[myTeamId] ?? '';
  if (currentCompetitionMatch.value) return matchPrimaryRunId(currentCompetitionMatch.value) ?? '';
  return '';
});
const currentGameRunId = computed(() => {
  if (activeCompetition.value) return currentCompetitionRunId.value;
  const selected = selectedTrainingRunId.value;
  if (selected && currentTrainingRunIdSet.value.has(selected)) return selected;
  return lobby.value?.current_run_id || currentTrainingMatchGroups.value[0]?.runs[0]?.run_id || '';
});
const editorGameRunId = computed(() => {
  const own = lobby.value?.my_team_id;
  if (activeCompetition.value) {
    const broadcast = activeCompetition.value.broadcast;
    return ownCompetitionEditorRun(own, visibleCompetitionMatches.value, broadcast ? broadcast.match_id || null : undefined);
  }
  return ownTrainingEditorRun(own, currentTrainingMatchGroups.value, archivedTrainingMatchGroups.value);
});
const displayedGameRunId = computed(() => activeTab.value === 'code'
  ? editorGameRunId.value
  : currentGameRunId.value || (activeCompetition.value ? '' : lastGameRunId.value));
const displayedCompetitionMatch = computed(() => visibleCompetitionMatches.value.find(
  match => Object.values(match.run_ids_by_team).includes(displayedGameRunId.value),
) ?? null);
const displayedGameWatchKeySource = computed(() => [
  displayedGameRunId.value,
  sessionStore.sessionId,
  canShowDisplayedRunPrint.value ? 'print' : 'no-print',
].join('|'));
function buildDisplayedGameWatchUrl(runId: string): string {
  if (!runId) return '';
  const params = new URLSearchParams({
    embed: '1',
    autoplay: '1',
    speed_ms: String(lobby.value?.cycle_frame_ms ?? 500),
    show_print: canShowDisplayedRunPrint.value ? '1' : '0',
  });
  if (sessionStore.sessionId) {
    params.set('session_id', sessionStore.sessionId);
  }
  return `/runs/${runId}/watch?${params.toString()}`;
}
const canShowDisplayedRunPrint = computed(() => {
  const myTeamId = lobby.value?.my_team_id;
  if (!myTeamId || !displayedGameRunId.value) return false;
  const trainingRun = trainingRunsById.value[displayedGameRunId.value];
  if (trainingRun) return trainingRun.team_id === myTeamId;
  const competitionRun = competitionRunsById.value[displayedGameRunId.value];
  if (competitionRun) return competitionRun.team_id === myTeamId;
  return false;
});
const canFinishActiveCompetition = computed(
  () => canManage.value && activeCompetition.value?.status === 'completed',
);
const activeCompetitionBoundsLabel = computed(() => {
  if (!activeCompetition.value) return '';
  const min = activeCompetition.value.min_match_size;
  const max = activeCompetition.value.match_size;
  return min === max ? `${max} игроков` : `${min}-${max} игроков`;
});
const competitionBannerText = computed(() => {
  const competition = activeCompetition.value;
  if (competition?.status === 'completed') return (competition.winner_team_ids.length > 1 ? 'Победители: ' : 'Победитель: ') + (competition.winner_team_ids.map(teamLabel).join(', ') || '—');
  const round = currentCompetitionRound.value;
  return round ? `Раунд ${round.round_index} · ${competitionRoundStatusLabel(round.status).toLocaleLowerCase('ru-RU')}` : 'Ожидание первого раунда';
});
const codeLockedByCompetition = computed(() => {
  const competition = activeCompetition.value;
  if (!competition || competition.status === 'finished') return false;
  if (competition.code_policy === 'locked_on_registration') return true;
  if (competition.code_policy === 'locked_on_start') {
    return ['running', 'paused', 'completed'].includes(competition.status);
  }
  if (competition.code_policy === 'allowed_between_matches') {
    return currentCompetitionRound.value?.matches.some(match => match.team_ids.includes(lobby.value?.my_team_id ?? '') && effectiveCompetitionMatchStatus(match) === 'running') ?? false;
  }
  return false;
});
const canEditSelectedCode = computed(() =>
  Boolean(
    !showPlayerCodeDialog.value &&
      codeWorkspaceTeamId.value && activeSlotKey.value &&
      (codeWorkspaceTeamId.value === lobby.value?.my_team_id) &&
      (!codeLockedByCompetition.value || canManage.value),
  ),
);
const trainingRunsById = computed(() => {
  const result: Record<string, RunDto> = {};
  for (const run of trainingRuns.value) result[run.run_id] = run;
  return result;
});
const competitionRunsById = computed(() => {
  const result: Record<string, CompetitionRunItemDto> = {};
  for (const run of competitionRuns.value) result[run.run_id] = run;
  return result;
});
const currentTrainingMatchGroups = computed(() => {
  const groups = lobby.value?.current_match_groups ?? [];
  return groups.length
    ? groups.map((group) => trainingMatchGroupFromDto(group, false))
    : buildTrainingMatchGroups(lobby.value?.current_run_ids ?? [], false);
});
const queuedDuelGroups = computed(() => currentTrainingMatchGroups.value.filter(group => group.status === 'queued')
  .sort((left, right) => Date.parse(left.started_at || '') - Date.parse(right.started_at || '')));
const bannerMatchRunId = computed(() => {
  return ownCurrentMatchRun(lobby.value?.my_team_id, currentTrainingMatchGroups.value);
});
const archivedTrainingMatchGroups = computed(() => {
  const groups = lobby.value?.archived_match_groups ?? [];
  return groups.length
    ? groups.map((group) => trainingMatchGroupFromDto(group, true))
    : buildTrainingMatchGroups(lobby.value?.archived_run_ids ?? [], true);
});
const currentTrainingRunIdSet = computed(() => new Set(
  currentTrainingMatchGroups.value.flatMap((group) => group.runs.map((run) => run.run_id)),
));
const competitionReplayChoices = computed(() =>
  visibleCompetitionMatches.value.map((match, matchIndex) => {
    const myTeamId = lobby.value?.my_team_id ?? '';
    const viewerRunId = (myTeamId ? match.run_ids_by_team[myTeamId] : '') || matchPrimaryRunId(match);
    return {
      run_id: viewerRunId,
      label: `Матч ${matchIndex + 1}` + ((match.attempt_number ?? 1) > 1 ? ` · переигровка ${match.attempt_number}/3` : ''),
      player_count: match.team_ids.length,
      meta: match.team_ids.map(teamLabel).join(' · '),
    };
  }).filter((choice) => Boolean(choice.run_id)),
);
const trainingReplayChoices = computed(() =>
  trainingMatchSections.value.current.filter(group => group.status !== 'queued').map((group, groupIndex) => {
    const myTeamId = lobby.value?.my_team_id ?? '';
    const ownRun = group.runs.find((run) => run.team_id === myTeamId);
    const viewerRun = ownRun ?? group.runs[0];
    return {
      run_id: viewerRun?.run_id ?? '',
      label: `Матч ${groupIndex + 1}`,
      player_count: matchGroupTeamIds(group).length,
      meta: group.runs.map((run) => teamLabel(run.team_id)).join(' · '),
    };
  }).filter((choice) => Boolean(choice.run_id)),
);
const currentReplayChoices = computed(() =>
  activeCompetition.value ? competitionReplayChoices.value : trainingReplayChoices.value,
);
const allTrainingMatchGroups = computed(() => [
  ...currentTrainingMatchGroups.value,
  ...archivedTrainingMatchGroups.value,
]);
const trainingMatchSections = computed(() => splitTrainingMatches(allTrainingMatchGroups.value));
const filteredTrainingMatchGroups = computed(() => trainingMatchSections.value.history.filter(group =>
  (canManage.value || matchGroupTeamIds(group).includes(lobby.value?.my_team_id ?? '')) &&
  (!matchPlayerFilter.value || matchGroupTeamIds(group).includes(matchPlayerFilter.value)) &&
  (!onlyProblemMatches.value || trainingMatchHasError(group)) &&
  matchesHistoryQuery(matchGroupTeamIds(group).map(teamLabel).join(' ') + ' ' + formatMatchDate(group),
    group.started_at || group.finished_at || trainingRunsById.value[primaryRunId(group)]?.created_at || null,
    matchSearch.value, matchDateFrom.value, matchDateTo.value)));
const matchPageCount = computed(() =>
  Math.max(1, Math.ceil(filteredTrainingMatchGroups.value.length / matchesPerPage))
);
const pagedTrainingMatchGroups = computed(() => {
  const start = (matchPage.value - 1) * matchesPerPage;
  return filteredTrainingMatchGroups.value.slice(start, start + matchesPerPage);
});
watch(matchPageCount, (pageCount) => {
  if (matchPage.value > pageCount) matchPage.value = pageCount;
});
watch(allTrainingMatchGroups, () => {
  if (matchPage.value < 1) matchPage.value = 1;
  if (matchPage.value > matchPageCount.value) matchPage.value = matchPageCount.value;
});
watch(currentReplayChoices, (choices) => {
  if (!choices.length) {
    selectedTrainingRunId.value = '';
    selectedCompetitionRunId.value = '';
    return;
  }
  if (activeCompetition.value) {
    if (selectedCompetitionRunId.value && choices.some((choice) => choice.run_id === selectedCompetitionRunId.value)) {
      return;
    }
    const preferred = typeof route.query.match === 'string' ? route.query.match : currentCompetitionRun.value?.run_id;
    selectedCompetitionRunId.value = choices.find((choice) => choice.run_id === preferred)?.run_id ?? choices[0].run_id;
  } else {
    if (selectedTrainingRunId.value && choices.some((choice) => choice.run_id === selectedTrainingRunId.value)) {
      return;
    }
    const preferred = typeof route.query.match === 'string' ? route.query.match : lobby.value?.current_run_id;
    selectedTrainingRunId.value = choices.find((choice) => choice.run_id === preferred)?.run_id ?? choices[0].run_id;
  }
});
const displayedTrainingRunIds = computed(() => {
  if (!displayedGameRunId.value) return [];
  const group = allTrainingMatchGroups.value
    .find((item) => item.runs.some((run) => run.run_id === displayedGameRunId.value));
  if (group) return group.runs.map((run) => run.run_id);
  const competitionMatch = displayedCompetitionMatch.value;
  if (competitionMatch && Object.values(competitionMatch.run_ids_by_team).includes(displayedGameRunId.value)) {
    return competitionMatch.team_ids
      .map((teamId) => competitionMatch.run_ids_by_team[teamId] ?? '')
      .filter(Boolean);
  }
  return [displayedGameRunId.value];
});
const displayedGameMatchGroup = computed(() =>
  allTrainingMatchGroups.value.find((item) => item.runs.some((run) => run.run_id === displayedGameRunId.value)) ?? null,
);
function isDisplayedEmbeddedGameFrame(message: EmbeddedGameFrame | null): message is EmbeddedGameFrame {
  if (!message) return false;
  if (message.runId === displayedGameRunId.value) return true;
  return displayedTrainingRunIds.value.includes(message.runId);
}
const frameGameStats = computed<CurrentGameStatRow[]>(() => {
  const message = embeddedGameFrame.value;
  if (!isDisplayedEmbeddedGameFrame(message)) return [];
  const players = collectFrameGamePlayers(message);
  const embeddedRows = message.players.map((player, index) => buildCurrentGameStatFromEmbeddedPlayer(message, player, index));
  const frameRows = players.map((player, index) => buildCurrentGameStatFromFrame(message, player, index));
  return dedupeCurrentGameStats(embeddedRows.length ? embeddedRows : frameRows);
});
const fallbackGameStats = computed<CurrentGameStatRow[]>(() =>
  displayedTrainingRunIds.value.flatMap((runId) => {
    const trainingRun = trainingRunsById.value[runId];
    if (trainingRun) {
      const groupScore = displayedGameMatchGroup.value?.scores_by_team[trainingRun.team_id];
      const payloadScore = extractRunScore(isRecord(trainingRun.result_payload) ? trainingRun.result_payload : {}, trainingRun.team_id);
      const scoreValue = payloadScore ?? (typeof groupScore === 'number' && Number.isFinite(groupScore) ? groupScore : null);
      return [{
        run_id: trainingRun.run_id,
        team_id: trainingRun.team_id,
        display_name: teamLabel(trainingRun.team_id),
        status: runStatusLabel(trainingRun.status),
        score: scoreValue === null ? runScoreLabel(trainingRun) : scoreLabel(scoreValue),
        scoreValue,
        lifePercent: 0,
        shieldPercent: 0,
        meta: '',
        isSelf: trainingRun.team_id === lobby.value?.my_team_id,
      }];
    }
    const competitionRun = competitionRunsById.value[runId];
    if (!competitionRun) return [];
    const payloadScore = extractRunScore(
      isRecord(competitionRun.result_payload) ? competitionRun.result_payload : {},
      competitionRun.team_id,
    );
    const competitionScore = displayedCompetitionMatch.value?.scores_by_team[competitionRun.team_id];
    const scoreValue = payloadScore ?? (typeof competitionScore === 'number' && Number.isFinite(competitionScore) ? competitionScore : null);
    return [{
      run_id: competitionRun.run_id,
      team_id: competitionRun.team_id,
      display_name: teamLabel(competitionRun.team_id),
      status: runStatusLabel(competitionRun.status as RunDto['status']),
      score: scoreValue === null ? 'пока нет' : scoreLabel(scoreValue),
      scoreValue,
      lifePercent: 0,
      shieldPercent: 0,
      meta: '',
      isSelf: competitionRun.team_id === lobby.value?.my_team_id,
    }];
  }),
);
const currentGameStats = computed<CurrentGameStatRow[]>(() => {
  if (frameGameStats.value.length) return sortCurrentGameStats(frameGameStats.value);
  const rows = replayFinishedInViewer.value ? fallbackGameStats.value : fallbackGameStats.value.map(row => ({
    ...row, score: '—', scoreValue: null, status: lobby.value?.cycle_phase === 'simulation' ? 'подготовка' : 'в игре',
  }));
  return sortCurrentGameStats(dedupeCurrentGameStats(rows));
});
const currentGameFrameLabel = computed(() => {
  const message = embeddedGameFrame.value;
  if (!isDisplayedEmbeddedGameFrame(message)) {
    if ((lobby.value?.cycle_replay_frame_count ?? 0) > 0) {
      return `кадр ${(lobby.value?.cycle_replay_frame_index ?? 0) + 1}/${lobby.value?.cycle_replay_frame_count}`;
    }
    return 'кадр —';
  }
  if (message.replayFrameCount > 0) {
    return `кадр ${message.replayFrameIndex + 1}/${message.replayFrameCount}`;
  }
  return `ход ${message.tick}`;
});
const currentGamePhaseLabel = computed(() => {
  const message = embeddedGameFrame.value;
  if (isDisplayedEmbeddedGameFrame(message) && message.firstShowActive) return message.firstShowWaiting ? 'Подготовка матча' : 'Первый показ';
  if (!isDisplayedEmbeddedGameFrame(message)) {
    return lobby.value?.cycle_phase_label || (displayedGameRunId.value ? 'ожидаем кадры' : 'нет активной игры');
  }
  return gamePhaseLabel(message.phase, message.status);
});
const gameSignalTone = computed<'idle' | 'yellow' | 'green'>(() => {
  const phase = lobby.value?.cycle_phase;
  if (phase === 'replay' || phase === 'result') return 'green';
  if (phase === 'simulation' || phase === 'waiting_viewer' || displayedGameRunId.value) return 'yellow';
  return 'idle';
});
const gameSignalLabel = computed(() => {
  const phase = lobby.value?.cycle_phase;
  if (phase === 'replay') return 'Идет реплей';
  if (phase === 'result') return 'Показан результат матча';
  if (phase === 'simulation') return 'Матч симулируется';
  if (phase === 'waiting_viewer') return 'Ожидание зрителя перед матчем';
  return 'Ожидание игроков';
});
const isWaitingForReplay = computed(() => {
  return lobby.value?.cycle_phase === 'replay' || lobby.value?.cycle_phase === 'result';
});
const replayFinishedInViewer = computed(() => {
  if (!displayedGameRunId.value) return false;
  const message = embeddedGameFrame.value;
  if (isDisplayedEmbeddedGameFrame(message) && message.firstShowActive) return false;
  if (activeTab.value !== 'code' && lobby.value?.cycle_phase === 'result') return true;
  if (!isDisplayedEmbeddedGameFrame(message)) return false;
  if (message.replayFrameCount > 1) return message.replayFrameIndex >= message.replayFrameCount - 1;
  return message.phase === 'finished';
});
const currentGameLeader = computed(() => {
  const scoredRows = currentGameStats.value.filter((row) => row.scoreValue !== null);
  if (!scoredRows.length) return null;
  return [...scoredRows].sort((left, right) => {
    const rightScore = right.scoreValue ?? Number.NEGATIVE_INFINITY;
    const leftScore = left.scoreValue ?? Number.NEGATIVE_INFINITY;
    if (rightScore !== leftScore) return rightScore - leftScore;
    if (right.isSelf !== left.isSelf) return Number(right.isSelf) - Number(left.isSelf);
    return left.display_name.localeCompare(right.display_name, 'ru');
  })[0] ?? null;
});
const currentGameLeaderLabel = computed(() => currentGameLeader.value?.display_name ?? '—');
const currentGameIsDraw = computed(() => {
  const group = displayedGameMatchGroup.value;
  if (group && matchGroupIsDraw(group)) return true;
  const match = displayedCompetitionMatch.value;
  const teamIds = match?.team_ids ?? (group ? matchGroupTeamIds(group) : currentGameStats.value.map(player => player.team_id));
  const scores = { ...match?.scores_by_team, ...Object.fromEntries(currentGameScoreMap.value) };
  if (isMatchDraw(game.value?.slug, teamIds, scores)) return true;
  const visibleScores = currentGameStats.value.map(player => player.scoreValue);
  return visibleScores.length > 1 && visibleScores.every(score => score !== null && score === visibleScores[0]);
});
const currentGameWinnerLabel = computed(() => {
  const groupWinners = displayedGameMatchGroup.value?.winner_team_ids ?? [];
  const groupWinner = primaryWinnerTeamId(groupWinners, currentGameScoreMap.value);
  if (groupWinner) return teamLabel(groupWinner);

  const competitionMatch = displayedCompetitionMatch.value;
  if (competitionMatch?.advanced_team_ids.length) {
    const competitionWinner = primaryWinnerTeamId(
      competitionMatch.advanced_team_ids,
      new Map([
        ...Object.entries(competitionMatch.scores_by_team),
        ...currentGameScoreMap.value.entries(),
      ]),
    );
    if (competitionWinner) return teamLabel(competitionWinner);
  }

  return currentGameLeader.value?.display_name ?? 'не определен';
});
const currentGameScoreMap = computed(() => {
  const result = new Map<string, number>();
  for (const row of currentGameStats.value) {
    if (row.scoreValue !== null) result.set(row.team_id, row.scoreValue);
  }
  return result;
});
const statsByTeam = computed(() => {
  const result: Record<string, LobbyParticipantStatsDto> = {};
  for (const stat of lobby.value?.participant_stats ?? []) result[stat.team_id] = stat;
  return result;
});
const lobbyLeaderboard = computed(() =>
  sortLobbyParticipants(lobby.value?.participant_stats ?? [], participantSort.value, teamLabel),
);

const preparingTeamIds = computed(() => {
  const listed = new Set([...(lobby.value?.playing_team_ids ?? []), ...(lobby.value?.queued_team_ids ?? [])]);
  return (lobby.value?.teams ?? []).map((team) => team.team_id).filter((teamId) => !listed.has(teamId));
});
const codeStateLabel = computed(() => {
  if (!activeSlotKey.value) return 'Выберите роль';
  if (codeLockedByCompetition.value && !canManage.value) {
    if (activeCompetition.value?.code_policy === 'allowed_between_matches') {
      return 'Код заблокирован на время матча соревнования.';
    }
    if (activeCompetition.value?.code_policy === 'locked_on_registration') {
      return 'Код заблокирован политикой соревнования с момента регистрации.';
    }
    return 'Код заблокирован политикой соревнования до завершения соревнования.';
  }
  if (codeWorkspaceTeamId.value !== lobby.value?.my_team_id) return 'Только просмотр';
  if (lobby.value?.my_status === 'playing') {
    return isDirty.value
      ? 'Есть несохраненные изменения. Текущая игра уже использует зафиксированный код.'
      : 'Сохранено. Текущая игра использует зафиксированный код, новые сохранения пойдут в следующую игру.';
  }
  if (lobby.value?.my_status === 'queued') {
    return isDirty.value
      ? 'Есть несохраненные изменения. Сохраните их до следующего запуска.'
      : 'Сохранено. При старте матча система зафиксирует этот код.';
  }
  if (isDirty.value) return 'Есть несохраненные изменения';
  return activeSlot.value?.code?.trim() ? 'Сохранено' : 'Пусто';
});

const canAutosaveCode = computed(() =>
  Boolean(
    codeWorkspaceTeamId.value &&
      activeSlotKey.value &&
      canEditSelectedCode.value &&
      editorCode.value !== savedCode.value,
  ),
);

function lobbyId(): string {
  return String(route.params.lobbyId || '');
}

function scoreLabel(value: number | null): string {
  if (value === null) return 'нет данных';
  return matchScoreLabel(value);
}

function averageScoreLabel(value: number | null | undefined): string {
  return value === null || value === undefined ? 'нет данных' : matchScoreLabel(value);
}

function sortCurrentGameStats(rows: CurrentGameStatRow[]): CurrentGameStatRow[] {
  return [...rows].sort((left, right) => {
    const rightScore = right.scoreValue ?? Number.NEGATIVE_INFINITY;
    const leftScore = left.scoreValue ?? Number.NEGATIVE_INFINITY;
    if (rightScore !== leftScore) return rightScore - leftScore;
    if (right.isSelf !== left.isSelf) return Number(right.isSelf) - Number(left.isSelf);
    return left.display_name.localeCompare(right.display_name, 'ru');
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function runStatusLabel(status: RunDto['status']): string {
  const labels: Record<RunDto['status'], string> = {
    created: 'создан',
    queued: 'в очереди',
    running: 'идет',
    finished: 'завершен',
    failed: 'ошибка',
    timeout: 'таймаут',
    canceled: 'остановлен',
  };
  return labels[status];
}

function gamePhaseLabel(phase: string, status: RunDto['status']): string {
  const normalized = phase.toLowerCase();
  const labels: Record<string, string> = {
    created: 'создан',
    queued: 'ожидает запуска',
    running: 'игра идет',
    started: 'игра идет',
    playing: 'игра идет',
    finished: 'завершен',
    failed: 'ошибка',
    timeout: 'таймаут',
    canceled: 'остановлен',
  };
  return labels[normalized] ?? runStatusLabel(status);
}

function runScoreLabel(run: RunDto): string {
  const payload = isRecord(run.result_payload) ? run.result_payload : {};
  const metrics = isRecord(payload.metrics) ? payload.metrics : {};
  const score = extractRunScore(payload, run.team_id) ?? extractRunScore(metrics, run.team_id);
  return score === null ? 'пока нет' : score.toFixed(1);
}

function extractRunScore(source: Record<string, unknown>, teamId: string): number | null {
  for (const key of ['score', 'points']) {
    const raw = source[key];
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  }
  const scores = source.scores;
  if (!isRecord(scores)) return null;
  const ownScore = scores[teamId];
  if (typeof ownScore === 'number' && Number.isFinite(ownScore)) return ownScore;
  const values = Object.values(scores).filter((item): item is number => typeof item === 'number' && Number.isFinite(item));
  return values.length === 1 ? values[0] : null;
}

function pluralizePlayers(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return 'игрок';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'игрока';
  return 'игроков';
}

function primaryRunId(group: TrainingMatchGroup): string {
  return group.runs[0]?.run_id ?? '';
}

function matchGroupTeamIds(group: TrainingMatchGroup): string[] {
  return [...new Set(group.runs.map((run) => run.team_id).filter(Boolean))];
}

function runIdForTeamInGroup(group: TrainingMatchGroup, teamId: string): string {
  return group.runs.find((run) => run.team_id === teamId)?.run_id ?? primaryRunId(group);
}

function trainingMatchHasError(group: TrainingMatchGroup): boolean {
  return group.runs.some(link => {
    const run = trainingRunsById.value[link.run_id];
    const metrics = isRecord(run?.result_payload?.metrics) ? run.result_payload.metrics : {};
    return run && (['failed', 'timeout'].includes(run.status) || Boolean(run.error_message) || Number(metrics.bot_errors) > 0 || Boolean(metrics.compile_error) || (isRecord(metrics.compile_errors) && Object.values(metrics.compile_errors).some(Boolean)));
  });
}
function matchGroupStatusLabel(group: TrainingMatchGroup): string {
  if (trainingMatchHasError(group)) return 'С ошибкой';
  if (group.status === 'queued') return 'Дуэль в очереди';
  if (group.status === 'simulation') return 'Идёт игра';
  if (group.status === 'replay') return 'Идёт повтор';
  return 'Завершён';
}
function trainingMatchTone(group: TrainingMatchGroup): string {
  if (trainingMatchHasError(group)) return 'agp-pill--danger';
  return shouldHideMatchWinner(group) ? 'agp-pill--primary' : 'agp-pill--success';
}
function trainingMatchSummary(group: TrainingMatchGroup): string {
  if (shouldHideMatchWinner(group)) return matchGroupTeamIds(group).length <= 5 ? matchGroupTeamIds(group).map(teamLabel).join(', ') : 'Матч идёт';
  if (matchGroupIsDraw(group)) return 'Ничья';
  const winner = matchWinnerLabel(group);
  return winner === 'не определен' ? 'Без победителя' : 'Победитель: ' + winner;
}
function trainingOwnResult(group: TrainingMatchGroup): string {
  if (shouldHideMatchWinner(group)) return 'Вы в игре';
  const score = matchPlayerScoreLabel(group, lobby.value?.my_team_id ?? '');
  if (matchGroupIsDraw(group)) return 'Вы: ничья' + (score ? ' · ' + score + ' очк.' : '');
  const winner = matchPlayerIsVisibleWinner(group, lobby.value?.my_team_id ?? '');
  return winner ? 'Вы: победа' + (score ? ' · ' + score + ' очк.' : '') : 'Вы: ' + (score ? score + ' очк.' : '—');
}
function participantCountLabel(count: number): string {
  const last = count % 10, hundred = count % 100;
  return `${count} ${hundred >= 11 && hundred <= 14 ? 'участников' : last === 1 ? 'участник' : last >= 2 && last <= 4 ? 'участника' : 'участников'}`;
}

function formatMatchDate(group: TrainingMatchGroup): string {
  const directDate = group.started_at || group.finished_at;
  if (directDate) return formatDateTime(directDate);
  const run = group.runs
    .map((item) => trainingRunsById.value[item.run_id])
    .filter(Boolean)
    .sort((left, right) => Date.parse(left.created_at) - Date.parse(right.created_at))[0];
  if (!run?.created_at) return 'время неизвестно';
  return formatDateTime(run.created_at);
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function matchWinnerLabel(group: TrainingMatchGroup): string {
  const winner = matchGroupPrimaryWinnerId(group);
  return winner ? teamLabel(winner) : 'не определен';
}

function shouldHideMatchWinner(group: TrainingMatchGroup): boolean {
  return ['queued', 'replay', 'simulation'].includes(group.status);
}

function matchGroupPrimaryWinnerId(group: TrainingMatchGroup): string {
  return primaryWinnerTeamId(matchGroupWinnerIds(group), matchGroupScoreMap(group));
}

function matchPlayerIsVisibleWinner(group: TrainingMatchGroup, teamId: string): boolean {
  return !shouldHideMatchWinner(group) && matchGroupPrimaryWinnerId(group) === teamId;
}

function matchPlayerScoreLabel(group: TrainingMatchGroup, teamId: string): string {
  const score = matchGroupScoreMap(group).get(teamId);
  return score === undefined ? '' : scoreLabel(score);
}

function matchGroupIsDraw(group: TrainingMatchGroup): boolean {
  const metrics = group.runs.map(link => trainingRunsById.value[link.run_id]?.result_payload?.metrics);
  return isMatchDraw(game.value?.slug, matchGroupTeamIds(group), Object.fromEntries(matchGroupScoreMap(group)),
    metrics.some(value => isRecord(value) && value.draw === true) ? { draw: true } : undefined);
}

function matchGroupWinnerIds(group: TrainingMatchGroup): string[] {
  if (matchGroupIsDraw(group)) return [];
  if (group.winner_team_ids.length) return group.winner_team_ids;
  const explicitWinners = new Set<string>();
  const placements = new Map<string, number>();
  const scores = new Map<string, number>();

  for (const runLink of group.runs) {
    const run = trainingRunsById.value[runLink.run_id];
    const payload = isRecord(run?.result_payload) ? run.result_payload : {};
    const winners = payload.winners ?? payload.winner;
    if (Array.isArray(winners)) {
      for (const winner of winners) {
        if (typeof winner === 'string' && winner) explicitWinners.add(winner);
      }
    } else if (typeof winners === 'string' && winners) {
      explicitWinners.add(winners);
    }

    const payloadPlacements = isRecord(payload.placements) ? payload.placements : {};
    for (const [teamId, rawPlacement] of Object.entries(payloadPlacements)) {
      if (typeof rawPlacement === 'number' && Number.isFinite(rawPlacement)) {
        placements.set(teamId, Math.min(placements.get(teamId) ?? rawPlacement, rawPlacement));
      }
    }

    const payloadScores = isRecord(payload.scores) ? payload.scores : {};
    for (const [teamId, rawScore] of Object.entries(payloadScores)) {
      if (typeof rawScore === 'number' && Number.isFinite(rawScore)) {
        scores.set(teamId, Math.max(scores.get(teamId) ?? rawScore, rawScore));
      }
    }

    const ownScore = extractRunScore(payload, runLink.team_id);
    if (ownScore !== null && runLink.team_id) {
      scores.set(runLink.team_id, Math.max(scores.get(runLink.team_id) ?? ownScore, ownScore));
    }
  }

  if (explicitWinners.size) return [...explicitWinners];
  if (placements.size) {
    const bestPlacement = Math.min(...placements.values());
    const placementWinners = [...placements.entries()]
      .filter(([, placement]) => placement === bestPlacement)
      .map(([teamId]) => teamId);
    if (placementWinners.length === 1) return placementWinners;
    if (!scores.size) return [];
    const bestScore = Math.max(...placementWinners.map((teamId) => scores.get(teamId) ?? Number.NEGATIVE_INFINITY));
    const winners = placementWinners.filter((teamId) => (scores.get(teamId) ?? Number.NEGATIVE_INFINITY) === bestScore);
    return winners.length === 1 ? winners : [];
  }
  if (scores.size) {
    const bestScore = Math.max(...scores.values());
    const winners = [...scores.entries()].filter(([, score]) => score === bestScore).map(([teamId]) => teamId);
    return winners.length === 1 ? winners : [];
  }
  return [];
}

function matchGroupScoreMap(group: TrainingMatchGroup): Map<string, number> {
  const scores = new Map<string, number>();
  for (const [teamId, score] of Object.entries(group.scores_by_team)) {
    if (Number.isFinite(score)) scores.set(teamId, score);
  }
  for (const runLink of group.runs) {
    const run = trainingRunsById.value[runLink.run_id];
    const payload = isRecord(run?.result_payload) ? run.result_payload : {};
    const payloadScores = isRecord(payload.scores) ? payload.scores : {};
    for (const [teamId, rawScore] of Object.entries(payloadScores)) {
      const score = numericFrameValue(rawScore);
      if (score !== null) scores.set(teamId, Math.max(scores.get(teamId) ?? score, score));
    }
    const ownScore = extractRunScore(payload, runLink.team_id);
    if (ownScore !== null && runLink.team_id) {
      scores.set(runLink.team_id, Math.max(scores.get(runLink.team_id) ?? ownScore, ownScore));
    }
  }
  return scores;
}

function primaryWinnerTeamId(teamIds: string[], scores: Map<string, number> = new Map()): string {
  const uniqueTeamIds = [...new Set(teamIds.filter(Boolean))];
  if (uniqueTeamIds.length <= 1) return uniqueTeamIds[0] ?? '';
  return uniqueTeamIds.sort((left, right) => {
    const leftScore = scores.get(left) ?? Number.NEGATIVE_INFINITY;
    const rightScore = scores.get(right) ?? Number.NEGATIVE_INFINITY;
    if (leftScore !== rightScore) return rightScore - leftScore;
    return teamLabel(left).localeCompare(teamLabel(right), 'ru');
  })[0] ?? '';
}

function matchPrimaryRunId(match: { team_ids: string[]; run_ids_by_team: Record<string, string> }): string {
  for (const teamId of match.team_ids) {
    const runId = match.run_ids_by_team[teamId];
    if (runId) return runId;
  }
  return Object.values(match.run_ids_by_team)[0] ?? '';
}

function runCreatedAtMs(run: { run_id: string }): number {
  const createdAt = trainingRunsById.value[run.run_id]?.created_at;
  const value = createdAt ? Date.parse(createdAt) : NaN;
  return Number.isFinite(value) ? value : 0;
}

function selectReplayChoice(runId: string): void {
  if (activeCompetition.value) selectedCompetitionRunId.value = runId;
  else selectedTrainingRunId.value = runId;
  if (activeTab.value === 'game') void router.replace({ query: { ...route.query, match: runId } });
}
function stepCurrentMatch(delta: number): void {
  const choices = currentReplayChoices.value;
  if (!choices.length) return;
  const index = choices.findIndex(choice => choice.run_id === displayedGameRunId.value);
  selectReplayChoice(choices[(Math.max(0, index) + delta + choices.length) % choices.length].run_id);
}
function openCurrentMatch(runId?: string): void {
  if (!runId && activeCompetition.value?.broadcast) {
    selectedCompetitionRunId.value = '';
    void router.push({ query: { ...route.query, tab: 'game', match: undefined } });
    return;
  }
  const choice = runId || currentReplayChoices.value.find(item => item.run_id === displayedGameRunId.value)?.run_id || currentReplayChoices.value[0]?.run_id;
  if (!choice) return;
  if (activeCompetition.value) selectedCompetitionRunId.value = choice; else selectedTrainingRunId.value = choice;
  void router.push({ query: { ...route.query, tab: 'game', match: choice } });
}
function resetHistoryFilters(): void {
  updateHistoryQuery({ search: undefined, player: undefined, after: undefined, before: undefined, errors: undefined });
}

function trainingMatchGroupFromDto(group: LobbyMatchGroupDto, archived: boolean): TrainingMatchGroup {
  return {
    group_id: group.group_id,
    batch_id: group.batch_id,
    archived,
    status: group.status,
    started_at: group.started_at,
    finished_at: group.finished_at,
    replay_frame_count: group.replay_frame_count,
    replay_frame_index: group.replay_frame_index,
    winner_team_ids: group.winner_team_ids,
    scores_by_team: group.scores_by_team ?? {},
    runs: group.run_ids.map((runId, index) => ({
      run_id: runId,
      team_id: group.team_ids[index] ?? trainingRunsById.value[runId]?.team_id ?? '',
    })),
  };
}

function buildTrainingMatchGroups(runIds: string[], archived: boolean): TrainingMatchGroup[] {
  const runs = runIds.map((runId) => ({
    run_id: runId,
    team_id: trainingRunsById.value[runId]?.team_id ?? '',
  })).sort((left, right) => runCreatedAtMs(right) - runCreatedAtMs(left));
  const maxPlayersPerMatch = game.value?.max_players_per_match ?? (game.value?.mode === 'small_match' ? 2 : 64);
  if (maxPlayersPerMatch < 64) {
    const groupSize = Math.max(2, maxPlayersPerMatch);
    const groups: TrainingMatchGroup[] = [];
    for (let index = 0; index < runs.length; index += groupSize) {
      const groupRuns = runs.slice(index, index + groupSize);
      groups.push({
        group_id: `${archived ? 'archive' : 'current'}-${index}-${groupRuns.map((run) => run.run_id).join('-')}`,
        batch_id: `${archived ? 'archive' : 'current'}-${index}`,
        archived,
        status: archived ? 'finished' : 'simulation',
        started_at: null,
        finished_at: null,
        replay_frame_count: 0,
        replay_frame_index: 0,
        winner_team_ids: [],
        scores_by_team: {},
        runs: groupRuns,
      });
    }
    return groups;
  }

  const closeCreatedAtMs = 2_000;
  const groups: TrainingMatchGroup[] = [];
  let currentGroup: typeof runs = [];
  for (const run of runs) {
    const previousRun = currentGroup[currentGroup.length - 1];
    const createdAt = runCreatedAtMs(run);
    const previousCreatedAt = previousRun ? runCreatedAtMs(previousRun) : 0;
    if (previousRun && Math.abs(previousCreatedAt - createdAt) > closeCreatedAtMs) {
      groups.push({
        group_id: `${archived ? 'archive' : 'current'}-${groups.length}-${currentGroup.map((item) => item.run_id).join('-')}`,
        batch_id: `${archived ? 'archive' : 'current'}-${groups.length}`,
        archived,
        status: archived ? 'finished' : 'simulation',
        started_at: null,
        finished_at: null,
        replay_frame_count: 0,
        replay_frame_index: 0,
        winner_team_ids: [],
        scores_by_team: {},
        runs: currentGroup,
      });
      currentGroup = [];
    }
    currentGroup.push(run);
  }
  if (currentGroup.length) {
    groups.push({
      group_id: `${archived ? 'archive' : 'current'}-${groups.length}-${currentGroup.map((item) => item.run_id).join('-')}`,
      batch_id: `${archived ? 'archive' : 'current'}-${groups.length}`,
      archived,
      status: archived ? 'finished' : 'simulation',
      started_at: null,
      finished_at: null,
      replay_frame_count: 0,
      replay_frame_index: 0,
      winner_team_ids: [],
      scores_by_team: {},
      runs: currentGroup,
    });
  }
  return groups;
}

function cleanCompetitionTitle(title: string): string {
  return title.replace(/^\[lobby:[^\]]+\]\s*/, '');
}

function archiveCompetitionWinnerLabel(item: LobbyCompetitionDto): string {
  return item.winner_team_ids.length ? item.winner_team_ids.map(teamLabel).join(', ') : 'не определен';
}

function teamLabel(teamId: string): string {
  const known = statsByTeam.value[teamId]?.display_name;
  if (known && !known.startsWith('team_')) return known;
  for (const run of Object.values(trainingRunsById.value)) {
    const participants = run.result_payload?.match_participants;
    if (Array.isArray(participants)) {
      const person = participants.find(p => isRecord(p) && p.team_id === teamId);
      if (isRecord(person) && typeof person.display_name === 'string' && !person.display_name.startsWith('team_')) return person.display_name;
    }
  }
  const number = [...teamId].reduce((hash, c) => (hash * 31 + c.charCodeAt(0)) >>> 0, 0) % 10000;
  return `Игрок №${number}`;
}

function collectFrameGamePlayers(message: EmbeddedGameFrame): Record<string, unknown>[] {
  const frame = message.frame;
  const byId = new Map<string, Record<string, unknown>>();
  collectRoleMapGamePlayers(byId, message);

  const visit = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (!isRecord(value)) return;

    const name = value.name ?? value.player ?? value.role ?? value.key;
    const hasPlayerShape =
      name !== undefined &&
      (
        value.score !== undefined ||
        value.points !== undefined ||
        value.life !== undefined ||
        value.hp !== undefined ||
        value.shield !== undefined ||
        value.coins !== undefined ||
        value.food_eaten !== undefined ||
        value.alive !== undefined
      );
    if (hasPlayerShape) {
      const id = String(value.team_id ?? value.key ?? value.role ?? value.name ?? `player-${byId.size + 1}`);
      upsertFrameGamePlayer(byId, id, value);
    }
    Object.values(value).forEach(visit);
  };

  visit(frame);
  collectSnakeGamePlayers(byId, message);
  return [...byId.values()];
}

function collectRoleMapGamePlayers(byId: Map<string, Record<string, unknown>>, message: EmbeddedGameFrame): void {
  const frame = isRecord(message.frame) ? message.frame : {};
  const positions = isRecord(frame.positions) ? frame.positions : null;
  if (!positions) return;
  const roleEntries = Object.entries(positions).filter(([, value]) => isRecord(value) || Array.isArray(value));
  if (!roleEntries.length) return;

  const batteries = isRecord(frame.batteries) ? frame.batteries : {};
  const collected = isRecord(frame.collected) ? frame.collected : {};
  const carrying = isRecord(frame.carrying) ? frame.carrying : {};
  const delivered = isRecord(frame.delivered) ? frame.delivered : {};
  const throws = isRecord(frame.throws) ? frame.throws : {};
  const frozen = isRecord(frame.frozen) ? frame.frozen : {};
  const labels = isRecord(frame.labels) ? frame.labels : {};
  const invalidMoves = isRecord(frame.invalid_moves) ? frame.invalid_moves : {};
  const slotScores = isRecord(frame.slot_scores) ? frame.slot_scores : {};
  roleEntries.forEach(([role], index) => {
    const label = typeof labels[role] === 'string' ? labels[role] : '';
    const participant = message.participants[index]
      ?? message.participants.find((item) => item.display_name === label);
    const teamId = participant?.team_id ?? role;
    const collectedValue = numericFrameValue(collected[role]) ?? 0;
    const carryingValue = numericFrameValue(carrying[role]) ?? 0;
    const deliveredValue = numericFrameValue(delivered[role]) ?? 0;
    const throwsValue = numericFrameValue(throws[role]) ?? 0;
    const frozenValue = numericFrameValue(frozen[role]) ?? 0;
    const batteryValue = numericFrameValue(batteries[role]);
    const invalidValue = numericFrameValue(invalidMoves[role]) ?? 0;
    const score = numericFrameValue(slotScores[role])
      ?? (
        Object.keys(delivered).length || Object.keys(carrying).length || Object.keys(throws).length
          ? Math.max(0, deliveredValue * 120 + carryingValue * 30 + throwsValue * 5 - invalidValue * 10)
          : Math.max(0, collectedValue * 100 + (batteryValue ?? 0) - invalidValue * 10)
      );
    upsertFrameGamePlayer(byId, teamId, {
      team_id: teamId,
      name: participant?.display_name || label || role,
      role,
      score,
      battery: batteryValue,
      collected: collectedValue,
      carrying: carryingValue,
      delivered: deliveredValue,
      throws: throwsValue,
      frozen: frozenValue,
      invalid_moves: invalidValue,
      alive: batteryValue === null ? true : batteryValue > 0,
    });
  });
}

function collectSnakeGamePlayers(byId: Map<string, Record<string, unknown>>, message: EmbeddedGameFrame): void {
  const frame = isRecord(message.frame) ? message.frame : {};
  const snakes = isRecord(frame.snakes) ? frame.snakes : null;
  if (!snakes) return;

  const slotScores = isRecord(frame.slot_scores) ? frame.slot_scores : {};
  Object.entries(snakes).forEach(([role, raw], index) => {
    if (!isRecord(raw)) return;
    const participant = message.participants[index];
    const teamId = typeof raw.team_id === 'string' && raw.team_id
      ? raw.team_id
      : participant?.team_id ?? role;
    const food = numericFrameValue(raw.food_eaten) ?? 0;
    const invalid = numericFrameValue(raw.invalid_moves) ?? 0;
    const length = Array.isArray(raw.body) ? raw.body.length : null;
    const alive = typeof raw.alive === 'boolean' ? raw.alive : true;
    const score = numericFrameValue(raw.score)
      ?? numericFrameValue(slotScores[role])
      ?? Math.max(0, food * 100 + (length ?? 0) * 5 + (alive ? 30 : 0) - invalid * 10);

    upsertFrameGamePlayer(byId, teamId, {
      team_id: teamId,
      name: typeof raw.name === 'string' && raw.name ? raw.name : participant?.display_name || role,
      role,
      score,
      food_eaten: food,
      length,
      invalid_moves: invalid,
      direction: typeof raw.direction === 'string' ? raw.direction : '',
      alive,
      life: length,
    });
  });
}

function upsertFrameGamePlayer(byId: Map<string, Record<string, unknown>>, id: string, next: Record<string, unknown>): void {
  const previous = byId.get(id);
  if (!previous) {
    byId.set(id, next);
    return;
  }

  const previousScore = numericFrameValue(previous.score ?? previous.points);
  const nextScore = numericFrameValue(next.score ?? next.points);
  const previousDetails = Object.values(previous).filter((value) => value !== null && value !== undefined && value !== '').length;
  const nextDetails = Object.values(next).filter((value) => value !== null && value !== undefined && value !== '').length;
  if (
    (previousScore === null && nextScore !== null) ||
    (previousScore === nextScore && nextDetails > previousDetails)
  ) {
    byId.set(id, next);
  }
}

function buildCurrentGameStatFromFrame(
  message: EmbeddedGameFrame,
  player: Record<string, unknown>,
  index: number,
): CurrentGameStatRow {
  const teamId = typeof player.team_id === 'string' ? player.team_id : '';
  const name = typeof player.name === 'string' ? player.name : '';
  const knownTeamLabel = teamId ? teamLabel(teamId) : '';
  const scoreValue = numericFrameValue(player.score ?? player.points);
  const life = numericFrameValue(player.life ?? player.hp);
  const shield = numericFrameValue(player.shield);
  const alive = typeof player.alive === 'boolean' ? player.alive : life !== 0;
  return {
    run_id: message.runId,
    team_id: teamId || `frame-player-${index}`,
    display_name: name && (!knownTeamLabel || knownTeamLabel === teamId) ? name : knownTeamLabel || name || `Игрок ${index + 1}`,
    status: message.phase === 'finished' ? (alive ? 'финиш' : 'выбыл') : alive ? 'в игре' : 'выбыл',
    score: framePlayerScoreLabel(player),
    scoreValue,
    lifePercent: percentFrameValue(life, 50),
    shieldPercent: percentFrameValue(shield, 25),
    meta: framePlayerMetaLabel(player),
    isSelf: teamId === lobby.value?.my_team_id,
  };
}

function buildCurrentGameStatFromEmbeddedPlayer(
  message: EmbeddedGameFrame,
  player: EmbeddedGamePlayerStat,
  index: number,
): CurrentGameStatRow {
  const teamId = player.team_id || player.id || `frame-player-${index}`;
  const scoreValue = numericFrameValue(player.score);
  const score = player.score_label || (scoreValue === null ? '—' : scoreLabel(scoreValue));
  return {
    run_id: message.runId,
    team_id: teamId,
    display_name: player.name || teamLabel(teamId) || `Игрок ${index + 1}`,
    status: message.phase === 'finished' ? (player.alive ? 'финиш' : 'выбыл') : player.alive ? 'в игре' : 'выбыл',
    score,
    scoreValue,
    lifePercent: Math.max(0, Math.min(100, player.life_percent)),
    shieldPercent: Math.max(0, Math.min(100, player.shield_percent)),
    meta: player.detail_label,
    isSelf: player.is_self || teamId === lobby.value?.my_team_id,
  };
}

function normalizeGameStatName(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9а-яё]+/gi, '');
}

function isSyntheticFrameTeamId(value: string): boolean {
  return value.startsWith('frame-player-');
}

function dedupeCurrentGameStats(rows: CurrentGameStatRow[]): CurrentGameStatRow[] {
  const concreteRows = rows.filter((row) => !isSyntheticFrameTeamId(row.team_id));
  const concreteNames = concreteRows
    .map((row) => normalizeGameStatName(row.display_name))
    .filter(Boolean);
  const result = new Map<string, CurrentGameStatRow>();
  const duplicateKeyByName = (normalizedName: string): string | null => {
    if (!normalizedName) return null;
    for (const [key, existing] of result.entries()) {
      if (normalizeGameStatName(existing.display_name) === normalizedName) return key;
    }
    return null;
  };

  const put = (row: CurrentGameStatRow): void => {
    const normalizedName = normalizeGameStatName(row.display_name);
    if (
      isSyntheticFrameTeamId(row.team_id) &&
      normalizedName &&
      concreteNames.some((name) => name.includes(normalizedName) || normalizedName.includes(name))
    ) {
      return;
    }

    const key = duplicateKeyByName(normalizedName)
      ?? (isSyntheticFrameTeamId(row.team_id) ? normalizedName || row.team_id : row.team_id);
    const previous = result.get(key);
    if (!previous) {
      result.set(key, row);
      return;
    }

    const previousHasScore = previous.scoreValue !== null;
    const rowHasScore = row.scoreValue !== null;
    if (
      (!previousHasScore && rowHasScore) ||
      (previousHasScore === rowHasScore && row.meta.length > previous.meta.length)
    ) {
      result.set(key, row);
    }
  };

  rows.forEach(put);
  return [...result.values()];
}

function numericFrameValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function percentFrameValue(value: number | null, max: number): number {
  if (value === null) return 0;
  return Math.max(0, Math.min(100, (value / max) * 100));
}

function framePlayerScoreLabel(player: Record<string, unknown>): string {
  const parts: string[] = [];
  const scoreSource = player.score !== undefined && player.score !== null ? 'score' : 'points';
  const score = numericFrameValue(scoreSource === 'score' ? player.score : player.points);
  if (score !== null) {
    parts.push(scoreLabel(score));
  }

  const details: Array<[string, string]> = [
    ['очки', 'points'],
    ['монеты', 'coins'],
    ['энергия', 'collected'],
    ['доставлено', 'delivered'],
    ['несет', 'carrying'],
    ['броски', 'throws'],
    ['еда', 'food_eaten'],
    ['длина', 'length'],
    ['заряд', 'battery'],
    ['заморозка', 'frozen'],
    ['жизни', 'life'],
    ['хиты', 'hits'],
    ['урон', 'damage'],
    ['ошибки', 'invalid_moves'],
  ];
  for (const [label, key] of details) {
    const value = numericFrameValue(player[key]);
    if (key === 'points' && score !== null && (scoreSource === 'points' || value === score)) continue;
    if (value !== null) {
      parts.push(`${label} ${scoreLabel(value)}`);
    }
  }

  return parts.length ? parts.join(' · ') : 'пока нет';
}

function framePlayerMetaLabel(player: Record<string, unknown>): string {
  const parts: string[] = [];
  const details: Array<[string, string]> = [
    ['позиция', 'position'],
    ['роль', 'role'],
  ];
  for (const [label, key] of details) {
    const value = player[key];
    if (typeof value === 'string' && value) parts.push(`${label}: ${value}`);
  }
  return parts.join(' · ');
}

function isRunStatus(value: unknown): value is RunDto['status'] {
  return typeof value === 'string'
    && ['created', 'queued', 'running', 'finished', 'failed', 'timeout', 'canceled'].includes(value);
}

function handleEmbeddedGameFrameMessage(event: MessageEvent): void {
  if (event.origin !== window.location.origin) return;
  const data = event.data;
  if (!isRecord(data) || data.type !== 'agp.watch.frame' || !isRecord(data.payload)) return;
  const payload = data.payload;
  if (typeof payload.runId !== 'string') return;

  embeddedGameFrame.value = {
    runId: payload.runId,
    status: isRunStatus(payload.status) ? payload.status : 'running',
    tick: typeof payload.tick === 'number' && Number.isFinite(payload.tick) ? payload.tick : 0,
    phase: typeof payload.phase === 'string' ? payload.phase : '',
    frame: payload.frame ?? {},
    replayFrameIndex: typeof payload.replayFrameIndex === 'number' ? payload.replayFrameIndex : 0,
    replayFrameCount: typeof payload.replayFrameCount === 'number' ? payload.replayFrameCount : 0,
    firstShowActive: payload.firstShowActive === true,
    firstShowWaiting: payload.firstShowWaiting === true,
    participants: Array.isArray(payload.participants)
      ? payload.participants.filter(isEmbeddedParticipant)
      : [],
    players: Array.isArray(payload.players)
      ? payload.players.filter(isEmbeddedPlayerStat)
      : [],
  };
}

function isEmbeddedPlayerStat(value: unknown): value is EmbeddedGamePlayerStat {
  return isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    typeof value.team_id === 'string' &&
    (typeof value.score === 'number' || value.score === null) &&
    typeof value.score_label === 'string' &&
    typeof value.life_percent === 'number' &&
    typeof value.shield_percent === 'number' &&
    typeof value.alive === 'boolean' &&
    typeof value.is_self === 'boolean' &&
    typeof value.detail_label === 'string';
}

function isEmbeddedParticipant(value: unknown): value is EmbeddedGameFrame['participants'][number] {
  return isRecord(value) &&
    typeof value.run_id === 'string' &&
    typeof value.team_id === 'string' &&
    typeof value.display_name === 'string' &&
    typeof value.captain_user_id === 'string' &&
    typeof value.is_current === 'boolean';
}

function isTerminalRunStatus(status: string | null | undefined): boolean {
  return Boolean(status && ['finished', 'failed', 'timeout', 'canceled'].includes(status));
}

function isResolvedCompetitionMatch(match: CompetitionMatchDto): boolean {
  return ['finished', 'auto_advanced', 'awaiting_tiebreak'].includes(match.status) || match.advanced_team_ids.length > 0;
}

function effectiveCompetitionMatchStatus(match: CompetitionMatchDto): CompetitionMatchStatus {
  if (activeCompetition.value?.presentation_mode === 'sequential') return match.status;
  if (match.status !== 'running') return match.status;
  const runIds = Object.values(match.run_ids_by_team);
  if (!runIds.length) return match.status;
  const allTerminal = runIds.every((runId) => isTerminalRunStatus(competitionRunsById.value[runId]?.status));
  return allTerminal ? 'finished' : match.status;
}

function competitionMatchHasWatchableRun(match: CompetitionMatchDto): boolean {
  if (match.status === 'pending' || match.status === 'auto_advanced') return false;
  return Object.values(match.run_ids_by_team).some(Boolean);
}

function isCompetitionMatchLoser(match: CompetitionMatchDto, teamId: string): boolean {
  return isResolvedCompetitionMatch(match) && !match.advanced_team_ids.includes(teamId);
}

function competitionTeamMatchSummary(match: CompetitionMatchDto, teamId: string): string {
  const score = match.scores_by_team[teamId];
  const placement = match.placements_by_team[teamId];
  const parts: string[] = [];
  if (score !== undefined) parts.push(`очки ${scoreLabel(score)}`);
  if (placement !== undefined) parts.push(`место ${placement}`);
  if (match.advanced_team_ids.includes(teamId)) parts.push('победа');
  else if (isCompetitionMatchLoser(match, teamId)) parts.push('поражение');
  else {
    const runStatus = competitionRunsById.value[match.run_ids_by_team[teamId] ?? '']?.status;
    parts.push(isTerminalRunStatus(runStatus) ? 'завершил' : 'играет');
  }
  return parts.join(' · ');
}

function competitionMatchStatusLabel(status: CompetitionMatchStatus): string {
  const labels: Record<CompetitionMatchStatus, string> = {
    pending: 'ожидает',
    running: 'играют',
    finished: 'завершен',
    awaiting_tiebreak: 'нужен тай-брейк',
    auto_advanced: 'автопроход',
  };
  return labels[status];
}

function competitionRoundStatusLabel(status: CompetitionRoundStatus): string {
  const labels: Record<CompetitionRoundStatus, string> = {
    running: 'идет',
    finished: 'завершен',
  };
  return labels[status];
}

function competitionStatusLabel(status: CompetitionStatus | string): string {
  const labels: Record<string, string> = {
    draft: 'черновик',
    running: 'идет',
    paused: 'пауза',
    completed: 'победитель определен',
    finished: 'завершено',
  };
  return labels[status];
}

function clearCodeAutosave(): void {
  if (!codeAutosaveHandle) return;
  clearTimeout(codeAutosaveHandle);
  codeAutosaveHandle = null;
}

function codeDraftKey(teamId: string, slotKey: string): string {
  return [
    CODE_DRAFT_STORAGE_PREFIX,
    sessionStore.sessionId || 'anonymous',
    teamId,
    slotKey,
  ].join(':');
}

function readCodeDraft(teamId: string, slotKey: string): string | null {
  try {
    return localStorage.getItem(codeDraftKey(teamId, slotKey));
  } catch {
    return null;
  }
}

function writeCodeDraft(teamId: string, slotKey: string, code: string): void {
  try {
    localStorage.setItem(codeDraftKey(teamId, slotKey), code);
  } catch {
    // Autosave is still attempted through the API; local draft is best effort.
  }
}

function clearCodeDraft(teamId: string, slotKey: string): void {
  try {
    localStorage.removeItem(codeDraftKey(teamId, slotKey));
  } catch {
    // Ignore storage errors.
  }
}

function persistCurrentCodeDraft(): void {
  const teamId = codeWorkspaceTeamId.value;
  const slotKey = activeSlotKey.value;
  if (!teamId || !slotKey || !canEditSelectedCode.value || editorCode.value === savedCode.value) return;
  writeCodeDraft(teamId, slotKey, editorCode.value);
}

async function persistCode(slotKey: string, code: string): Promise<void> {
  const teamId = codeWorkspaceTeamId.value;
  if (!teamId || !slotKey || !canEditSelectedCode.value) return;
  isSavingCode.value = true;
  errorMessage.value = '';
  try {
    await updateSlotCode({
      team_id: teamId,
      slot_key: slotKey,
      actor_user_id: sessionStore.nickname,
      code,
    });
    const slot = workspace.value?.slot_states.find((item) => item.slot_key === slotKey);
    if (slot) {
      slot.code = code;
      const fresh = await getWorkspace(teamId);
      const freshSlot = fresh.slot_states.find(item => item.slot_key === slotKey);
      if (freshSlot) { slot.updated_at = freshSlot.updated_at; slot.revision = freshSlot.revision; }
    }
    if (activeSlotKey.value === slotKey) savedCode.value = code;
    clearCodeDraft(teamId, slotKey);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось сохранить код';
  } finally {
    isSavingCode.value = false;
  }
}

async function flushCodeAutosave(): Promise<void> {
  clearCodeAutosave();
  if (!canAutosaveCode.value) return;
  await persistCode(activeSlotKey.value, editorCode.value);
}

function scheduleCodeAutosave(): void {
  clearCodeAutosave();
  if (!canAutosaveCode.value) return;
  persistCurrentCodeDraft();
  codeAutosaveHandle = setTimeout(() => {
    void flushCodeAutosave();
  }, 900);
}

function flushCodeAutosaveOnPageHide(): void {
  clearCodeAutosave();
  persistCurrentCodeDraft();
  const teamId = codeWorkspaceTeamId.value;
  const slotKey = activeSlotKey.value;
  if (!teamId || !slotKey || !canAutosaveCode.value) return;
  updateSlotCodeKeepalive({
    team_id: teamId,
    slot_key: slotKey,
    actor_user_id: sessionStore.nickname,
    code: editorCode.value,
  });
}

async function selectSlot(slotKey: string): Promise<void> {
  await flushCodeAutosave();
  const slot = slotStates.value.find((item) => item.slot_key === slotKey);
  const serverCode = slot?.code ?? '';
  const teamId = codeWorkspaceTeamId.value;
  const draftCode = teamId ? readCodeDraft(teamId, slotKey) : null;
  if (teamId && draftCode !== null && draftCode === serverCode) {
    clearCodeDraft(teamId, slotKey);
  }
  isHydratingEditor.value = true;
  activeSlotKey.value = slotKey;
  editorCode.value = draftCode ?? serverCode;
  savedCode.value = serverCode;
  requestAnimationFrame(() => {
    isHydratingEditor.value = false;
    if (draftCode !== null && draftCode !== serverCode) scheduleCodeAutosave();
  });
}

function applyTemplate(): void {
  if (!activeTemplate.value) return;
  replacementUndo.value = editorCode.value;
  editorCode.value = activeTemplate.value;
}

function applyDemoStrategy(): void {
  if (!canUseDemoStrategy.value) return;
  if (!activeDemoStrategy.value) return;
  replacementUndo.value = editorCode.value;
  editorCode.value = activeDemoStrategy.value.code;
}

async function addDemoBot(): Promise<void> {
  if (!lobby.value || !canAddBot.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await addLobbyDemoBot(lobby.value.lobby_id);
    refreshTrainingRunsWhenChanged(lobby.value);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось добавить бота';
  } finally {
    isBusy.value = false;
  }
}

async function openPlayerCode(stat: LobbyParticipantStatsDto): Promise<void> {
  if (!canManage.value) return;
  await flushCodeAutosave();
  selectedCodeTeamId.value = stat.team_id;
  activeSlotKey.value = '';
  editorCode.value = '';
  savedCode.value = '';
  workspace.value = null;
  showPlayerCodeDialog.value = true;
  await refreshWorkspace();
}

async function closePlayerCodeDialog(): Promise<void> {
  await flushCodeAutosave();
  showPlayerCodeDialog.value = false;
  selectedCodeTeamId.value = '';
  activeSlotKey.value = '';
  editorCode.value = '';
  savedCode.value = '';
  await refreshWorkspace();
}

async function removeTeamFromLobby(stat: LobbyParticipantStatsDto): Promise<void> {
  if (!lobby.value || !canUseAdminBots.value) return;
  if (!confirm(`Удалить игрока "${stat.display_name}" из лобби?`)) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await leaveLobby({ lobby_id: lobby.value.lobby_id, team_id: stat.team_id });
    await refreshTrainingRuns();
    await refreshCompetitions();
    if (workspace.value?.team_id === stat.team_id) {
      showPlayerCodeDialog.value = false;
      selectedCodeTeamId.value = '';
      await refreshWorkspace();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось удалить игрока из лобби';
  } finally {
    isBusy.value = false;
  }
}

async function refreshWorkspace(): Promise<void> {
  const teamId = codeWorkspaceTeamId.value;
  if (!teamId) {
    workspace.value = null;
    activeSlotKey.value = '';
    editorCode.value = '';
    savedCode.value = '';
    return;
  }
  workspace.value = await getWorkspace(teamId);
  if (!activeSlotKey.value && workspace.value.slot_states[0]) {
    await selectSlot(workspace.value.slot_states[0].slot_key);
  } else if (activeSlotKey.value) {
    const slot = workspace.value.slot_states.find((item) => item.slot_key === activeSlotKey.value);
    const wasDirty = isDirty.value;
    const serverCode = slot?.code ?? '';
    const draftCode = readCodeDraft(teamId, activeSlotKey.value);
    if (draftCode !== null && draftCode === serverCode) {
      clearCodeDraft(teamId, activeSlotKey.value);
    }
    savedCode.value = serverCode;
    if (!wasDirty) {
      isHydratingEditor.value = true;
      editorCode.value = draftCode ?? serverCode;
      requestAnimationFrame(() => {
        isHydratingEditor.value = false;
        if (draftCode !== null && draftCode !== serverCode) scheduleCodeAutosave();
      });
    }
  }
}

async function refreshCompetitions(): Promise<void> {
  if (!lobby.value) return;
  const lobbyIdValue = lobby.value.lobby_id;
  const refreshId = ++competitionRefreshSequence;
  const competitions = await listCompetitions({ lobby_id: lobbyIdValue });
  if (refreshId !== competitionRefreshSequence || lobby.value?.lobby_id !== lobbyIdValue) return;
  const nextActiveCompetition =
    competitions.find(
      (item) => item.lobby_id === lobbyIdValue && item.status !== 'finished',
    ) ?? null;
  const nextCompetitionRuns = nextActiveCompetition
    ? await listCompetitionRuns(nextActiveCompetition.competition_id)
    : [];
  if (refreshId !== competitionRefreshSequence || lobby.value?.lobby_id !== lobbyIdValue) return;
  const archive = await listLobbyCompetitionArchive(lobbyIdValue);
  if (refreshId !== competitionRefreshSequence || lobby.value?.lobby_id !== lobbyIdValue) return;
  activeCompetition.value = nextActiveCompetition;
  competitionRuns.value = nextCompetitionRuns;
  competitionArchive.value = archive.items;
  if (activeCompetition.value && activeTab.value === 'competition') {
    await router.replace({ name: 'competition', params: { competitionId: activeCompetition.value.competition_id } });
  }
  if (!activeCompetition.value && activeTab.value === 'competition') {
    activeTab.value = competitionArchive.value.length ? 'archive' : 'lobby';
  }
}

async function refreshTrainingRuns(): Promise<void> {
  if (isRefreshingTrainingRuns) {
    pendingTrainingRunsRefresh = true;
    return;
  }
  isRefreshingTrainingRuns = true;
  try {
    do {
      pendingTrainingRunsRefresh = false;
      const lobbyIdValue = lobby.value?.lobby_id;
      if (!lobbyIdValue) break;
      const runs = await listRuns({
        lobby_id: lobbyIdValue,
        run_kind: 'training_match',
      });
      if (lobby.value?.lobby_id === lobbyIdValue) {
        trainingRuns.value = runs;
      }
    } while (pendingTrainingRunsRefresh);
  } catch {
    // Keep the latest known run details; lobby state itself is still useful.
  } finally {
    isRefreshingTrainingRuns = false;
  }
}

function lobbyRunsSignature(nextLobby: LobbyDto | null): string {
  if (!nextLobby) return '';
  const groupSignature = [...nextLobby.current_match_groups, ...nextLobby.archived_match_groups]
    .map((group) => [
      group.group_id,
      group.status,
      group.run_ids.join(','),
      group.winner_team_ids.join(','),
      Object.entries(group.scores_by_team)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([teamId, score]) => `${teamId}=${score}`)
        .join(','),
    ].join(':'))
    .join('|');
  return [
    nextLobby.current_run_id ?? '',
    nextLobby.cycle_phase,
    nextLobby.current_run_ids.join(','),
    nextLobby.archived_run_ids.join(','),
    groupSignature,
  ].join('::');
}

function refreshTrainingRunsWhenChanged(nextLobby: LobbyDto | null): void {
  const signature = lobbyRunsSignature(nextLobby);
  if (signature === trainingRunsRefreshSignature.value) return;
  trainingRunsRefreshSignature.value = signature;
  void refreshTrainingRuns();
}

async function loadLobby(): Promise<void> {
  const id = lobbyId();
  joinRequired.value = false;
  try {
    lobby.value = await getLobby(id);
    if (!canManage.value && !lobby.value.my_team_id && activeTab.value !== 'game' && lobby.value.teams.length < lobby.value.max_teams && ['open', 'running', 'draft'].includes(lobby.value.status)) lobby.value = await joinLobbyAsUser({ lobby_id: id, access_code: lobbyAccessCode.value.trim() || null });
  } catch (error) {
    if (!canManage.value && lobbyAccessCode.value.trim()) {
      lobby.value = await joinLobbyAsUser({ lobby_id: id, access_code: lobbyAccessCode.value.trim() });
      lobbyAccessCode.value = '';
    } else if (!canManage.value && error instanceof Error && (error.message.includes('код') || error.message.includes('403'))) {
      joinRequired.value = true; lobby.value = null; return;
    } else throw error;
  }
  game.value = await getGame(lobby.value.game_id);
  competitionMatchSize.value = competitionMaxMatchSize.value;
  clampCompetitionSettingsToGame();
  templates.value = await getGameTemplates(lobby.value.game_id);
  docs.value = await getGameDocs(lobby.value.game_id);
  await refreshWorkspace();
  trainingRunsRefreshSignature.value = lobbyRunsSignature(lobby.value);
  await refreshTrainingRuns();
  await refreshCompetitions();
  if (!canSeeCodeTab.value && activeTab.value === 'code') {
    activeTab.value = 'lobby';
  }
}

async function refreshLobbyOnly(options: { forceRuns?: boolean; refreshCompetitions?: boolean } = {}): Promise<void> {
  if (!lobby.value) return;
  const refreshId = ++lobbyRefreshSequence;
  const nextLobby = await getLobby(lobby.value.lobby_id);
  if (refreshId !== lobbyRefreshSequence) return;
  lobby.value = nextLobby;
  if (options.forceRuns) {
    trainingRunsRefreshSignature.value = lobbyRunsSignature(lobby.value);
    await refreshTrainingRuns();
  } else {
    refreshTrainingRunsWhenChanged(lobby.value);
  }
  if (options.refreshCompetitions !== false) {
    await refreshCompetitions();
  }
}

async function submitLobbyAccessCode(): Promise<void> {
  if (!lobbyAccessCode.value || isBusy.value) return;
  isBusy.value = true;
  isLoading.value = true;
  errorMessage.value = '';
  try {
    await loadLobby();

    if (!canSeeCodeTab.value && activeTab.value === 'code') {
      activeTab.value = 'lobby';
    }
    if (lobby.value) {
      startLiveUpdates();
      startCompetitionPolling();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось войти в лобби';
  } finally {
    isBusy.value = false;
    isLoading.value = false;
  }
}

async function saveCode(): Promise<void> {
  if (!codeWorkspaceTeamId.value || !activeSlotKey.value) return;
  clearCodeAutosave();
  await persistCode(activeSlotKey.value, editorCode.value);
  await refreshWorkspace();
}

const canJoinAsPlayer = computed(() =>
  Boolean(
    lobby.value &&
      canManage.value &&
      !lobby.value.my_team_id &&
      ['draft', 'open', 'running'].includes(lobby.value.status) &&
      lobby.value.teams.length < lobby.value.max_teams &&
      !activeCompetition.value,
  ),
);
async function joinAsPlayer(): Promise<void> {
  if (!lobby.value || !canJoinAsPlayer.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await joinLobbyAsUser({ lobby_id: lobby.value.lobby_id, access_code: null });
    selectedCodeTeamId.value = '';
    activeSlotKey.value = '';
    editorCode.value = '';
    savedCode.value = '';
    workspace.value = null;
    await refreshWorkspace();
    activeTab.value = 'code';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось присоединиться как игрок';
  } finally {
    isBusy.value = false;
  }
}

async function leaveAsPlayer(): Promise<void> {
  if (!lobby.value || !lobby.value.my_team_id || !canLeaveAsPlayer.value) return;
  if (!confirm(canManage.value ? 'Прекратить участие как игрок?' : 'Выйти из лобби?')) return;
  await flushCodeAutosave();
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await leaveLobby({ lobby_id: lobby.value.lobby_id, team_id: lobby.value.my_team_id });
    selectedCodeTeamId.value = '';
    activeSlotKey.value = '';
    workspace.value = null;
    editorCode.value = '';
    savedCode.value = '';
    if (activeTab.value === 'code') activeTab.value = 'lobby';
    if (!canManage.value) {
      await router.push('/lobbies');
      return;
    }
    await refreshTrainingRuns();
    await refreshCompetitions();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось прекратить участие';
  } finally {
    isBusy.value = false;
  }
}

async function startLobbyByTeacher(): Promise<void> {
  if (!lobby.value || !canManage.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await setLobbyStatus({ lobby_id: lobby.value.lobby_id, status: 'open' });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось запустить лобби';
  } finally {
    isBusy.value = false;
  }
}

async function pauseLobbyByTeacher(): Promise<void> {
  if (!lobby.value || !canManage.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await setLobbyStatus({ lobby_id: lobby.value.lobby_id, status: 'paused' });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось поставить лобби на паузу';
  } finally {
    isBusy.value = false;
  }
}

async function stopLobbyByTeacher(): Promise<void> {
  if (!lobby.value || !canStopLobbyByTeacher.value) return;
  if (!confirm('Остановить лобби? Очередь очистится, новые матчи не будут запускаться до повторного запуска.')) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await setLobbyStatus({ lobby_id: lobby.value.lobby_id, status: 'stopped' });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось остановить лобби';
  } finally {
    isBusy.value = false;
  }
}

async function saveLobbySettings(): Promise<void> {
  if (!lobby.value || !canSaveLobbySettings.value) return;
  isSavingLobbySettings.value = true;
  errorMessage.value = '';
  try {
    const payload = lobbySettingsPayload.value;
    lobby.value = await updateLobby({
      lobby_id: lobby.value.lobby_id,
      title: payload.title,
      access: payload.access,
      access_code: payload.access_code,
      max_teams: payload.max_teams,
    });
    lobbySettingsTouched.value = false;
    syncLobbySettings(true);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось сохранить настройки лобби';
  } finally {
    isSavingLobbySettings.value = false;
  }
}

async function deleteLobbyByTeacher(): Promise<void> {
  if (!lobby.value || !canDeleteLobby.value) return;
  if (!confirm('Удалить лобби вместе с тренировочными матчами? Это действие нельзя отменить.')) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    await deleteLobby(lobby.value.lobby_id);
    await router.push('/lobbies');
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось удалить лобби';
  } finally {
    isBusy.value = false;
  }
}

async function play(): Promise<void> {
  if (!lobby.value || isBusy.value || !canUseTrainingQueue.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    await flushCodeAutosave();
    if (isDirty.value) throw new Error('Не удалось сохранить код');
    lobby.value = await playLobby({ lobby_id: lobby.value.lobby_id });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось встать в очередь';
  } finally {
    isBusy.value = false;
  }
}

async function stop(): Promise<void> {
  if (!lobby.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await stopLobby(lobby.value.lobby_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось остановить участие';
  } finally {
    isBusy.value = false;
  }
}

async function startCompetitionFromLobby(): Promise<void> {
  if (!lobby.value) return;
  clampCompetitionSettingsToGame();
  isBusy.value = true;
  try {
    const competition = await startLobbyCompetition({
      lobby_id: lobby.value.lobby_id,
      title: `${lobby.value.title} / соревнование`,
      participant_selection: competitionRosterMode.value,
      team_ids: competitionSelectedTeams.value,
      tie_break_policy: competitionTieBreakPolicy.value,
      code_policy: competitionCodePolicy.value,
      presentation_mode: competitionPresentationMode.value,
      advancement_top_k: Math.max(1, Math.min(competitionAdvanceTopK.value, competitionMatchSize.value)),
      match_size: Math.max(
        competitionMinMatchSize.value,
        Math.min(competitionMaxMatchSize.value, competitionMatchSize.value),
      ),
    });
    await refreshLobbyOnly();
    showCompetitionDialog.value = false;
    await router.push({ name: 'competition', params: { competitionId: competition.competition_id } });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось начать соревнование';
  } finally {
    isBusy.value = false;
  }
}

function startLiveUpdates(): void {
  stopLiveUpdates();
  if (!lobby.value || typeof EventSource === 'undefined') {
    startPolling();
    return;
  }
  const sse = createResilientSSE({
    url: `/api/v1/lobbies/${encodeURIComponent(lobby.value.lobby_id)}/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`,
    onOpen(source) {
      source.addEventListener('agp.update', (event: MessageEvent) => {
        try {
          const envelope = JSON.parse(event.data) as StreamEnvelopeDto<LobbyDto>;
          if (envelope.channel !== 'lobby' || !envelope.payload) return;
          lobby.value = envelope.payload;
          refreshTrainingRunsWhenChanged(lobby.value);
        } catch {
          // Keep last valid snapshot.
        }
      });
    },
    onFallbackToPolling() {
      startPolling();
    },
  });
  lobbyEventSource = sse as unknown as EventSource;
}

function startCompetitionPolling(): void {
  stopCompetitionPolling();
  competitionPollingHandle = setInterval(() => {
    refreshCompetitions().catch(() => {
      // Keep the last known bracket; the next polling tick can recover.
    });
  }, 10000);
}

function stopCompetitionPolling(): void {
  if (!competitionPollingHandle) return;
  clearInterval(competitionPollingHandle);
  competitionPollingHandle = null;
}

function startPolling(): void {
  if (pollingHandle) return;
  pollingHandle = setInterval(() => {
    refreshLobbyOnly({ refreshCompetitions: false }).catch(() => {
      // Keep the latest useful lobby snapshot while the network is unstable.
    });
  }, 5000);
}

function stopLiveUpdates(): void {
  if (lobbyEventSource) {
    (lobbyEventSource as unknown as { close: () => void }).close();
    lobbyEventSource = null;
  }
  if (pollingHandle) {
    clearInterval(pollingHandle);
    pollingHandle = null;
  }
}

watch(
  () => codeWorkspaceTeamId.value,
  () => {
    void refreshWorkspace();
  }
);

watch(
  () => currentGameRunId.value,
  (runId) => {
    const frameRunId = embeddedGameFrame.value?.runId ?? '';
    if (frameRunId && frameRunId !== runId && !displayedTrainingRunIds.value.includes(frameRunId)) {
      embeddedGameFrame.value = null;
    }
    if (runId) lastGameRunId.value = runId;
  }
);

watch(
  displayedGameWatchKeySource,
  (watchKey) => {
    const runId = displayedGameRunId.value;
    if (!runId) {
      displayedGameWatchKey.value = '';
      displayedGameWatchUrl.value = '';
      return;
    }
    if (displayedGameWatchKey.value === watchKey && displayedGameWatchUrl.value) return;
    displayedGameWatchKey.value = watchKey;
    displayedGameWatchUrl.value = buildDisplayedGameWatchUrl(runId);
  },
  { immediate: true },
);

watch(editorCode, () => {
  if (isHydratingEditor.value) return;
  scheduleCodeAutosave();
});

watch(activeTab, (nextTab, previousTab) => {
  const tab = nextTab === 'lobby' ? undefined : nextTab;
  const clearMatch = nextTab === 'code' && route.query.match !== undefined;
  if (route.query.tab !== tab || clearMatch) void router.replace({ query: { ...route.query, tab, ...(nextTab === 'code' ? { match: undefined } : {}) } });
  if (nextTab === 'code' && previousTab !== 'code') {
    editorReferenceOpenedAutomatically.value = !editorGameRunId.value;
    rulesOpen.value = editorReferenceOpenedAutomatically.value;
    lobbyMobilePane.value = 'code';
  }
  if (previousTab === 'code') void flushCodeAutosave();
}, { immediate: true });

watch(editorGameRunId, runId => {
  if (runId && editorReferenceOpenedAutomatically.value) {
    editorReferenceOpenedAutomatically.value = false;
    rulesOpen.value = false;
  }
});

watch(
  () => canSeeCodeTab.value,
  (canSeeCode) => {
    if (!canSeeCode && activeTab.value === 'code') {
      activeTab.value = 'lobby';
    }
  },
);

onBeforeRouteLeave(async () => {
  await flushCodeAutosave();
});

function handlePageVisibilityChange(): void {
  if (document.visibilityState === 'hidden') { flushCodeAutosaveOnPageHide(); stopLiveUpdates(); }
  else { void refreshLobbyOnly(); startLiveUpdates(); }
}

onMounted(async () => {
  window.addEventListener('message', handleEmbeddedGameFrameMessage);
  window.addEventListener('pagehide', flushCodeAutosaveOnPageHide);
  document.addEventListener('visibilitychange', handlePageVisibilityChange);
  isLoading.value = true;
  errorMessage.value = '';
  try {
    await loadLobby();

    if (lobby.value) {
      startLiveUpdates();
      startCompetitionPolling();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось открыть лобби';
  } finally {
    isLoading.value = false;
  }
});

onUnmounted(() => {
  flushCodeAutosaveOnPageHide();
  window.removeEventListener('message', handleEmbeddedGameFrameMessage);
  window.removeEventListener('pagehide', flushCodeAutosaveOnPageHide);
  document.removeEventListener('visibilitychange', handlePageVisibilityChange);
  stopLiveUpdates();
  stopCompetitionPolling();
});

const lobbyMenuItems = computed<ActionMenuItem[]>(() => {
  const items: ActionMenuItem[] = [];
  if (canManage.value) items.push({ id: 'settings', label: 'Настройки лобби', disabled: isBusy.value });
  if (canManage.value && canSeeCodeTab.value) items.push({ id: 'code', label: 'Мой код' });
  if (canManage.value && !hasPlayerInLobby.value) items.push({ id: 'join', label: 'Участвовать как игрок', disabled: !canJoinAsPlayer.value || isBusy.value });
  if (!activeCompetition.value && canStartLobby.value) items.push({ id: 'resume', label: 'Возобновить подбор', disabled: isBusy.value });
  if (!activeCompetition.value && canStopLobbyByTeacher.value) items.push({ id: 'stop', label: 'Остановить тренировку', danger: true, disabled: isBusy.value });
  if (canDeleteLobby.value) items.push({ id: 'delete', label: 'Удалить лобби', danger: true, disabled: isBusy.value });
  if (canLeaveAsPlayer.value) items.push({ id: 'leave', label: 'Выйти из лобби', danger: true, disabled: isBusy.value });
  return items;
});
function handleLobbyMenu(action: string): void {
  if (action === 'settings') showLobbySettingsDialog.value = true;
  if (action === 'code') activeTab.value = 'code';
  if (action === 'resume') void startLobbyByTeacher();
  if (action === 'join') void joinAsPlayer();
  if (action === 'pause') void pauseLobbyByTeacher();
  if (action === 'stop') void stopLobbyByTeacher();
  if (action === 'delete') void deleteLobbyByTeacher();
  if (action === 'leave') void leaveAsPlayer();
}
</script>

<style scoped>


.lobby-page {
  min-height: 0;
  gap: 16px;
  align-content: start;
  grid-auto-rows: max-content;
  padding: 0;
  background-color: var(--agp-bg);
  background-image: none;
  background-size: 160px 160px, auto, auto, auto;
}

.lobby-page--game {
  gap: 0;
  background-color: var(--agp-surface);
  background-image: none;
}

.lobby-page > :not(.lobby-head) {
  margin-inline: 0.6rem;
}

.lobby-page--game > :not(.lobby-head) {
  margin-inline: 0;
}

.lobby-editor-toolbar,
.lobby-access-card,
.lobby-access-form {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.lobby-access-card {
  justify-content: space-between;
  background: var(--agp-surface-soft);
}

.lobby-access-form {
  min-width: min(100%, 24rem);
}

.lobby-access-form input {
  max-width: 14rem;
}

.lobby-competition-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
}
.lobby-competition-banner > div { min-width: 0; }
.lobby-competition-banner strong { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; font-size: 14px; line-height: 20px; }
.lobby-competition-banner > a { flex: none; white-space: nowrap; }

.lobby-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  place-items: center;
  overflow-y: auto;
  padding: 16px;
  background: rgba(15, 23, 42, 0.32);
  backdrop-filter: blur(3px);
}

.lobby-competition-dialog,
.lobby-settings-dialog,
.lobby-player-code-dialog {
  width: min(100%, 28rem);
  max-height: calc(100dvh - 32px);
  overflow-y: auto;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 0.7rem;
  background: var(--agp-surface);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.24);
  padding: 1rem;
}

.lobby-settings-dialog {
  width: min(100%, 34rem);
}

.lobby-player-code-dialog {
  width: min(100%, 78rem);
  max-height: calc(100dvh - 32px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.lobby-dialog-head,
.lobby-dialog-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.lobby-dialog-head {
  align-items: center;
  margin-bottom: 16px;
}

.lobby-dialog-close {
  flex: none;
  width: 2rem;
  height: 2rem;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--agp-surface);
  color: var(--agp-text-muted);
  font-size: 1.2rem;
  line-height: 1;
}

.lobby-dialog-actions {
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

.lobby-code-layout,
.lobby-game-layout {
  display: grid;
  grid-template-columns: minmax(13rem, 17rem) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: start;
}

.lobby-code-layout {
  align-items: start;
}

.lobby-code-layout--modal {
  min-height: 34rem;
  overflow: hidden;
}

.lobby-code-layout--modal .lobby-roles,
.lobby-code-layout--modal .lobby-editor {
  min-height: 0;
}

.lobby-code-layout--modal .lobby-editor {
  display: flex;
  flex-direction: column;
}

.lobby-code-layout--modal :deep(.cm-editor) {
  min-height: 28rem;
}

.lobby-game-layout {
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 23rem);
  gap: 0;
  align-items: stretch;
  height: calc(100dvh - 3.35rem);
  min-height: 0;
}

.lobby-roles,
.lobby-editor,
.lobby-match-list,
.lobby-stats-list {
  display: grid;
  gap: 0.5rem;
}

.lobby-roles,
.lobby-editor {
  position: relative;
  overflow: hidden;
  border-color: var(--agp-border);
  background: var(--agp-surface);
  color: var(--agp-text);
  box-shadow: none;
}

.lobby-roles::before,
.lobby-editor::before {
  content: none;
}

.lobby-roles-head {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 0.55rem;
  margin-bottom: 0.5rem;
}

.lobby-roles-head > div:first-child {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
}

.lobby-roles-head span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-role-progress {
  height: 0.42rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--agp-border);
}

.lobby-role-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--agp-primary);
  box-shadow: none;
}

.lobby-role-button {
  position: relative;
  z-index: 1;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 0.55rem;
  background: var(--agp-surface);
  color: var(--agp-text);
  padding: 0.55rem 0.65rem;
  display: grid;
  gap: 0.1rem;
  text-align: left;
}

.lobby-role-button.active {
  border-color: var(--agp-border);
  background: var(--agp-surface);
  box-shadow: none;
}

.lobby-role-button span {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.lobby-role-button span i {
  width: 0.58rem;
  height: 0.58rem;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: none;
}

.lobby-role-button.filled span i {
  background: #14b8a6;
  box-shadow: none;
}

.lobby-role-button span {
  font-weight: 700;
}

.lobby-role-button small,
.lobby-stat-row span {
  color: var(--agp-text-muted);
}

.lobby-role-button small {
  color: var(--agp-text-muted);
}

.lobby-settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.lobby-competition-setting {
  display: grid;
  align-content: start;
  gap: 4px;
  min-width: 0;
  font-size: 0.78rem;
  color: var(--agp-text-muted);
}

.lobby-editor-toolbar {
  position: relative;
  z-index: 1;
  justify-content: space-between;
  margin-bottom: 0.65rem;
}

.lobby-editor-toolbar h2,
.lobby-editor-toolbar h3 {
  color: var(--agp-text);
}

.lobby-editor-toolbar p {
  color: var(--agp-text-muted);
}

.lobby-editor-toolbar .btn-outline-secondary {
  border-color: var(--agp-border);
  background: var(--agp-surface);
  color: var(--agp-text-muted);
}

.lobby-editor-toolbar .btn-outline-secondary:hover:not(:disabled) {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
  color: var(--agp-text);
}

.lobby-editor-toolbar .btn-dark {
  border: 0;
  background: var(--agp-action);
  color: var(--arena-on-primary);
  box-shadow: none;
}

.lobby-competition-settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 12px;
}

.lobby-competition-setting--wide {
  grid-column: 1 / -1;
}

.lobby-match-row,
.lobby-stat-row {
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  padding: 0.55rem 0.65rem;
  display: grid;
  gap: 0.1rem;
  text-decoration: none;
  color: inherit;
}

.lobby-game-layout .lobby-stat-row {
  padding: 0.45rem 0.55rem;
  font-size: 0.86rem;
}

.lobby-game-layout .lobby-stat-row span {
  font-size: 0.78rem;
}

.lobby-match-row {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.lobby-match-row > span {
  display: grid;
  gap: 0.05rem;
  min-width: 0;
}

.lobby-match-row.muted {
  background: var(--agp-surface-soft);
}

.lobby-match-pagination {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.lobby-match-pagination {
  justify-content: space-between;
  margin-top: 0.65rem;
}

.lobby-game-view {
  position: relative;
  min-height: 0;
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: var(--agp-surface);
  box-shadow: none;
}

.lobby-game-view iframe {
  width: 100%;
  height: 100%;
  min-height: 0;
  border: 0;
  border-radius: 0;
}

.lobby-game-finished-overlay {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: grid;
  place-items: center;
  background: var(--agp-surface);
  backdrop-filter: blur(4px);
  pointer-events: none;
}

.lobby-game-finished-card {
  display: grid;
  gap: 0.25rem;
  text-align: center;
  padding: 1rem 1.5rem;
  border-radius: 0.6rem;
  background: var(--agp-surface);
  border: 1px solid rgba(135, 226, 255, 0.3);
  color: var(--agp-text);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
}

.lobby-game-finished-card strong {
  font-size: 1.1rem;
}

.lobby-game-finished-card small {
  color: var(--agp-text-muted);
}

.lobby-game-stats {
  min-height: 0;
  padding: 0.85rem;
  overflow: auto;
  border: 0;
  border-left: 1px solid rgba(34, 211, 238, 0.24);
  border-radius: 0;
  background: var(--agp-surface);
  color: var(--agp-text);
  box-shadow: none;
}

.lobby-game-stats .text-muted {
  color: var(--agp-text-muted) !important;
}

.lobby-game-stats-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.lobby-game-stats-head h2,
.lobby-game-stats-head strong {
  color: var(--agp-text);
}

.lobby-game-stats-head span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-game-run-select {
  display: grid;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
}

.lobby-game-run-select span {
  color: var(--agp-text-muted);
  font-size: 0.74rem;
  font-weight: 700;
}

.lobby-game-run-card {
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 8px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.05rem 0.55rem;
  align-items: center;
  background: var(--agp-surface);
  color: var(--agp-text);
  padding: 0.5rem 0.6rem;
  text-align: left;
}

.lobby-game-run-card:hover,
.lobby-game-run-card.active {
  border-color: var(--agp-border);
  background: var(--agp-surface);
}

.lobby-game-run-card i {
  grid-row: 1 / span 2;
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-style: normal;
  font-weight: 700;
  font-size: 0.78rem;
}

.lobby-game-run-card strong,
.lobby-game-run-card small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-game-run-card small {
  color: var(--agp-text-muted);
}

.lobby-game-mini-stats {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
}

.lobby-game-mini-stats div,
.lobby-game-empty-stat {
  border: 1px solid rgba(34, 211, 238, 0.16);
  border-radius: 8px;
  background: var(--agp-surface);
  padding: 0.55rem 0.65rem;
}

.lobby-game-mini-stats span {
  display: block;
  color: var(--agp-text-muted);
  font-size: 0.72rem;
}

.lobby-game-mini-stats strong {
  color: var(--agp-text);
}

.lobby-game-scoreboard {
  gap: 0.5rem;
}

.lobby-game-layout .lobby-stat-row {
  grid-template-columns: minmax(0, 1fr);
  gap: 0.3rem;
  border-color: var(--agp-border);
  border-radius: 8px;
  background: var(--agp-surface);
  color: var(--agp-text);
  min-width: 0;
}

.lobby-game-layout .lobby-stat-row--self {
  border-color: var(--agp-border);
  background: var(--agp-surface);
}

.lobby-stat-title {
  display: grid;
  gap: 0.05rem;
  min-width: 0;
}

.lobby-stat-title strong {
  overflow: hidden;
  color: var(--agp-text);
  overflow-wrap: anywhere;
  line-height: 1.15;
}

.lobby-stat-score {
  color: var(--agp-warning);
  font-weight: 700;
  line-height: 1.22;
  overflow-wrap: anywhere;
  text-align: left;
}

.lobby-stat-bars {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.3rem;
}

.lobby-stat-bars span {
  height: 0.32rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--agp-border);
}

.lobby-stat-bars i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.lobby-stat-bars span:first-child i {
  background: #22c55e;
}

.lobby-stat-bars span:last-child i {
  background: #38bdf8;
}

.lobby-game-layout .lobby-stat-row small {
  color: var(--agp-text-muted);
  overflow-wrap: anywhere;
}

.lobby-game-empty-stat {
  color: var(--agp-text-muted);
  font-size: 0.86rem;
}

.lobby-empty {
  height: 100%;
  min-height: 24rem;
  display: grid;
  place-content: center;
  gap: 0.25rem;
  border: 1px solid rgba(34, 211, 238, 0.12);
  background: var(--agp-surface);
  color: var(--agp-text);
  text-align: center;
}

.lobby-empty .text-muted {
  color: var(--agp-text-muted) !important;
}

@media (max-width: 980px) {
  .lobby-code-layout--single-slot .lobby-roles { display: none; }
  .lobby-code-layout,
  .lobby-game-layout {
    grid-template-columns: 1fr;
  }

  .lobby-game-layout {
    height: auto;
    min-height: 0;
  }

  .lobby-game-view iframe {
    height: 70dvh;
    min-height: 28rem;
  }

  .lobby-competition-settings-grid {
    grid-template-columns: 1fr;
  }
}


.arena-lobby-workbar{display:flex;align-items:center;gap:8px;grid-column:1/-1;min-height:44px}.arena-lobby-workbar h1{font-size:16px;line-height:24px;margin:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.arena-lobby-workbar>.small{font-size:11px;margin-right:8px}.lobby-page--workspace{height:calc(100dvh - 24px);grid-template-columns:minmax(0,52fr) minmax(0,48fr);grid-template-rows:auto minmax(0,1fr);gap:8px}.lobby-page--workspace>.lobby-code-layout{grid-column:1;grid-row:2;display:flex;min-height:0}.lobby-page--workspace .lobby-roles{display:none}.lobby-page--workspace .lobby-editor{padding:0!important;display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}.arena-lobby-editor-head{min-height:44px;border-bottom:1px solid var(--agp-border);margin:0;padding:6px 12px;display:flex}.arena-lobby-editor-head>strong{font-size:12px;font-weight:500}.arena-lobby-editor-head select{max-width:180px}.arena-lobby-editor-head details{margin-left:auto}.lobby-page--workspace .agp-code-editor{flex:1;min-height:0;overflow:hidden}.lobby-page--workspace :deep(.cm-editor){height:100%;min-height:0!important;border:0!important;border-radius:0!important}.lobby-page--workspace>.lobby-game-layout{grid-column:2;grid-row:2;display:flex;min-height:0}.lobby-page--workspace .lobby-game-stats{display:none}.lobby-page--workspace .lobby-game-view{flex:1;min-height:0;border:1px solid var(--agp-border);border-radius:10px;background:var(--agp-surface);overflow:hidden}.lobby-page--workspace .lobby-game-view>.agp-game-reference{height:100%;overflow:auto}.arena-file-menu{position:relative}.arena-file-menu summary{font-size:22px;padding:0 8px;list-style:none;cursor:pointer}.arena-file-menu>div{position:absolute;right:0;z-index:20;width:210px;background:var(--agp-surface);border:1px solid var(--agp-border);border-radius:8px;padding:8px;display:grid}.arena-file-menu button{background:none;border:0;color:var(--agp-text);text-align:left;padding:8px;font-size:13px}.arena-roster-picker{margin:0 0 16px;padding:0;border:0;display:grid;gap:8px}.arena-roster-picker legend{font-size:14px;font-weight:600}.arena-roster-picker label{display:flex;align-items:center;gap:8px;font-size:13px}.arena-roster-picker>div{max-height:180px;overflow:auto;display:grid;gap:8px;padding:8px;background:var(--agp-surface-soft);border-radius:6px}.lobby-competition-dialog{max-height:calc(100dvh - 32px);overflow:auto}
@media(max-width:900px){.lobby-page--workspace{height:auto;grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto auto}.lobby-page--workspace>.lobby-code-layout{grid-row:2;grid-column:1;height:58dvh}.lobby-page--workspace>.lobby-game-layout{grid-row:3;grid-column:1;height:48dvh}.arena-lobby-workbar{flex-wrap:wrap}.arena-lobby-workbar>.small{display:none}.arena-lobby-workbar .btn{font-size:12px;padding:6px 8px}}


.lobby-page.lobby-page--workspace{min-height:0;align-content:stretch}.lobby-page.lobby-page--workspace>:not(.lobby-head){margin-inline:0}.lobby-page--workspace>.lobby-code-layout{align-items:stretch}.lobby-page--workspace .lobby-editor{height:100%;background:var(--agp-surface);color:var(--agp-text);border-color:var(--agp-border);gap:0}.lobby-page--workspace :deep(.cm-editor){background:var(--agp-surface);color:var(--agp-text)}.lobby-page--workspace>.lobby-game-layout{height:100%}.lobby-page--workspace .lobby-empty{background:var(--agp-surface);color:var(--agp-text)}.lobby-dialog-close{border-radius:6px}.lobby-dialog-close{background:var(--agp-surface);color:var(--agp-text)}.arena-lobby-mobile-tabs{display:none}
@media(max-width:900px){.lobby-page.lobby-page--workspace{height:calc(100dvh - 16px);grid-template-rows:auto auto minmax(0,1fr);gap:8px}.arena-lobby-mobile-tabs{display:flex;gap:8px;grid-row:2;grid-column:1}.arena-lobby-mobile-tabs button{flex:1;min-height:44px;border:1px solid var(--agp-border);background:var(--agp-surface);color:var(--agp-text);border-radius:6px}.arena-lobby-mobile-tabs button[aria-pressed=true]{background:var(--agp-primary-soft);color:var(--agp-primary)}.lobby-page--workspace>.lobby-code-layout{grid-row:3;height:100%}.lobby-page--workspace>.lobby-game-layout{grid-row:3;height:100%;display:none!important}.lobby-page--workspace.lobby-page--field>.lobby-code-layout{display:none!important}.lobby-page--workspace.lobby-page--field>.lobby-game-layout{display:flex!important}}

.arena-queue-notice{display:flex;justify-content:space-between;align-items:center;gap:12px;grid-column:1/-1}.lobby-page--workspace>.arena-queue-notice{grid-row:2}.lobby-page--workspace:has(.arena-queue-notice){grid-template-rows:auto auto minmax(0,1fr)}.lobby-page--workspace:has(.arena-queue-notice)>.lobby-code-layout,.lobby-page--workspace:has(.arena-queue-notice)>.lobby-game-layout{grid-row:3}@media(max-width:900px){.lobby-page--workspace:has(.arena-queue-notice){grid-template-rows:auto auto auto minmax(0,1fr)}.lobby-page--workspace:has(.arena-queue-notice)>.arena-queue-notice{grid-row:3}.lobby-page--workspace:has(.arena-queue-notice)>.lobby-code-layout,.lobby-page--workspace:has(.arena-queue-notice)>.lobby-game-layout{grid-row:4}}

.lobby-page:not(.lobby-page--workspace){min-height:0}.lobby-page>:not(.lobby-head){margin-inline:0}
.arena-competition-panes{display:flex;gap:8px;margin-top:12px}.arena-competition-panes button{min-height:36px;border:1px solid var(--agp-border);border-radius:6px;background:var(--agp-surface);color:var(--agp-text-muted);padding:6px 12px}.arena-competition-panes button[aria-pressed=true]{background:var(--agp-primary-soft);color:var(--agp-primary)}@media(max-width:767px){.arena-competition-panes button,.lobby-dialog-close{min-height:44px;min-width:44px}}

.lobby-overview-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; min-width: 0; }
.lobby-overview-head > div:first-child { min-width: 0; }
.lobby-overview-head h1 { margin: 0; font-size: 24px; line-height: 32px; font-weight: 600; overflow-wrap: anywhere; }
.lobby-overview-head p { margin: 4px 0 0; color: var(--agp-text-muted); font-size: 12px; line-height: 20px; }
.lobby-overview-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; flex: none; }
.lobby-label-compact { display: none; }
.lobby-overview-tabs { display: flex; align-items: center; gap: 24px; border-bottom: 1px solid var(--agp-border); overflow-x: auto; }
.lobby-overview-tabs button { flex: none; padding: 10px 0; border: 0; border-bottom: 2px solid transparent; color: var(--agp-text-muted); background: transparent; font: inherit; font-size: 13px; line-height: 20px; }
.lobby-overview-tabs button[aria-current] { color: var(--agp-primary); border-bottom-color: var(--agp-primary); font-weight: 600; }
.lobby-overview-tabs button:hover { color: var(--agp-primary); }
.lobby-invite { display: flex; align-items: center; gap: 12px; padding: 12px 16px; }
.lobby-invite > span { flex: none; font-size: 12px; color: var(--agp-text-muted); }
.lobby-invite .form-control { flex: 1; min-width: 0; }
.lobby-invite > button { flex: none; }
.lobby-queue-banner, .lobby-pause-banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; border: 1px solid var(--agp-border); border-radius: 8px; background: var(--arena-success-soft); color: var(--agp-success); font-size: 13px; }
.lobby-queue-banner :deep(.arena-loading) { color: inherit; }
.lobby-queue-banner > .btn { flex-shrink: 0; }
.lobby-pause-banner { background: var(--arena-warning-soft); color: var(--agp-warning); }
.lobby-list-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 0 0 12px; }
.lobby-list-heading h2 { font-size: 16px; line-height: 24px; font-weight: 600; margin: 0; }
.lobby-list-heading p { margin: 4px 0 0; font-size: 12px; line-height: 20px; color: var(--agp-text-muted); }
.lobby-list-filters { display: flex; gap: 12px; align-items: center; }
.lobby-list-filters > :is(select,input) { width: 200px; min-width: 0; }
.lobby-list-filters > .btn { flex: none; }
.lobby-check { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: var(--agp-text-muted); white-space: nowrap; }
.lobby-check input { width: 14px; height: 14px; accent-color: var(--agp-primary); }
.lobby-game-list, .lobby-participants { padding: 16px; }
.lobby-game-entry { min-width: 0; border-bottom: 1px solid var(--agp-border); }
.lobby-game-entry:last-of-type { border-bottom: 0; }
.lobby-game-row { display: grid; grid-template-columns: 200px minmax(0,1fr) 80px; gap: 16px; align-items: center; padding: 12px 0; font-size: 13px; line-height: 20px; }
.lobby-game-row--own { grid-template-columns: 200px minmax(0,1fr) 160px 80px; }
.lobby-game-entry:first-child .lobby-game-row { padding-top: 0; }
.lobby-game-entry:last-of-type .lobby-game-row { padding-bottom: 0; }
.lobby-game-identity, .lobby-game-result { min-width: 0; display: grid; gap: 4px; }
.lobby-game-identity > div { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.lobby-game-identity strong { font-weight: 600; }
.lobby-game-identity time { font-size: 12px; color: var(--agp-text-muted); font-variant-numeric: tabular-nums; }
.lobby-game-result > span { overflow-wrap: anywhere; }
.lobby-text-action { border: 0; padding: 0; background: none; color: var(--agp-primary); font: inherit; font-size: 13px; line-height: 20px; text-align: left; text-decoration: none; cursor: pointer; }
.lobby-text-action:hover { text-decoration: underline; }
.lobby-game-result .lobby-text-action { justify-self: start; }
.lobby-game-watch { justify-self: end; }
.lobby-own-result { color: var(--agp-primary); font-size: 12px; font-weight: 500; }
.lobby-game-expanded { padding: 4px 0 12px; }
.lobby-game-expanded .table > :not(caption) > * > * { padding: 6px 8px; }
.lobby-game-list .lobby-match-pagination { border-top: 1px solid var(--agp-border); padding-top: 12px; margin-top: 16px; }
.lobby-table-self > td { background: var(--agp-primary-soft); }
.lobby-participant-identity { overflow-wrap: anywhere; }
.lobby-participant-place { width: 64px; text-align: right; font-variant-numeric: tabular-nums; }
.lobby-participant-actions { width: 1%; text-align: right; white-space: nowrap; }
.lobby-stat-cell { font-variant-numeric: tabular-nums; }
@media (max-width: 1000px) {
  .lobby-overview-head { flex-wrap: wrap; }
  .lobby-overview-actions { justify-content: flex-start; }
  .lobby-game-row { grid-template-columns: 180px minmax(0,1fr) 72px; }
  .lobby-game-row--own { grid-template-columns: 180px minmax(0,1fr) 140px 72px; }
}
@media (max-width: 767px) {
  .lobby-overview-head h1 { font-size: 22px; line-height: 28px; }
  .lobby-overview-actions { flex: 1 1 100%; }
  .lobby-label-wide { display: none; }
  .lobby-label-compact { display: inline; }
  .lobby-overview-tabs { gap: 16px; }
  .lobby-overview-tabs button { min-height: 44px; }
  .lobby-list-heading { align-items: flex-start; flex-wrap: wrap; gap: 8px; }
  .lobby-list-filters { flex-wrap: wrap; gap: 8px; width: 100%; }
  .lobby-list-filters > :is(select,input) { flex: 1; width: auto; min-width: 140px; }
  .lobby-list-filters .btn { padding-inline: 10px; }
  .lobby-game-list, .lobby-participants { padding: 12px; }
  .lobby-game-row, .lobby-game-row--own { grid-template-columns: minmax(0,1fr) auto; gap: 8px 12px; }
  .lobby-game-identity { grid-column: 1; grid-row: 1; }
  .lobby-game-watch { grid-column: 2; grid-row: 1; display: inline-flex; align-items: center; min-height: 44px; }
  .lobby-game-result, .lobby-own-result { grid-column: 1/-1; }
  .lobby-game-result { display: flex; justify-content: space-between; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
  .lobby-game-result > span { min-width: 0; flex: 1 1 160px; }
  .lobby-game-result .lobby-text-action { min-height: 44px; }
  .lobby-invite { flex-wrap: wrap; gap: 8px; padding: 12px; }
  .lobby-invite > span { flex: 1; }
  .lobby-invite > .form-control { order: 2; flex-basis: 100%; }
  .lobby-invite > .lobby-dialog-close { margin-left: auto; }

}

@media (max-width: 1000px) {
  .lobby-participant-table thead { display: none; }
  .lobby-participant-table tr { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); padding: 12px 0; border-bottom: 1px solid var(--agp-border); gap: 8px 12px; position: relative; }
  .lobby-participant-table tr:last-child { border-bottom: 0; padding-bottom: 0; }
  .lobby-participant-table td { padding: 0; border: 0; }
  .lobby-participant-table .lobby-participant-place { position: absolute; left: 0; top: 12px; width: 24px; text-align: left; color: var(--agp-text-muted); }
  .lobby-participant-table .lobby-participant-identity { grid-column: 1/-1; padding-left: 32px; padding-right: 48px; }
  .lobby-participant-table .lobby-participant-presence { grid-column: 1; color: var(--agp-text-muted); font-size: 12px; }
  .lobby-participant-table .lobby-participant-queue { grid-column: 2/-1; }
  .lobby-participant-table .lobby-stat-cell { text-align: left !important; display: grid; font-size: 13px; gap: 2px; }
  .lobby-stat-cell::before { content: attr(data-label); font-family: "Golos Text", sans-serif; font-size: 11px; color: var(--agp-text-muted); }
  .lobby-participant-table .lobby-participant-actions { position: absolute; right: 0; top: 12px; }
  .lobby-participant-table .lobby-participant-actions--duel { position: static; grid-column: 3; grid-row: 2; width: auto; align-self: center; }
  .lobby-participant-row--duel .lobby-participant-queue { grid-column: 2; align-self: center; }
  .lobby-participant-row--duel .lobby-participant-presence { align-self: center; }
  .lobby-participant-row--duel .lobby-participant-queue .agp-pill { white-space: normal; }
  .lobby-participant-actions--duel :deep(.arena-menu-trigger) { position: absolute; right: 0; top: 12px; }
}

.lobby-page--workspace > .agp-skeleton-region { grid-column: 1 / -1; grid-row: 2; }
@media (max-width: 900px) { .lobby-page--workspace > .agp-skeleton-region { grid-row: 3; } }

.lobby-games { display: grid; gap: 16px; }
.lobby-games > .lobby-list-heading { margin: 0; }
.lobby-section-count { margin-left: 8px; color: var(--agp-text-muted); font-size: 12px; font-weight: 400; }
.lobby-current-games .lobby-list-heading, .lobby-queued-duels .lobby-list-heading { margin-bottom: 12px; }
.lobby-live-list { padding: 4px 16px; max-height: 360px; overflow: auto; }
.lobby-live-row { display: grid; grid-template-columns: 160px minmax(0,1fr) auto; align-items: center; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--agp-border); font-size: 13px; }
.lobby-live-row:last-child { border: 0; }
.lobby-live-row > div { display: grid; gap: 4px; }
.lobby-live-row strong { font-size: 13px; font-weight: 600; }
.lobby-live-names { overflow-wrap: anywhere; }
.lobby-live-empty { padding: 16px; font-size: 13px; color: var(--agp-text-muted); }
.lobby-history-heading { padding-top: 8px; }
.lobby-history-toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.lobby-history-toolbar > :is(input,select) { width: 200px; }
.lobby-history-toolbar > input { flex: 1; min-width: 180px; }
.lobby-history-dates { position: relative; }
.lobby-history-dates summary { list-style: none; cursor: pointer; }
.lobby-history-dates summary::-webkit-details-marker { display: none; }
.lobby-history-dates > div { position: absolute; right: 0; z-index: 20; display: grid; gap: 8px; padding: 12px; width: 220px; background: var(--agp-surface); border: 1px solid var(--agp-border); border-radius: 8px; box-shadow: 0 8px 24px #10182718; }
.lobby-history-dates label { display: grid; gap: 4px; font-size: 12px; color: var(--agp-text-muted); }
.lobby-page.lobby-page--game { height: calc(100dvh - 24px); min-height: 0; grid-template-rows: auto minmax(0,1fr); gap: 8px; background: var(--agp-bg); }
.arena-live-workbar { display: flex; gap: 8px; align-items: center; min-height: 44px; }
.arena-live-workbar h1 { min-width: 0; flex: 1; font-size: 16px; line-height: 24px; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.arena-live-workbar > :is(button,a) { flex: none; }
.arena-live-switcher { display: flex; align-items: center; gap: 8px; }
.arena-live-switcher select { width: 240px; }
.arena-live-players { display: none; }
.lobby-page--game > .lobby-game-layout { height: 100%; min-height: 0; grid-template-columns: minmax(0,1fr) 320px; align-items: stretch; }
.lobby-page--game .lobby-game-view { height: 100%; min-height: 0; overflow: hidden; border: 1px solid var(--agp-border); border-radius: 10px; background: var(--agp-surface); }
.lobby-page--game .lobby-game-view iframe { display: block; width: 100%; height: 100%; min-height: 0; border: 0; }
.lobby-live-stats { min-height: 0; overflow: auto; padding: 16px; }
.lobby-live-stats > header { display: grid; gap: 4px; margin-bottom: 12px; }
.lobby-live-stats h2 { font-size: 16px; line-height: 24px; margin: 0; }
@media (max-width: 900px) {
  .lobby-page.lobby-page--game { height: calc(100dvh - 16px); }
  .arena-live-workbar { flex-wrap: wrap; }
  .arena-live-workbar h1 { flex: 1; }
  .arena-live-switcher { order: 2; flex: 1 0 100%; }
  .arena-live-switcher select { width: auto; flex: 1; min-width: 0; }
  .arena-live-players { display: inline-flex; }
  .lobby-page--game > .lobby-game-layout { grid-template-columns: minmax(0,1fr); }
  .lobby-live-stats { display: none; }
}
@media (max-width: 767px) {
  .lobby-live-row { grid-template-columns: minmax(0,1fr) auto; gap: 8px; }
  .lobby-live-row > .btn { grid-column: 2; grid-row: 1; min-height: 44px; display: flex; align-items: center; }
  .lobby-live-names { grid-column: 1/-1; color: var(--agp-text-muted); font-size: 12px; }
  .lobby-history-toolbar > :is(input,select) { width: 100%; }
  .lobby-history-toolbar > input { flex-basis: 100%; }
  .lobby-history-dates > div { right: auto; left: 0; }
}
</style>
