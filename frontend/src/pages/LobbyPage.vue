<template>
  <section class="agp-grid lobby-page" :class="{ 'lobby-page--game': activeTab === 'game', 'lobby-page--workspace': activeTab === 'code', 'lobby-page--field': lobbyMobilePane === 'field' }">
    <header v-if="activeTab === 'code'" class="arena-lobby-workbar"><button class="agp-back-link" aria-label="К лобби" @click="activeTab = 'lobby'"><AppIcon name="back" /></button><h1>{{ lobby?.title }}</h1><span class="small text-muted">{{ isSavingCode ? 'Сохраняем…' : isDirty ? 'Черновик' : formatTime(activeSlot?.updated_at) }}</span><button class="btn btn-outline-secondary" :aria-pressed="rulesOpen" @click="rulesOpen = !rulesOpen; lobbyMobilePane = 'field'">Условие</button><button v-if="showStopAction" class="btn btn-outline-danger" :disabled="!canStop || isBusy" @click="stop">Выйти из очереди</button><button v-else class="btn btn-primary" :disabled="!canPlay || isBusy" @click="play">В очередь</button></header>
    <header v-else class="agp-card p-2 lobby-head">
      <div class="lobby-title-block">
        <div class="lobby-title-line">
          <RouterLink class="agp-back-link" to="/lobbies" aria-label="К списку лобби"><AppIcon name="back" /></RouterLink>
          <h1 class="h4 mb-0">{{ lobby?.title || 'Лобби' }}</h1>
          <span v-if="lobby && (hasPlayerInLobby || canManage)" class="agp-pill agp-pill--neutral lobby-head-status">{{ hasPlayerInLobby ? readyStatusLabel : managerCycleStatusLabel }}</span>
        </div>
      </div>
      <nav v-if="lobby" class="lobby-tabs" aria-label="Разделы лобби">
        <button v-if="canSeeCodeTab" @click="activeTab = 'code'">Код и поле</button>
        <button :class="{ active: activeTab === 'lobby' }" @click="activeTab = 'lobby'">Участники и матчи</button>
        <button v-if="canSeeGameTab" :class="{ active: activeTab === 'game' }" @click="activeTab = 'game'">
          <span
            class="lobby-game-signal"
            :class="`lobby-game-signal--${gameSignalTone}`"
            :title="gameSignalLabel"
            aria-hidden="true"
          ></span>
          Игра
        </button>
        <button :class="{ active: activeTab === 'rules' }" @click="activeTab = 'rules'">Правила</button>
        <button v-if="activeCompetition" :class="{ active: activeTab === 'competition' }" @click="activeTab = 'competition'">
          Соревнование
        </button>
        <button v-if="competitionArchive.length" :class="{ active: activeTab === 'archive' }" @click="activeTab = 'archive'">
          Архив
        </button>
      </nav>
      <div v-if="lobby && (hasPlayerInLobby || canManage)" class="lobby-head-actions">
        <button v-if="showPlayAction" class="btn btn-primary" :disabled="!canPlay || isBusy" @click="play">В очередь</button>
        <button v-if="showStopAction" class="btn btn-outline-secondary" :disabled="!canStop || isBusy" aria-label="Выйти из очереди" @click="stop"><span class="lobby-action-wide">Выйти из очереди</span><span class="lobby-action-compact">Не готов</span></button>
        <button v-if="canManage && !activeCompetition" class="btn btn-outline-secondary" :disabled="isBusy" aria-label="Начать соревнование" @click="showCompetitionDialog = true"><AppIcon name="trophy" /><span class="lobby-action-wide">Соревнование</span><span class="lobby-action-compact">Турнир</span></button>
        <button v-if="canManage && !activeCompetition && canStartLobby" class="btn btn-primary" :disabled="isBusy" aria-label="Продолжить тренировку" @click="startLobbyByTeacher"><span class="lobby-action-wide">Продолжить тренировку</span><span class="lobby-action-compact">Продолжить</span></button>
        <ActionMenu v-if="canManage" label="Действия лобби" :items="lobbyMenuItems" @select="handleLobbyMenu" />
        <button v-else-if="canLeaveAsPlayer" class="btn btn-outline-secondary" :disabled="isBusy" @click="leaveAsPlayer">Выйти из лобби</button>
      </div>
    </header>

    <nav v-if="activeTab === 'code'" class="arena-lobby-mobile-tabs" aria-label="Рабочая панель"><button :aria-pressed="lobbyMobilePane === 'code'" @click="lobbyMobilePane = 'code'">Код</button><button :aria-pressed="lobbyMobilePane === 'field'" @click="lobbyMobilePane = 'field'">Поле</button></nav>
    <article v-if="queueExpired" class="agp-card p-3 arena-queue-notice" role="status"><span>Вы вышли из очереди после 10 минут офлайн.</span><button class="btn btn-outline-primary" :disabled="!canPlay || isBusy" @click="play">Снова готов</button></article>
    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <LoadingSkeleton v-if="isLoading" :count="3" label="Загрузка лобби…" />

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
      <article v-if="activeCompetition && activeTab !== 'code'" class="agp-card p-3 lobby-competition-banner">
        <div>
          <strong>{{ activeCompetition.status === 'completed' ? 'Победитель определен' : 'Идет соревнование' }}</strong>
          <div class="small text-muted">
            {{ competitionBannerText }}
          </div>
        </div>
        <button class="btn btn-sm btn-outline-secondary" @click="activeTab = 'competition'">Открыть сетку</button>
      </article>

      <Teleport to="body">
        <div v-if="showCompetitionDialog" class="lobby-modal-backdrop" @click.self="showCompetitionDialog = false">
          <article class="lobby-competition-dialog" v-dialog-focus="() => showCompetitionDialog = false" role="dialog" aria-modal="true" aria-labelledby="competition-dialog-title">
            <header class="lobby-dialog-head">
              <div>
                <h2 id="competition-dialog-title" class="h5 mb-1">Начать соревнование</h2>

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
                <span>Тай-брейк</span>
                <select v-model="competitionTieBreakPolicy" class="form-select form-select-sm">
                  <option value="manual">Ручное решение</option>
                  <option value="shared_advancement">Пропустить всех на границе</option>
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
              <button class="btn btn-outline-secondary" type="button" :disabled="!canSaveLobbySettings" @click="saveLobbySettings">
                {{ isSavingLobbySettings ? 'Сохраняем...' : 'Сохранить' }}
              </button>
              <button class="btn btn-outline-danger" type="button" :disabled="!canDeleteLobby || isBusy" @click="deleteLobbyByTeacher">
                Удалить
              </button>
            </footer>
            <p v-if="canManage && !canDeleteLobby" class="small text-muted mt-3 mb-0">
              Удаление доступно только после остановки лобби.
            </p>
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
                  <div class="d-flex gap-2 flex-wrap">
                    <button v-if="replacementUndo !== null" class="btn btn-sm btn-outline-secondary" @click="undoCodeReplacement">Отменить замену</button><button class="btn btn-sm btn-outline-secondary" :disabled="!activeTemplate || !canEditSelectedCode" @click="applyTemplate">
                      Шаблон
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" :disabled="!activeDemoStrategy || !canEditSelectedCode" @click="applyDemoStrategy">
                      Пример
                    </button>
                    <button class="btn btn-sm btn-dark" :disabled="!canSaveCode" @click="saveCode">
                      {{ isSavingCode ? 'Сохранение...' : 'Сохранить' }}
                    </button>
                  </div>
                </div>
                <CodeEditor v-model="editorCode" :readonly="!activeSlotKey || !canEditSelectedCode" @run="play" />
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
          <CodeEditor v-model="editorCode" :readonly="!activeSlotKey || !canEditSelectedCode" @run="play" />
        </article>
      </section>
      <section v-if="canSeeCodeTab && !workspace" v-show="activeTab === 'code'" class="agp-card p-4 lobby-code-empty">
        <h2 class="h5 mb-2">Код пока недоступен</h2>
        <p class="text-muted mb-0">
          Рабочее место появится после присоединения к лобби как игрок.
        </p>
      </section>

      <section v-if="activeTab === 'rules'" class="agp-card p-4"><h2>{{ game?.title }}</h2><MarkdownContent :source="docs?.player_instruction || game?.description || ''" /><MarkdownContent v-for="link in docs?.links.filter(l => l.content)" :key="link.path" :source="link.content!" /></section>
      <section v-show="activeTab === 'lobby'" class="lobby-state-grid">
        <div class="lobby-main-stack">
          <article class="agp-card p-3 lobby-matches-card">
            <header class="lobby-section-head">
              <div>
                <h2 class="h6 mb-1">Матчи</h2>

              </div>
              <span class="lobby-count-pill">{{ allTrainingMatchGroups.length }} всего</span>
            </header>
            <div class="lobby-history-filters"><label v-if="canManage"><input v-model="onlyMyMatches" type="checkbox" :disabled="!lobby?.my_team_id" /> Мои матчи</label><label><input v-model="onlyProblemMatches" type="checkbox" /> С ошибками</label><span class="text-muted">{{ filteredTrainingMatchGroups.length }} из {{ allTrainingMatchGroups.length }} загруженных</span></div>
            <div class="lobby-match-list">
              <section v-for="batch in pagedTrainingMatchBatches" :key="batch.batch_id" class="lobby-match-batch">
                <h3>{{ batch.title }}</h3>
                <article
                  v-for="group in batch.groups"
                  :key="group.group_id"
                  class="lobby-match-group"
                  :class="{ muted: group.archived }"
                >
                  <header>
                    <div>
                      <span>{{ matchGroupStatusLabel(group) }}</span>
                      <strong>{{ matchGroupTeamIds(group).length }} {{ pluralizePlayers(matchGroupTeamIds(group).length) }}</strong>
                    </div>
                    <RouterLink
                      class="btn btn-sm btn-outline-secondary"
                      :to="`/runs/${primaryRunId(group)}/watch`"
                      target="_blank"
                      rel="noopener noreferrer"
                      @click.stop
                    >
                      Смотреть
                    </RouterLink>
                  </header>
                  <div class="lobby-match-meta">
                    <span>{{ formatMatchDate(group) }}</span>
                    <span v-if="shouldHideMatchWinner(group)" class="lobby-match-replay-badge">Идет реплей</span>
                    <span v-else>Победитель: <strong>{{ matchWinnerLabel(group) }}</strong></span>
                  </div>
                  <details><summary>Участники и результаты</summary><div class="lobby-match-players" aria-label="Игроки матча">
                    <span
                      v-for="teamId in matchGroupTeamIds(group)"
                      :key="`${group.group_id}-${teamId}`"
                      class="lobby-match-player-chip"
                      :class="{ winner: matchPlayerIsVisibleWinner(group, teamId) }"
                    >
                      <span>{{ teamLabel(teamId) }}</span>
                      <small v-if="matchPlayerScoreLabel(group, teamId)">{{ matchPlayerScoreLabel(group, teamId) }}</small>
                    </span>
                  </div></details>
                </article>
              </section>
              <div v-if="!filteredTrainingMatchGroups.length" class="agp-empty-state agp-empty-state--compact">
                {{ allTrainingMatchGroups.length ? 'По выбранным фильтрам матчей нет.' : 'Матчей пока нет.' }}
              </div>
            </div>
            <footer v-if="matchPageCount > 1" class="lobby-match-pagination">
              <button class="btn btn-sm btn-outline-secondary" :disabled="matchPage === 1" @click="matchPage -= 1">
                Назад
              </button>
              <span class="small text-muted">Страница {{ matchPage }} из {{ matchPageCount }}</span>
              <button class="btn btn-sm btn-outline-secondary" :disabled="matchPage === matchPageCount" @click="matchPage += 1">
                Вперед
              </button>
            </footer>
          </article>
        </div>

        <aside class="lobby-side-stack">
          <article class="agp-card p-3">
            <header class="lobby-section-head">
              <div>
                <h2 class="h6 mb-1">Лидерборд</h2>

              </div>
              <span class="lobby-count-pill">{{ lobbyLeaderboard.length }} {{ pluralizePlayers(lobbyLeaderboard.length) }}</span>
              <button
                v-if="canUseAdminBots"
                class="lobby-mini-icon"
                :disabled="isBusy || !canAddBot"
                title="Добавить тестового бота"
                aria-label="Добавить тестового бота"
                @click="addDemoBot"
              >
                {{ isBusy ? '...' : '+' }}
              </button>
            </header>
            <div class="lobby-history-filters"><input v-model="playerSearch" type="search" aria-label="Найти участника" placeholder="Найти участника" /><label><input v-model="onlyQueuedPlayers" type="checkbox" /> В очереди</label></div>
            <div v-if="filteredLeaderboard.length" class="lobby-leaderboard-list">
              <div v-for="stat in filteredLeaderboard" :key="stat.team_id" class="lobby-leaderboard-row">
                <span class="lobby-leaderboard-place">{{ lobbyLeaderboard.findIndex(row => row.team_id === stat.team_id) + 1 }}</span>
                <div>
                  <header class="lobby-leaderboard-player-head">
                    <strong>{{ teamLabel(stat.team_id) }}</strong>
                    <span class="lobby-status-badge" :class="`lobby-status-badge--${teamStatusTone(stat.team_id)}`">
                      {{ teamStatusLabel(stat.team_id) }}
                    </span>
                  </header>
                  <span class="lobby-leaderboard-meta">
                    {{ stat.matches_total ? `${stat.wins} побед · ${stat.matches_total} игр · средний счёт ${averageScoreLabel(stat.average_score)}` : 'Без матчей' }}
                  </span>
                </div>
                <div class="lobby-leaderboard-actions">
                  <button
                    v-if="canManage"
                    class="lobby-mini-icon lobby-mini-icon--code"
                    :disabled="isBusy"
                    title="Открыть код игрока"
                    aria-label="Открыть код игрока"
                    @click="openPlayerCode(stat)"
                  >
                    &lt;/&gt;
                  </button>
                  <button
                    v-if="canUseAdminBots"
                    class="lobby-remove-player"
                    :disabled="isBusy || Boolean(activeCompetition)"
                    title="Удалить игрока из лобби"
                    aria-label="Удалить игрока из лобби"
                    @click="removeTeamFromLobby(stat)"
                  >
                    <AppIcon name="close" />
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="agp-empty-state agp-empty-state--compact">Статистика появится после первых матчей.</div>
          </article>
        </aside>
      </section>

      <section v-if="canSeeGameTab || activeTab === 'code'" v-show="activeTab === 'game' || activeTab === 'code'" class="lobby-game-layout">
        <article class="lobby-game-view"><GameReference v-if="rulesOpen && activeTab === 'code'" :title="game?.title || ''" :description="game?.description" :instruction="docs?.player_instruction" :template="activeTemplate" :docs="docs" :frame="{}" :is-actual="false" @close="rulesOpen = false" />
          <iframe
            v-if="displayedGameRunId" v-show="!rulesOpen || activeTab !== 'code'"
            :key="displayedGameWatchUrl"
            :src="displayedGameWatchUrl"
            title="Текущая игра"
          ></iframe>
          <div v-if="replayFinishedInViewer" class="lobby-game-finished-overlay">
            <div class="lobby-game-finished-card">
              <strong>Игра завершена</strong>
              <span>Победитель: {{ currentGameWinnerLabel }}</span>
              <small>Ожидайте следующей игры</small>
            </div>
          </div>
          <div v-if="!displayedGameRunId && !rulesOpen" class="lobby-empty">
            <SnakeLoader v-if="lobby.my_status === 'queued'" label="Подбираем матч" /><h2 v-else class="h6">Ⅱ {{ activeCompetition ? 'Ожидаем раунд' : 'Матч ещё не начался' }}</h2>
          </div>
        </article>
        <aside class="lobby-game-stats">
          <header class="lobby-game-stats-head">
            <div>
              <h2 class="h6 mb-1">Матч</h2>
              <span>{{ currentGamePhaseLabel }}</span>
            </div>
            <strong>{{ currentGameFrameLabel }}</strong>
          </header>

          <section v-if="currentReplayChoices.length > 1" class="lobby-game-run-select" aria-label="Реплеи">
            <span>Реплеи этого запуска</span>
            <button
              v-for="(choice, index) in currentReplayChoices"
              :key="choice.run_id"
              type="button"
              class="lobby-game-run-card"
              :class="{ active: displayedGameRunId === choice.run_id }"
              @click="selectReplayChoice(choice.run_id)"
            >
              <i>{{ index + 1 }}</i>
              <strong>{{ choice.label }}</strong>
              <small>{{ choice.meta }}</small>
            </button>
          </section>

          <div class="lobby-game-mini-stats">
            <div>
              <span>Лидер</span>
              <strong>{{ currentGameLeaderLabel }}</strong>
            </div>
            <div>
              <span>Игроков</span>
              <strong>{{ currentGameStats.length || '—' }}</strong>
            </div>
          </div>

          <div v-if="currentGameStats.length" class="lobby-stats-list lobby-game-scoreboard">
            <article
              v-for="stat in currentGameStats"
              :key="`${stat.run_id}-${stat.team_id}`"
              class="lobby-stat-row"
              :class="{ 'lobby-stat-row--self': stat.isSelf }"
            >
              <div class="lobby-stat-title">
                <strong>{{ stat.display_name }}</strong>
                <span>{{ stat.status }}</span>
              </div>
              <div class="lobby-stat-score">{{ stat.score }}</div>
              <div class="lobby-stat-bars">
                <span><i :style="{ width: `${stat.lifePercent}%` }"></i></span>
                <span><i :style="{ width: `${stat.shieldPercent}%` }"></i></span>
              </div>
              <small v-if="stat.meta">{{ stat.meta }}</small>
            </article>
          </div>
          <div v-else class="lobby-game-empty-stat">Статистика появится, когда начнется матч.</div>
        </aside>
      </section>

      <section v-if="activeCompetition" v-show="activeTab === 'competition'" class="agp-card p-3 lobby-competition-panel">
        <div class="d-flex justify-content-between gap-3 flex-wrap">
          <div>
            <h2 class="h6 mb-1">{{ cleanCompetitionTitle(activeCompetition.title) }}</h2>
            <p class="small text-muted mb-0">
              {{ competitionStatusLabel(activeCompetition.status) }} · матч {{ activeCompetitionBoundsLabel }} · проходят {{ activeCompetition.advancement_top_k }}
            </p>
          </div>
          <div v-if="canManage" class="d-flex gap-2 flex-wrap">
            <button v-if="activeCompetition.status === 'running'" class="btn btn-primary" :disabled="isBusy || currentCompetitionRound?.status !== 'finished'" @click="launchNextRound">Следующий раунд</button>
            <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/competitions/${activeCompetition.competition_id}`">
              Управление
            </RouterLink>
            <button
              class="btn btn-sm btn-outline-secondary"
              :disabled="!canFinishActiveCompetition || isBusy"
              @click="finishCompetitionFromLobby"
            >
              Завершить
            </button>
          </div>
        </div>
        <div v-if="activeCompetition.pending_reason" class="alert alert-warning py-2 mt-3 mb-0">
          {{ activeCompetition.pending_reason }}
        </div>
        <div v-if="activeCompetition.winner_team_ids.length" class="lobby-winners mt-3">
          <span class="small text-muted">Победитель</span>
          <strong>{{ activeCompetition.winner_team_ids.map(teamLabel).join(', ') }}</strong>
        </div>
        <nav class="arena-competition-panes" aria-label="Соревнование"><button :aria-pressed="competitionPane === 'matches'" @click="competitionPane = 'matches'">Матчи</button><button :aria-pressed="competitionPane === 'table'" @click="competitionPane = 'table'">Таблица</button></nav>
        <div v-if="competitionPane === 'table' && competitionTeamStats.length" class="lobby-competition-leaderboard mt-3">
          <h3 class="h6 mb-0">Итоги команд</h3>
          <div class="lobby-competition-stat-list">
            <div v-for="stat in competitionTeamStats" :key="stat.team_id" class="lobby-competition-stat-row">
              <strong>{{ stat.name }}</strong>
              <span>побед {{ stat.wins }} · поражений {{ stat.losses }} · очков {{ scoreLabel(stat.points) }}</span>
            </div>
          </div>
        </div>
        <div v-if="competitionPane === 'matches' && activeCompetition.rounds.length" class="lobby-rounds mt-3">
          <section v-for="round in activeCompetition.rounds" :key="round.round_index" class="lobby-round">
            <header>
              <strong>Раунд {{ round.round_index }}</strong>
              <span class="small text-muted">{{ competitionRoundStatusLabel(round.status) }}</span>
            </header>
            <article v-for="(match, matchIndex) in round.matches" :key="match.match_id" class="lobby-competition-match">
              <div class="d-flex justify-content-between gap-2 flex-wrap">
                <strong>Матч {{ matchIndex + 1 }}</strong>
                <div class="d-flex align-items-center gap-2 flex-wrap">
                  <span class="small text-muted">{{ competitionMatchStatusLabel(effectiveCompetitionMatchStatus(match)) }}</span>
                  <RouterLink
                    v-if="matchPrimaryRunId(match)"
                    class="btn btn-sm btn-outline-secondary"
                    :to="{ name: 'run-watch', params: { runId: matchPrimaryRunId(match) }, query: { back: route.fullPath } }"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Смотреть
                  </RouterLink>
                </div>
              </div>
              <MatchRoster :team-ids="match.team_ids" :name-for="teamLabel" :scores="competitionMatchScores(match, competitionRuns)" :advanced="match.advanced_team_ids" :my-team-id="lobby.my_team_id" />
              <div v-if="match.tie_break_reason" class="small text-warning">{{ match.tie_break_reason }}</div>
            </article>
          </section>
        </div>
        <div v-else-if="competitionPane === 'matches'" class="agp-empty-state agp-empty-state--compact mt-3">Сетка появится после старта первого раунда.</div>
      </section>

      <section v-show="activeTab === 'archive'" class="agp-card p-3">
        <h2 class="h6 mb-3">Архив соревнований</h2>
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
                Победитель: {{ archiveCompetitionWinnerLabel(item) }}
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
import ActionMenu, { type ActionMenuItem } from "../components/ActionMenu.vue";
import { competitionMatchScores } from '../lib/competitionPresentation';
import AppIcon from '../components/AppIcon.vue';
import { statusPillClass } from '../lib/statusTone';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import { computed, defineComponent, h, onMounted, onUnmounted, ref, watch, type PropType } from 'vue';
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';

import { formatTime } from '../lib/attemptPresentation';
import MatchRoster from '../components/MatchRoster.vue';
import SnakeLoader from '../components/SnakeLoader.vue';
import GameReference from '../components/GameReference.vue';
import MarkdownContent from '../components/MarkdownContent.vue';
import CodeEditor from '../components/CodeEditor.vue';
import {
  addLobbyDemoBot,
  deleteLobby,
  finishLobbyCompetition,
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
  setLobbyReady,
  setLobbyStatus,
  startLobbyCompetition,
  advanceCompetition,
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

const ParticipantColumn = defineComponent({
  props: {
    title: { type: String, required: true },
    tone: { type: String as PropType<'playing' | 'queued' | 'preparing'>, required: true },
    teamIds: { type: Array as PropType<string[]>, required: true },
    stats: { type: Object as PropType<Record<string, LobbyParticipantStatsDto>>, required: true },
    empty: { type: String, required: true },
  },
  setup(props) {
    const initials = (name: string): string => {
      const parts = name.trim().split(/\s+/).filter(Boolean);
      const letters = parts.length > 1 ? [parts[0][0], parts[1][0]] : [name[0] ?? '?'];
      return letters.join('').toUpperCase();
    };
    const averageLabel = (value: number | null | undefined): string =>
      value === null || value === undefined ? 'нет данных' : value.toFixed(1);
    return () =>
      h('section', { class: ['lobby-participant-column', `lobby-participant-column--${props.tone}`] }, [
        h('header', { class: 'lobby-participant-column-head' }, [
          h('h3', props.title),
          h('span', props.teamIds.length),
        ]),
        props.teamIds.length
          ? props.teamIds.map((teamId) => {
              const stat = props.stats[teamId];
              const name = stat?.display_name ?? teamId;
              return h('div', { class: 'lobby-player-row', key: teamId }, [
                h('span', { class: 'lobby-player-avatar' }, initials(name)),
                h('span', { class: 'lobby-player-main' }, [
                  h('strong', name),
                  h('span', { class: 'lobby-player-meta' }, [
                    h('i', `побед ${stat?.wins ?? 0}`),
                    h('i', `игр ${stat?.matches_total ?? 0}`),
                    h('i', `средний счет ${averageLabel(stat?.average_score)}`),
                  ]),
                ]),
              ]);
            })
          : h('div', { class: 'lobby-column-empty' }, props.empty),
      ]);
  },
});

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
  participants: Array<{
    run_id: string;
    team_id: string;
    display_name: string;
    captain_user_id: string;
    is_current: boolean;
  }>;
  players: EmbeddedGamePlayerStat[];
}

interface CompetitionTeamStatRow {
  team_id: string;
  name: string;
  wins: number;
  losses: number;
  points: number;
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
const competitionPane = ref<'matches' | 'table'>('matches');
const trainingRuns = ref<RunDto[]>([]);
const competitionArchive = ref<LobbyCompetitionDto[]>([]);
type LobbyTab = 'code' | 'lobby' | 'game' | 'competition' | 'archive' | 'rules';
function routeTab(): LobbyTab { const tab = String(route.query.tab || 'lobby'); return ['code','lobby','game','competition','archive','rules'].includes(tab) ? tab as LobbyTab : 'lobby'; }
const activeTab = ref<LobbyTab>(routeTab());
watch(() => route.query.tab, () => { activeTab.value = routeTab(); });
const activeSlotKey = ref('');
const queueExpired = computed(() => lobby.value?.teams.find(team => team.team_id === lobby.value?.my_team_id)?.blocker_reason?.includes('10 минут') ?? false);
const rulesOpen = ref(false);
const lobbyMobilePane = ref<'code' | 'field'>('code');
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
const competitionCodePolicy = ref<CompetitionCodePolicy>('locked_on_start');
const lastGameRunId = ref('');
const selectedTrainingRunId = ref('');
const selectedCompetitionRunId = ref('');
const displayedGameWatchUrl = ref('');
const displayedGameWatchKey = ref('');
const matchPage = ref(1);
const matchesPerPage = 8;
const onlyMyMatches = ref(false);
const onlyProblemMatches = ref(false);
const playerSearch = ref('');
const onlyQueuedPlayers = ref(false);
const queueReadinessLabel = computed(() => {
  const queued = lobby.value?.queued_team_ids.length ?? 0;
  const playing = lobby.value?.playing_team_ids.length ?? 0;
  const minimum = game.value?.min_players_per_match ?? 2;
  if (lobby.value?.cycle_phase === 'replay') return `Повтор для ${playing} игроков · в очереди ${queued}`;
  return playing ? `Играют ${playing} · в очереди ${queued}` : `Готовы ${queued} из ${minimum} для старта`;
});
const filteredLeaderboard = computed(() => lobbyLeaderboard.value.filter(stat =>
  (!onlyQueuedPlayers.value || lobby.value?.queued_team_ids.includes(stat.team_id)) &&
  teamLabel(stat.team_id).toLocaleLowerCase('ru-RU').includes(playerSearch.value.trim().toLocaleLowerCase('ru-RU'))));
watch([onlyMyMatches, onlyProblemMatches], () => { matchPage.value = 1; });
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
const canSeeGameTab = computed(() => hasPlayerInLobby.value || canManage.value);
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
  Boolean(canManage.value && lobby.value?.my_team_id && !activeCompetition.value && lobby.value.status !== 'closed'),
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

function teamStatusLabel(teamId: string): string {
  const state = lobby.value?.teams.find(team => team.team_id === teamId);
  if (lobby.value?.playing_team_ids.includes(teamId)) return 'играет';
  if (state?.is_bot) return state.ready ? 'Бот · в очереди' : 'Бот';
  if (state && !state.online) return state.ready ? 'Офлайн · в очереди' : 'Офлайн';
  if (lobby.value?.queued_team_ids.includes(teamId)) return 'в очереди';
  return 'готовится';
}

function teamStatusTone(teamId: string): string {
  if (lobby.value?.playing_team_ids.includes(teamId)) return 'playing';
  if (lobby.value?.queued_team_ids.includes(teamId)) return 'queued';
  return 'preparing';
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
  return competition.rounds.find((round) => round.round_index === competition.current_round_index) ?? null;
});
const visibleCompetitionMatches = computed(() => {
  const currentRound = currentCompetitionRound.value;
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!currentRound) return [];
  if (myTeamId) {
    return currentRound.matches.filter(
      (match) =>
        competitionMatchHasWatchableRun(match) &&
        match.team_ids.includes(myTeamId) &&
        Boolean(match.run_ids_by_team[myTeamId]),
    );
  }
  if (!canManage.value) return [];
  return currentRound.matches.filter(
    (match) => competitionMatchHasWatchableRun(match) && Boolean(matchPrimaryRunId(match)),
  );
});
const currentCompetitionMatch = computed(() => {
  const selected = selectedCompetitionRunId.value;
  if (selected) {
    const selectedMatch = visibleCompetitionMatches.value.find(
      (match) => Object.values(match.run_ids_by_team).includes(selected),
    );
    if (selectedMatch) return selectedMatch;
  }
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
  const match = currentCompetitionMatch.value;
  if (match && myTeamId) {
    const runId = match.run_ids_by_team[myTeamId] ?? '';
    return runId ? competitionRunsById.value[runId] ?? null : null;
  }
  if (match && canManage.value) {
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
  if (currentCompetitionRun.value) return currentCompetitionRun.value.run_id;
  if (currentCompetitionMatch.value && myTeamId) return currentCompetitionMatch.value.run_ids_by_team[myTeamId] ?? '';
  if (currentCompetitionMatch.value && canManage.value) return matchPrimaryRunId(currentCompetitionMatch.value) ?? '';
  return '';
});
const currentGameRunId = computed(() => {
  if (currentCompetitionRunId.value) return currentCompetitionRunId.value;
  const selected = selectedTrainingRunId.value;
  if (selected && currentTrainingRunIdSet.value.has(selected)) return selected;
  return lobby.value?.current_run_id || currentTrainingMatchGroups.value[0]?.runs[0]?.run_id || '';
});
const displayedGameRunId = computed(() => currentGameRunId.value || (activeCompetition.value ? '' : lastGameRunId.value));
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
  const replayStartedAt = lobby.value?.replay_started_at;
  if (replayStartedAt) {
    params.set('sync_started_at', replayStartedAt);
    params.set('sync_frame_ms', String(lobby.value?.cycle_frame_ms ?? 500));
  } else if ((lobby.value?.cycle_replay_frame_count ?? 0) > 0) {
    params.set('sync_frame_index', String(lobby.value?.cycle_replay_frame_index ?? 0));
    params.set('sync_frame_ms', String(lobby.value?.cycle_frame_ms ?? 500));
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
  if (activeCompetition.value?.status === 'completed') {
    return 'Лобби заблокировано, сетка доступна до ручного завершения учителем.';
  }
  if (!hasPlayerInLobby.value) {
    return 'Лобби заблокировано для входа и выхода. Матчи доступны из сетки соревнования.';
  }
  return 'Лобби заблокировано для входа и выхода. Текущая игра остается во вкладке "Игра".';
});
const codeLockedByCompetition = computed(() => {
  const competition = activeCompetition.value;
  if (!competition || competition.status === 'finished') return false;
  if (competition.code_policy === 'locked_on_registration') return true;
  if (competition.code_policy === 'locked_on_start') {
    return ['running', 'paused', 'completed'].includes(competition.status);
  }
  if (competition.code_policy === 'allowed_between_matches') {
    return Boolean(currentCompetitionRun.value || currentCompetitionMatch.value);
  }
  return false;
});
const canEditSelectedCode = computed(() =>
  Boolean(
    codeWorkspaceTeamId.value &&
      activeSlotKey.value &&
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
      label: `Матч ${matchIndex + 1}`,
      meta: match.team_ids.map(teamLabel).join(' · '),
    };
  }).filter((choice) => Boolean(choice.run_id)),
);
const trainingReplayChoices = computed(() =>
  currentTrainingMatchGroups.value.map((group, groupIndex) => {
    const myTeamId = lobby.value?.my_team_id ?? '';
    const ownRun = group.runs.find((run) => run.team_id === myTeamId);
    const viewerRun = ownRun ?? group.runs[0];
    return {
      run_id: viewerRun?.run_id ?? '',
      label: `Матч ${groupIndex + 1}`,
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
const filteredTrainingMatchGroups = computed(() => allTrainingMatchGroups.value.filter(group =>
  ((!canManage.value || onlyMyMatches.value) ? matchGroupTeamIds(group).includes(lobby.value?.my_team_id ?? '') : true) &&
  (!onlyProblemMatches.value || group.runs.some(link => { const run = trainingRunsById.value[link.run_id]; const metrics = isRecord(run?.result_payload?.metrics) ? run.result_payload.metrics : {}; return run && (['failed', 'timeout'].includes(run.status) || Boolean(run.error_message) || Number(metrics.bot_errors) > 0 || Boolean(metrics.compile_error) || (isRecord(metrics.compile_errors) && Object.values(metrics.compile_errors).some(Boolean))); }))));
const matchPageCount = computed(() =>
  Math.max(1, Math.ceil(filteredTrainingMatchGroups.value.length / matchesPerPage))
);
const pagedTrainingMatchGroups = computed(() => {
  const start = (matchPage.value - 1) * matchesPerPage;
  return filteredTrainingMatchGroups.value.slice(start, start + matchesPerPage);
});
const pagedTrainingMatchBatches = computed(() => {
  const batches: { batch_id: string; title: string; groups: TrainingMatchGroup[] }[] = [];
  for (const group of pagedTrainingMatchGroups.value) {
    let batch = batches.find((item) => item.batch_id === group.batch_id);
    if (!batch) {
      batch = {
        batch_id: group.batch_id,
        title: formatBatchTitle(group),
        groups: [],
      };
      batches.push(batch);
    }
    batch.groups.push(group);
  }
  return batches;
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
    const preferred = currentCompetitionRun.value?.run_id;
    selectedCompetitionRunId.value = choices.find((choice) => choice.run_id === preferred)?.run_id ?? choices[0].run_id;
  } else {
    if (selectedTrainingRunId.value && choices.some((choice) => choice.run_id === selectedTrainingRunId.value)) {
      return;
    }
    const preferred = lobby.value?.current_run_id;
    selectedTrainingRunId.value = choices.find((choice) => choice.run_id === preferred)?.run_id ?? choices[0].run_id;
  }
});
const displayedTrainingRunIds = computed(() => {
  if (!displayedGameRunId.value) return [];
  const group = allTrainingMatchGroups.value
    .find((item) => item.runs.some((run) => run.run_id === displayedGameRunId.value));
  if (group) return group.runs.map((run) => run.run_id);
  const competitionMatch = currentCompetitionMatch.value;
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
  return dedupeCurrentGameStats([...embeddedRows, ...frameRows]);
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
    const competitionScore = currentCompetitionMatch.value?.scores_by_team[competitionRun.team_id];
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
const currentGameStats = computed<CurrentGameStatRow[]>(() =>
  sortCurrentGameStats(dedupeCurrentGameStats([...frameGameStats.value, ...fallbackGameStats.value])),
);
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
  if (lobby.value?.cycle_phase === 'result') return true;
  const message = embeddedGameFrame.value;
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
const currentGameWinnerLabel = computed(() => {
  const groupWinners = displayedGameMatchGroup.value?.winner_team_ids ?? [];
  const groupWinner = primaryWinnerTeamId(groupWinners, currentGameScoreMap.value);
  if (groupWinner) return teamLabel(groupWinner);

  const competitionMatch = currentCompetitionMatch.value;
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
  [...(lobby.value?.participant_stats ?? [])].sort((left, right) => {
    const rightWinRate = winRate(right);
    const leftWinRate = winRate(left);
    if (rightWinRate !== leftWinRate) return rightWinRate - leftWinRate;
    if (right.wins !== left.wins) return right.wins - left.wins;
    const rightAverage = right.average_score ?? Number.NEGATIVE_INFINITY;
    const leftAverage = left.average_score ?? Number.NEGATIVE_INFINITY;
    if (rightAverage !== leftAverage) return rightAverage - leftAverage;
    return right.matches_total - left.matches_total;
  }),
);
const competitionTeamStats = computed<CompetitionTeamStatRow[]>(() => {
  const rows: Record<string, CompetitionTeamStatRow> = {};
  const ensureRow = (teamId: string) => {
    rows[teamId] ??= {
      team_id: teamId,
      name: teamLabel(teamId),
      wins: 0,
      losses: 0,
      points: 0,
    };
    return rows[teamId];
  };

  for (const entrant of activeCompetition.value?.entrants ?? []) ensureRow(entrant.team_id);
  for (const round of activeCompetition.value?.rounds ?? []) {
    for (const match of round.matches) {
      for (const teamId of match.team_ids) {
        const row = ensureRow(teamId);
        row.points += match.scores_by_team[teamId] ?? 0;
        if (!isResolvedCompetitionMatch(match)) continue;
        if (match.advanced_team_ids.includes(teamId)) row.wins += 1;
        else row.losses += 1;
      }
    }
  }

  return Object.values(rows).sort((left, right) => {
    if (right.wins !== left.wins) return right.wins - left.wins;
    if (right.points !== left.points) return right.points - left.points;
    return left.losses - right.losses;
  });
});
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
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function averageScoreLabel(value: number | null | undefined): string {
  return value === null || value === undefined ? 'нет данных' : value.toFixed(1);
}

function winRate(stat: LobbyParticipantStatsDto): number {
  if (stat.matches_total <= 0) return Number.NEGATIVE_INFINITY;
  return stat.wins / stat.matches_total;
}

function winRateLabel(stat: LobbyParticipantStatsDto): string {
  if (stat.matches_total <= 0) return 'нет данных';
  return `${(winRate(stat) * 100).toFixed(1)}%`;
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

function matchGroupStatusLabel(group: TrainingMatchGroup): string {
  if (group.status === 'simulation') return 'Симуляция';
  if (group.status === 'replay') return 'Идет реплей';
  if (group.status === 'result') return 'Результат';
  return group.archived ? 'Архивный матч' : 'Текущий матч';
}

function formatBatchTitle(group: TrainingMatchGroup): string {
  const startedAt = group.started_at || trainingRunsById.value[primaryRunId(group)]?.created_at || '';
  if (!startedAt) return group.archived ? 'Прошлые запуски' : 'Текущий запуск';
  return `${group.archived ? 'Запуск' : 'Текущий запуск'} · ${formatDateTime(startedAt)}`;
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
  return group.status === 'replay';
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

function matchGroupWinnerIds(group: TrainingMatchGroup): string[] {
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
    if (placementWinners.length === 1 || !scores.size) return placementWinners;
    const bestScore = Math.max(...placementWinners.map((teamId) => scores.get(teamId) ?? Number.NEGATIVE_INFINITY));
    return placementWinners.filter((teamId) => (scores.get(teamId) ?? Number.NEGATIVE_INFINITY) === bestScore);
  }
  if (scores.size) {
    const bestScore = Math.max(...scores.values());
    return [...scores.entries()].filter(([, score]) => score === bestScore).map(([teamId]) => teamId);
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
  if (activeCompetition.value) {
    selectedCompetitionRunId.value = runId;
    return;
  }
  selectedTrainingRunId.value = runId;
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
  if (activeCompetition.value && activeTab.value === 'archive') activeTab.value = 'competition';
  if (!activeCompetition.value && activeTab.value === 'competition') {
    activeTab.value = competitionArchive.value.length ? 'archive' : 'lobby';
  }
  if (!competitionArchive.value.length && activeTab.value === 'archive') {
    activeTab.value = 'lobby';
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
    if (!canManage.value && !lobby.value.my_team_id && ['open', 'running', 'draft'].includes(lobby.value.status)) lobby.value = await joinLobbyAsUser({ lobby_id: id, access_code: lobbyAccessCode.value.trim() || null });
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
  if (!confirm('Прекратить участие в лобби как игрок? Код останется в системе, но игрок выйдет из этого лобби.')) return;
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

async function launchNextRound(): Promise<void> {
  if (!activeCompetition.value || isBusy.value) return;
  isBusy.value = true;
  try { activeCompetition.value = await advanceCompetition({ competition_id: activeCompetition.value.competition_id, requested_by: sessionStore.nickname }); }
  catch (e) { errorMessage.value = e instanceof Error ? e.message : 'Не удалось запустить раунд'; }
  finally { isBusy.value = false; }
}
async function startCompetitionFromLobby(): Promise<void> {
  if (!lobby.value) return;
  clampCompetitionSettingsToGame();
  isBusy.value = true;
  try {
    await startLobbyCompetition({
      lobby_id: lobby.value.lobby_id,
      title: `${lobby.value.title} / соревнование`,
      participant_selection: competitionRosterMode.value,
      team_ids: competitionSelectedTeams.value,
      tie_break_policy: competitionTieBreakPolicy.value,
      code_policy: competitionCodePolicy.value,
      advancement_top_k: Math.max(1, Math.min(competitionAdvanceTopK.value, competitionMatchSize.value)),
      match_size: Math.max(
        competitionMinMatchSize.value,
        Math.min(competitionMaxMatchSize.value, competitionMatchSize.value),
      ),
    });
    await refreshLobbyOnly();
    activeTab.value = 'competition';
    showCompetitionDialog.value = false;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось начать соревнование';
  } finally {
    isBusy.value = false;
  }
}

async function finishCompetitionFromLobby(): Promise<void> {
  if (!lobby.value || !activeCompetition.value) return;
  isBusy.value = true;
  try {
    await finishLobbyCompetition({
      lobby_id: lobby.value.lobby_id,
      competition_id: activeCompetition.value.competition_id,
    });
    await refreshLobbyOnly();
    activeTab.value = 'archive';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось завершить соревнование';
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
  if (route.query.tab !== tab) void router.replace({ query: { ...route.query, tab } });
  if (previousTab === 'code') void flushCodeAutosave();
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
  const items: ActionMenuItem[] = [{ id: 'settings', label: 'Настройки лобби', disabled: isBusy.value }];
  if (!hasPlayerInLobby.value) items.push({ id: 'join', label: 'Участвовать как игрок', disabled: !canJoinAsPlayer.value || isBusy.value });
  if (!activeCompetition.value && canPauseLobby.value) items.push({ id: 'pause', label: 'Приостановить тренировку', disabled: isBusy.value });
  if (!activeCompetition.value && canStopLobbyByTeacher.value) items.push({ id: 'stop', label: 'Остановить тренировку', danger: true, disabled: isBusy.value });
  if (canLeaveAsPlayer.value) items.push({ id: 'leave', label: 'Выйти из лобби', danger: true, disabled: isBusy.value });
  return items;
});
function handleLobbyMenu(action: string): void {
  if (action === 'settings') showLobbySettingsDialog.value = true;
  if (action === 'join') void joinAsPlayer();
  if (action === 'pause') void pauseLobbyByTeacher();
  if (action === 'stop') void stopLobbyByTeacher();
  if (action === 'leave') void leaveAsPlayer();
}
</script>

<style scoped>


.lobby-page {
  min-height: 100dvh;
  gap: 0.6rem;
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

.lobby-head {
  position: sticky;
  top: 0;
  z-index: 12;
  display: grid;
  grid-template-columns: minmax(13rem, 0.7fr) minmax(16rem, 1fr) auto;
  gap: 0.65rem;
  align-items: center;
  min-height: 3.35rem;
  border-radius: 0;
  border-left: 0;
  border-right: 0;
}

.lobby-page > :not(.lobby-head) {
  margin-inline: 0.6rem;
}

.lobby-page--game > :not(.lobby-head) {
  margin-inline: 0;
}

.lobby-title-block {
  min-width: 0;
}

.lobby-title-line {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.lobby-title-line h1 {
  min-width: 0;
  overflow: hidden;
  font-size: 1rem;
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lobby-head-status { flex: none; white-space: nowrap; }
.lobby-action-compact { display: none; }
@media (max-width: 480px) {
  .lobby-action-wide { display: none; }
  .lobby-action-compact { display: inline; }
  .lobby-head-actions .arena-menu-trigger { margin-left: auto; }
}

.lobby-head-actions,
.lobby-tabs,
.lobby-editor-toolbar,
.lobby-access-card,
.lobby-access-form {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.lobby-head-actions {
  justify-content: flex-end;
  flex-wrap: wrap;
}

.lobby-ready-summary {
  display: grid;
  gap: 0.05rem;
  max-width: 14rem;
  text-align: right;
}

.lobby-ready-summary strong {
  font-size: 0.86rem;
}

.lobby-ready-summary span {
  color: var(--agp-text-muted);
  font-size: 0.72rem;
  line-height: 1.25;
}

.lobby-ready-icon {
  min-width: 2.75rem;
  height: 2.75rem;
  padding: .5rem .75rem;
  border: 1px solid transparent;
  border-radius: .55rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: .5rem;
  font-size: .85rem;
  font-weight: 700;
  line-height: 1.2;
}

.lobby-ready-icon:disabled {
  opacity: 0.38;
}

.lobby-ready-icon--play {
  background: var(--agp-action);
  box-shadow: none;
  color: var(--arena-on-primary);
}

.lobby-ready-icon--stop {
  border-color: var(--agp-border);
  background: var(--agp-surface);
  color: var(--agp-text-muted);
}

.lobby-action-icon {
  width: auto;
  min-width: 2.25rem;
  height: 2.25rem;
  padding: .45rem .65rem;
  gap: .35rem;
  white-space: nowrap;
  border: 1px solid rgba(148, 163, 184, 0.42);
  border-radius: .5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--agp-surface);
  color: var(--agp-text);
  font-size: .75rem;
  font-weight: 700;
  line-height: 1;
  box-shadow: none;
}

.lobby-action-icon:hover:not(:disabled) {
  border-color: var(--agp-border);
  color: var(--agp-primary);
}

.lobby-action-icon:disabled {
  opacity: 0.45;
}

.lobby-action-icon--play {
  border-color: transparent;
  background: var(--agp-action);
  color: var(--arena-on-primary);
}

.lobby-action-icon--join {
  border-color: var(--agp-border);
  background: var(--arena-success-soft);
  color: var(--agp-primary);
}

.lobby-action-icon--leave {
  border-color: var(--agp-border);
  background: var(--arena-warning-soft);
  color: var(--agp-warning);
}

.lobby-action-icon--danger {
  border-color: var(--agp-border);
  color: var(--agp-danger);
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
  gap: 1rem;
  border-color: var(--agp-border);
  background: var(--arena-warning-soft);
}

.lobby-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  place-items: start end;
  overflow-y: auto;
  padding: 4.2rem 1rem 1rem;
  background: rgba(15, 23, 42, 0.32);
  backdrop-filter: blur(3px);
}

.lobby-competition-dialog,
.lobby-settings-dialog,
.lobby-player-code-dialog {
  width: min(100%, 28rem);
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
  max-height: calc(100dvh - 6rem);
  overflow: hidden;
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
  margin-bottom: 0.9rem;
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
  margin-top: 1rem;
}

.lobby-tabs button {
  border: 0;
  border-radius: 0.45rem;
  background: transparent;
  color: var(--agp-text-muted);
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.7rem;
  font-weight: 700;
}

.lobby-tabs button.active {
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.lobby-game-signal {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.16);
}

.lobby-game-signal--idle {
  background: #94a3b8;
}

.lobby-game-signal--yellow {
  background: #f59e0b;
}

.lobby-game-signal--green {
  background: #10b981;
}

.lobby-code-layout,
.lobby-game-layout,
.lobby-state-grid {
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

.lobby-state-grid {
  grid-template-columns: minmax(0, 1.4fr) minmax(20rem, 0.6fr);
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
.lobby-participant-column,
.lobby-match-list,
.lobby-stats-list,
.lobby-main-stack,
.lobby-side-stack,
.lobby-teacher-card {
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

.lobby-role-button span,
.lobby-participant-column h3 {
  font-weight: 700;
}

.lobby-role-button small,
.lobby-player-meta,
.lobby-stat-row span {
  color: var(--agp-text-muted);
}

.lobby-role-button small {
  color: var(--agp-text-muted);
}

.lobby-competition-panel,
.lobby-competition-leaderboard,
.lobby-competition-stat-list,
.lobby-rounds,
.lobby-round,
.lobby-competition-match,
.lobby-competition-team-rows {
  display: grid;
  gap: 0.75rem;
}

.lobby-settings-card {
  position: relative;
  overflow: hidden;
}

.lobby-settings-card::before {
  content: none;
}

.lobby-settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.lobby-settings-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.5rem;
  align-items: center;
}

.lobby-winners {
  display: grid;
  gap: 0.15rem;
  width: fit-content;
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: 0.45rem;
  background: var(--agp-primary-soft);
  padding: 0.55rem 0.65rem;
}

.lobby-round {
  border-top: 1px solid var(--agp-border);
  padding-top: 0.75rem;
}

.lobby-round header,
.lobby-match-team-list {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.lobby-round header {
  justify-content: space-between;
}

.lobby-competition-match {
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  padding: 0.65rem;
  background: var(--agp-surface-soft);
}

.lobby-competition-stat-list {
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 0.5rem;
}

.lobby-competition-stat-row,
.lobby-competition-team-row {
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  background: var(--agp-surface);
  padding: 0.5rem 0.6rem;
  display: grid;
  gap: 0.05rem;
}

.lobby-competition-stat-row span,
.lobby-competition-team-row span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-competition-team-rows {
  gap: 0.45rem;
}

.lobby-competition-team-row {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.lobby-competition-team-row.winner {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
}

.lobby-competition-team-row.loser {
  background: var(--agp-surface);
}

.lobby-competition-setting {
  display: grid;
  gap: 0.15rem;
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

.lobby-participant-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
}

.lobby-participant-column {
  align-content: start;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.55rem;
  background: var(--agp-surface);
  padding: 0.65rem;
  min-width: 0;
  overflow: hidden;
}

.lobby-participant-column-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.lobby-participant-column-head span {
  min-width: 1.6rem;
  height: 1.6rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-weight: 700;
  font-size: 0.78rem;
}

.lobby-participant-column--playing .lobby-participant-column-head span {
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.lobby-participant-column--queued .lobby-participant-column-head span {
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.lobby-participant-column--preparing .lobby-participant-column-head span {
  background: var(--arena-warning-soft);
  color: var(--agp-warning);
}

.lobby-column-empty {
  border: 1px dashed rgba(15, 118, 110, 0.22);
  border-radius: 0.55rem;
  background: var(--agp-surface);
  color: var(--agp-text-muted);
  font-size: 0.84rem;
  padding: 0.65rem;
}

.lobby-participants-card {
  min-height: 10rem;
}

.lobby-main-stack {
  align-content: start;
  min-width: 0;
}

.lobby-side-stack {
  align-content: start;
}

.lobby-teacher-card {
  align-content: start;
}

.lobby-competition-settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.45rem;
}

.lobby-competition-setting--wide {
  grid-column: 1 / -1;
}

.lobby-participant-column h3 {
  font-size: 0.82rem;
  margin: 0;
}

.lobby-player-row,
.lobby-match-row,
.lobby-match-group,
.lobby-stat-row,
.lobby-leaderboard-row {
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

.lobby-player-row {
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 0.55rem;
  background: var(--agp-surface);
  min-width: 0;
  overflow: hidden;
}

.lobby-player-avatar {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-size: 0.72rem;
  font-weight: 700;
}

.lobby-participant-column--playing .lobby-player-avatar {
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.lobby-participant-column--preparing .lobby-player-avatar {
  background: var(--arena-warning-soft);
  color: var(--agp-warning);
}

.lobby-player-main {
  min-width: 0;
  display: grid;
  gap: 0.25rem;
}

.lobby-player-main strong {
  min-width: 0;
  overflow: hidden;
  overflow-wrap: anywhere;
  line-height: 1.15;
}

.lobby-player-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(4.8rem, max-content));
  align-items: start;
  gap: 0.35rem;
  font-size: 0.76rem;
}

.lobby-player-meta i {
  font-style: normal;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  background: var(--agp-surface-soft);
  padding: 0.08rem 0.4rem;
  white-space: nowrap;
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

.lobby-match-group {
  gap: 0.5rem;
}

.lobby-match-batch {
  display: grid;
  gap: 0.45rem;
}

.lobby-match-batch + .lobby-match-batch {
  margin-top: 0.75rem;
}

.lobby-match-batch > h3 {
  margin: 0;
  color: var(--agp-text-muted);
  font-size: 0.8rem;
  font-weight: 700;
}

.lobby-match-group.muted {
  background: var(--agp-surface-soft);
}

.lobby-match-group header,
.lobby-run-links,
.lobby-leaderboard-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.lobby-match-group header {
  justify-content: space-between;
}

.lobby-match-group header > div {
  display: grid;
  gap: 0.05rem;
}

.lobby-match-group header > div span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-section-head,
.lobby-match-pagination,
.lobby-match-meta {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.lobby-section-head {
  justify-content: space-between;
  margin-bottom: 0.65rem;
}

.lobby-count-pill {
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: 999px;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  padding: 0.2rem 0.55rem;
  font-size: 0.78rem;
  font-weight: 700;
}

.lobby-match-meta {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-match-meta strong {
  color: var(--agp-text);
}

.lobby-match-players {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.lobby-match-player-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  max-width: 16rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 999px;
  background: var(--agp-surface);
  color: var(--agp-text-muted);
  padding: 0.14rem 0.55rem;
  font-size: 0.78rem;
  font-weight: 700;
}

.lobby-match-player-chip span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-match-player-chip small {
  color: var(--agp-text);
  font-size: 0.72rem;
  font-weight: 700;
}

.lobby-match-player-chip.winner {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.lobby-match-replay-badge {
  border: 1px solid rgba(245, 158, 11, 0.28);
  border-radius: 999px;
  background: var(--arena-warning-soft);
  color: var(--agp-warning);
  padding: 0.12rem 0.5rem;
  font-weight: 700;
}

.lobby-match-pagination {
  justify-content: space-between;
  margin-top: 0.65rem;
}

.lobby-leaderboard-list {
  display: grid;
  gap: 0.45rem;
}

.lobby-leaderboard-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  background: var(--agp-surface);
}

.lobby-leaderboard-row > div {
  display: grid;
  gap: 0.18rem;
  min-width: 0;
}

.lobby-leaderboard-row > .lobby-leaderboard-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.35rem;
}

.lobby-mini-icon {
  width: 1.9rem;
  height: 1.9rem;
  border: 1px solid rgba(20, 184, 166, 0.28);
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-size: 0.98rem;
  font-weight: 700;
  line-height: 1;
}

.lobby-mini-icon:hover:not(:disabled) {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
}

.lobby-mini-icon:disabled {
  opacity: 0.45;
}

.lobby-mini-icon--code {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.78rem;
}

.lobby-leaderboard-player-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
  min-width: 0;
}

.lobby-leaderboard-player-head strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.15;
}

.lobby-leaderboard-meta,
.lobby-leaderboard-row span:not(.lobby-leaderboard-place):not(.lobby-status-badge) {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-leaderboard-meta {
  display: block;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.lobby-status-badge {
  flex: none;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 999px;
  background: var(--agp-surface-soft);
  color: var(--agp-text-muted);
  padding: 0.12rem 0.45rem;
  font-size: 0.7rem;
  font-weight: 700;
  line-height: 1.2;
}

.lobby-status-badge--playing {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.lobby-status-badge--queued {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.lobby-status-badge--preparing {
  border-color: var(--agp-border);
  background: var(--arena-warning-soft);
  color: var(--agp-warning);
}

.lobby-remove-player {
  width: 1.75rem;
  height: 1.75rem;
  border: 1px solid rgba(248, 113, 113, 0.28);
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--arena-error-soft);
  color: var(--agp-danger);
  font-size: 1rem;
  font-weight: 700;
  line-height: 1;
}

.lobby-remove-player:hover:not(:disabled) {
  border-color: var(--agp-border);
  background: var(--arena-error-soft);
}

.lobby-remove-player:disabled {
  opacity: 0.4;
}

.lobby-leaderboard-place {
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-weight: 700;
  font-size: 0.78rem;
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
  .lobby-head,
  .lobby-code-layout,
  .lobby-game-layout,
  .lobby-state-grid,
  .lobby-participant-columns {
    grid-template-columns: 1fr;
  }

  .lobby-head-actions,
  .lobby-teacher-card {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .lobby-ready-summary {
    max-width: 100%;
    text-align: left;
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


.arena-lobby-workbar{display:flex;align-items:center;gap:8px;grid-column:1/-1;min-height:44px}.arena-lobby-workbar h1{font-size:16px;line-height:24px;margin:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.arena-lobby-workbar>.small{font-size:11px;margin-right:8px}.lobby-page--workspace{height:calc(100dvh - 24px);grid-template-columns:minmax(0,52fr) minmax(0,48fr);grid-template-rows:auto minmax(0,1fr);gap:8px}.lobby-page--workspace>.lobby-code-layout{grid-column:1;grid-row:2;display:flex;min-height:0}.lobby-page--workspace .lobby-roles{display:none}.lobby-page--workspace .lobby-editor{padding:0!important;display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}.arena-lobby-editor-head{min-height:44px;border-bottom:1px solid var(--agp-border);margin:0;padding:6px 12px;display:flex}.arena-lobby-editor-head>strong{font-size:12px;font-weight:500}.arena-lobby-editor-head select{max-width:180px}.arena-lobby-editor-head details{margin-left:auto}.lobby-page--workspace .agp-code-editor{flex:1;min-height:0;overflow:hidden}.lobby-page--workspace :deep(.cm-editor){height:100%;min-height:0!important;border:0!important;border-radius:0!important}.lobby-page--workspace>.lobby-game-layout{grid-column:2;grid-row:2;display:flex;min-height:0}.lobby-page--workspace .lobby-game-stats{display:none}.lobby-page--workspace .lobby-game-view{flex:1;min-height:0;border:1px solid var(--agp-border);border-radius:10px;background:var(--agp-surface);overflow:hidden}.lobby-page--workspace .lobby-game-view>.agp-game-reference{height:100%;overflow:auto}.arena-file-menu{position:relative}.arena-file-menu summary{font-size:22px;padding:0 8px;list-style:none;cursor:pointer}.arena-file-menu>div{position:absolute;right:0;z-index:20;width:210px;background:var(--agp-surface);border:1px solid var(--agp-border);border-radius:8px;padding:8px;display:grid}.arena-file-menu button{background:none;border:0;color:var(--agp-text);text-align:left;padding:8px;font-size:13px}.arena-roster-picker{margin:0 0 16px;padding:0;border:0;display:grid;gap:8px}.arena-roster-picker legend{font-size:14px;font-weight:600}.arena-roster-picker label{display:flex;align-items:center;gap:8px;font-size:13px}.arena-roster-picker>div{max-height:180px;overflow:auto;display:grid;gap:8px;padding:8px;background:var(--agp-surface-soft);border-radius:6px}.lobby-competition-dialog{max-height:calc(100dvh - 6rem);overflow:auto}
@media(max-width:900px){.lobby-page--workspace{height:auto;grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto auto}.lobby-page--workspace>.lobby-code-layout{grid-row:2;grid-column:1;height:58dvh}.lobby-page--workspace>.lobby-game-layout{grid-row:3;grid-column:1;height:48dvh}.arena-lobby-workbar{flex-wrap:wrap}.arena-lobby-workbar>.small{display:none}.arena-lobby-workbar .btn{font-size:12px;padding:6px 8px}}


.lobby-page.lobby-page--workspace{min-height:0;align-content:stretch}.lobby-page.lobby-page--workspace>:not(.lobby-head){margin-inline:0}.lobby-page--workspace>.lobby-code-layout{align-items:stretch}.lobby-page--workspace .lobby-editor{height:100%;background:var(--agp-surface);color:var(--agp-text);border-color:var(--agp-border);gap:0}.lobby-page--workspace :deep(.cm-editor){background:var(--agp-surface);color:var(--agp-text)}.lobby-page--workspace>.lobby-game-layout{height:100%}.lobby-page--workspace .lobby-empty{background:var(--agp-surface);color:var(--agp-text)}.lobby-head{border-radius:10px;border:1px solid var(--agp-border);background:var(--agp-surface)}.lobby-ready-icon--play,.lobby-action-icon--play{background:var(--agp-action);color:var(--arena-on-primary);border-color:var(--agp-action)}.lobby-action-icon,.lobby-ready-icon,.lobby-dialog-close{border-radius:6px}.lobby-dialog-close{background:var(--agp-surface);color:var(--agp-text)}.lobby-ready-summary>span{display:none}.lobby-leaderboard-meta{color:var(--agp-text-muted)}


.lobby-leaderboard-list{max-height:520px;overflow:auto;scrollbar-gutter:stable}.lobby-leaderboard-row{padding:8px;min-height:56px}.arena-lobby-mobile-tabs{display:none}
@media(max-width:900px){.lobby-page.lobby-page--workspace{height:calc(100dvh - 16px);grid-template-rows:auto auto minmax(0,1fr);gap:8px}.arena-lobby-mobile-tabs{display:flex;gap:8px;grid-row:2;grid-column:1}.arena-lobby-mobile-tabs button{flex:1;min-height:44px;border:1px solid var(--agp-border);background:var(--agp-surface);color:var(--agp-text);border-radius:6px}.arena-lobby-mobile-tabs button[aria-pressed=true]{background:var(--agp-primary-soft);color:var(--agp-primary)}.lobby-page--workspace>.lobby-code-layout{grid-row:3;height:100%}.lobby-page--workspace>.lobby-game-layout{grid-row:3;height:100%;display:none!important}.lobby-page--workspace.lobby-page--field>.lobby-code-layout{display:none!important}.lobby-page--workspace.lobby-page--field>.lobby-game-layout{display:flex!important}}

.arena-queue-notice{display:flex;justify-content:space-between;align-items:center;gap:12px;grid-column:1/-1}.lobby-page--workspace>.arena-queue-notice{grid-row:2}.lobby-page--workspace:has(.arena-queue-notice){grid-template-rows:auto auto minmax(0,1fr)}.lobby-page--workspace:has(.arena-queue-notice)>.lobby-code-layout,.lobby-page--workspace:has(.arena-queue-notice)>.lobby-game-layout{grid-row:3}@media(max-width:900px){.lobby-page--workspace:has(.arena-queue-notice){grid-template-rows:auto auto auto minmax(0,1fr)}.lobby-page--workspace:has(.arena-queue-notice)>.arena-queue-notice{grid-row:3}.lobby-page--workspace:has(.arena-queue-notice)>.lobby-code-layout,.lobby-page--workspace:has(.arena-queue-notice)>.lobby-game-layout{grid-row:4}}

.lobby-page:not(.lobby-page--workspace){min-height:0}.lobby-page>:not(.lobby-head){margin-inline:0}
.arena-competition-panes{display:flex;gap:8px;margin-top:12px}.arena-competition-panes button{min-height:36px;border:1px solid var(--agp-border);border-radius:6px;background:var(--agp-surface);color:var(--agp-text-muted);padding:6px 12px}.arena-competition-panes button[aria-pressed=true]{background:var(--agp-primary-soft);color:var(--agp-primary)}@media(max-width:767px){.arena-competition-panes button,.lobby-dialog-close{min-height:44px;min-width:44px}}
</style>
