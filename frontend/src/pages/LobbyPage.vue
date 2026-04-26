<template>
  <section class="agp-grid lobby-page" :class="{ 'lobby-page--game': activeTab === 'game' }">
    <header class="agp-card p-2 lobby-head">
      <div class="lobby-title-block">
        <div class="lobby-title-line">
          <RouterLink class="agp-back-link" to="/lobbies">←</RouterLink>
          <h1 class="h4 mb-0">{{ lobby?.title || 'Лобби' }}</h1>
        </div>
      </div>
      <nav v-if="lobby" class="lobby-tabs" aria-label="Разделы лобби">
        <button v-if="canSeeCodeTab" :class="{ active: activeTab === 'code' }" @click="activeTab = 'code'">Код</button>
        <button :class="{ active: activeTab === 'lobby' }" @click="activeTab = 'lobby'">Лобби</button>
        <button v-if="canSeeGameTab" :class="{ active: activeTab === 'game' }" @click="activeTab = 'game'">
          <span
            class="lobby-game-signal"
            :class="`lobby-game-signal--${gameSignalTone}`"
            :title="gameSignalLabel"
            aria-hidden="true"
          ></span>
          Игра
        </button>
        <button v-if="activeCompetition" :class="{ active: activeTab === 'competition' }" @click="activeTab = 'competition'">
          Соревнование
        </button>
        <button v-if="competitionArchive.length" :class="{ active: activeTab === 'archive' }" @click="activeTab = 'archive'">
          Архив
        </button>
      </nav>
      <div v-if="lobby && hasPlayerInLobby" class="lobby-head-actions">
        <div class="lobby-ready-summary">
          <strong>{{ readyStatusLabel }}</strong>
          <span>{{ readyStatusHint }}</span>
        </div>
        <button
          v-if="showPlayAction"
          class="lobby-ready-icon lobby-ready-icon--play"
          :disabled="!canPlay || isBusy"
          :title="isBusy ? 'Обновляем статус' : 'Готов играть'"
          aria-label="Готов играть"
          @click="play"
        >
          {{ isBusy ? '…' : '▶' }}
        </button>
        <button
          v-if="showStopAction"
          class="lobby-ready-icon lobby-ready-icon--stop"
          :disabled="!canStop || isBusy"
          title="Не готов"
          aria-label="Не готов"
          @click="stop"
        >
          ■
        </button>
        <button
          v-if="canLeaveAsPlayer"
          class="lobby-action-icon"
          :disabled="isBusy"
          title="Прекратить участие"
          aria-label="Прекратить участие"
          @click="leaveAsPlayer"
        >
          ↩
        </button>
        <button
          v-if="canManage && !activeCompetition"
          class="lobby-action-icon"
          :disabled="isBusy"
          title="Начать соревнование"
          aria-label="Начать соревнование"
          @click="showCompetitionDialog = true"
        >
          ⚑
        </button>
        <button
          v-if="canManage"
          class="lobby-action-icon"
          :disabled="isBusy"
          title="Настройки лобби"
          aria-label="Настройки лобби"
          @click="showLobbySettingsDialog = true"
        >
          ⚙
        </button>
        <button
          v-if="canManage && canPauseLobby"
          class="lobby-action-icon"
          :disabled="isBusy"
          title="Пауза"
          aria-label="Пауза"
          @click="pauseLobbyByTeacher"
        >
          ❚❚
        </button>
        <button
          v-if="canManage && canStartLobby"
          class="lobby-action-icon lobby-action-icon--play"
          :disabled="isBusy"
          title="Запустить"
          aria-label="Запустить"
          @click="startLobbyByTeacher"
        >
          ▶
        </button>
        <button
          v-if="canManage && canStopLobbyByTeacher"
          class="lobby-action-icon lobby-action-icon--danger"
          :disabled="isBusy"
          title="Остановить"
          aria-label="Остановить"
          @click="stopLobbyByTeacher"
        >
          ■
        </button>
      </div>
      <div v-else-if="lobby && canManage" class="lobby-head-actions">
        <div class="lobby-ready-summary">
          <strong>{{ managerCycleStatusLabel }}</strong>
          <span>{{ managerCycleStatusHint }}</span>
        </div>
        <button class="btn btn-outline-secondary" :disabled="!canJoinAsPlayer || isBusy" @click="joinAsPlayer">
          {{ isBusy ? '...' : 'Участвовать как игрок' }}
        </button>
        <button
          v-if="!activeCompetition"
          class="lobby-action-icon"
          :disabled="isBusy"
          title="Начать соревнование"
          aria-label="Начать соревнование"
          @click="showCompetitionDialog = true"
        >
          ⚑
        </button>
        <button
          class="lobby-action-icon"
          :disabled="isBusy"
          title="Настройки лобби"
          aria-label="Настройки лобби"
          @click="showLobbySettingsDialog = true"
        >
          ⚙
        </button>
        <button
          v-if="canPauseLobby"
          class="lobby-action-icon"
          :disabled="isBusy"
          title="Пауза"
          aria-label="Пауза"
          @click="pauseLobbyByTeacher"
        >
          ❚❚
        </button>
        <button
          v-if="canStartLobby"
          class="lobby-action-icon lobby-action-icon--play"
          :disabled="isBusy"
          title="Запустить"
          aria-label="Запустить"
          @click="startLobbyByTeacher"
        >
          ▶
        </button>
        <button
          v-if="canStopLobbyByTeacher"
          class="lobby-action-icon lobby-action-icon--danger"
          :disabled="isBusy"
          title="Остановить"
          aria-label="Остановить"
          @click="stopLobbyByTeacher"
        >
          ■
        </button>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <article v-if="isLoading" class="agp-card p-4">
      <div class="agp-loading-state agp-loading-state--compact">Загрузка лобби...</div>
    </article>

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
      <article v-if="activeCompetition" class="agp-card p-3 lobby-competition-banner">
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
          <article class="lobby-competition-dialog" role="dialog" aria-modal="true" aria-labelledby="competition-dialog-title">
            <header class="lobby-dialog-head">
              <div>
                <h2 id="competition-dialog-title" class="h5 mb-1">Начать соревнование</h2>
                <p class="small text-muted mb-0">Старт заблокирует вход, выход и обычную очередь в этом лобби.</p>
              </div>
              <button
                class="lobby-dialog-close"
                type="button"
                aria-label="Закрыть"
                :disabled="isBusy"
                @click="showCompetitionDialog = false"
              >
                ×
              </button>
            </header>

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
                :disabled="isBusy || Boolean(activeCompetition)"
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
          <article class="lobby-settings-dialog" role="dialog" aria-modal="true" aria-labelledby="lobby-settings-dialog-title">
            <header class="lobby-dialog-head">
              <div>
                <h2 id="lobby-settings-dialog-title" class="h5 mb-1">Настройки лобби</h2>
                <p class="small text-muted mb-0">Доступ, лимит игроков и автоочистка тренировочных матчей.</p>
              </div>
              <button
                class="lobby-dialog-close"
                type="button"
                aria-label="Закрыть"
                :disabled="isSavingLobbySettings"
                @click="showLobbySettingsDialog = false"
              >
                ×
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
              <label class="lobby-competition-setting lobby-competition-setting--wide">
                <span>Автоудаление старых тренировочных матчей, дней</span>
                <input
                  v-model.trim="lobbySettingsRetentionDays"
                  class="form-control form-control-sm mono"
                  type="number"
                  min="1"
                  max="3650"
                  placeholder="без автоочистки"
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
          <article class="lobby-player-code-dialog" role="dialog" aria-modal="true" aria-labelledby="player-code-dialog-title">
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
                ×
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
                    <button class="btn btn-sm btn-outline-secondary" :disabled="!activeTemplate || !canEditSelectedCode" @click="applyTemplate">
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
                <CodeEditor v-model="editorCode" :readonly="!activeSlotKey || !canEditSelectedCode" />
              </article>
            </div>
            <div v-else class="agp-loading-state agp-loading-state--compact">Загрузка кода...</div>
          </article>
        </div>
      </Teleport>

      <section v-if="activeTab === 'code' && canSeeCodeTab && workspace" class="lobby-code-layout">
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
          <div class="lobby-editor-toolbar">
            <div>
              <h2 class="h6 mb-1">{{ activeSlotKey || 'Код' }}</h2>
              <p class="small mb-0">{{ codeStateLabel }}</p>
            </div>
            <div class="d-flex gap-2 flex-wrap">
              <button class="btn btn-sm btn-outline-secondary" :disabled="!activeTemplate || !canEditSelectedCode" @click="applyTemplate">
                Шаблон
              </button>
              <button
                v-if="canUseDemoStrategy"
                class="btn btn-sm btn-outline-secondary"
                :disabled="!activeDemoStrategy || !canEditSelectedCode"
                @click="applyDemoStrategy"
              >
                Пример
              </button>
              <button class="btn btn-sm btn-dark" :disabled="!canSaveCode" @click="saveCode">
                {{ isSavingCode ? 'Сохранение...' : 'Сохранить' }}
              </button>
            </div>
          </div>
          <CodeEditor v-model="editorCode" :readonly="!activeSlotKey || !canEditSelectedCode" />
        </article>
      </section>
      <section v-else-if="activeTab === 'code' && canSeeCodeTab" class="agp-card p-4 lobby-code-empty">
        <h2 class="h5 mb-2">Код пока недоступен</h2>
        <p class="text-muted mb-0">
          Рабочее место появится после присоединения к лобби как игрок.
        </p>
      </section>

      <section v-else-if="activeTab === 'lobby'" class="lobby-state-grid">
        <div class="lobby-main-stack">
          <article class="agp-card p-3 lobby-matches-card">
            <header class="lobby-section-head">
              <div>
                <h2 class="h6 mb-1">Матчи</h2>
                <p class="small text-muted mb-0">Последние игры в этом лобби.</p>
              </div>
              <span class="lobby-count-pill">{{ allTrainingMatchGroups.length }} всего</span>
            </header>
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
                </article>
              </section>
              <div v-if="!allTrainingMatchGroups.length" class="agp-empty-state agp-empty-state--compact">
                Матчей пока нет.
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
                <p class="small text-muted mb-0">Статус и средняя статистика игроков.</p>
              </div>
              <button
                v-if="canUseAdminBots"
                class="btn btn-sm btn-outline-secondary"
                :disabled="isBusy || !canAddBot"
                @click="addDemoBot"
              >
                {{ isBusy ? 'Добавляем...' : 'Добавить бота' }}
              </button>
            </header>
            <div v-if="lobbyLeaderboard.length" class="lobby-leaderboard-list">
              <div v-for="(stat, index) in lobbyLeaderboard" :key="stat.team_id" class="lobby-leaderboard-row">
                <span class="lobby-leaderboard-place">{{ index + 1 }}</span>
                <div>
                  <header class="lobby-leaderboard-player-head">
                    <strong>{{ stat.display_name }}</strong>
                    <span class="lobby-status-badge" :class="`lobby-status-badge--${teamStatusTone(stat.team_id)}`">
                      {{ teamStatusLabel(stat.team_id) }}
                    </span>
                  </header>
                  <span>
                    побед {{ stat.wins }} · игр {{ stat.matches_total }} · средний счет {{ averageScoreLabel(stat.average_score) }}
                  </span>
                </div>
                <div class="lobby-leaderboard-actions">
                  <button
                    v-if="canManage"
                    class="btn btn-sm btn-outline-secondary"
                    :disabled="isBusy"
                    @click="openPlayerCode(stat)"
                  >
                    Код
                  </button>
                  <button
                    v-if="canUseAdminBots"
                    class="lobby-remove-player"
                    :disabled="isBusy || Boolean(activeCompetition)"
                    title="Удалить игрока из лобби"
                    aria-label="Удалить игрока из лобби"
                    @click="removeTeamFromLobby(stat)"
                  >
                    ×
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="agp-empty-state agp-empty-state--compact">Статистика появится после первых матчей.</div>
          </article>
        </aside>
      </section>

      <section v-else-if="activeTab === 'game'" class="lobby-game-layout">
        <article class="lobby-game-view">
          <iframe
            v-if="displayedGameRunId"
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
          <div v-if="!displayedGameRunId" class="lobby-empty">
            <h2 class="h6">Текущей игры пока нет</h2>
            <p class="small text-muted mb-0">Заполните код и нажмите Play. Изменения попадут в следующую игру.</p>
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
              :class="{ active: selectedTrainingRunId === choice.run_id }"
              @click="selectedTrainingRunId = choice.run_id"
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

      <section v-else-if="activeTab === 'competition' && activeCompetition" class="agp-card p-3 lobby-competition-panel">
        <div class="d-flex justify-content-between gap-3 flex-wrap">
          <div>
            <h2 class="h6 mb-1">{{ cleanCompetitionTitle(activeCompetition.title) }}</h2>
            <p class="small text-muted mb-0">
              {{ competitionStatusLabel(activeCompetition.status) }} · матч {{ activeCompetitionBoundsLabel }} · проходят {{ activeCompetition.advancement_top_k }}
            </p>
          </div>
          <div v-if="canManage" class="d-flex gap-2 flex-wrap">
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
        <div v-if="competitionTeamStats.length" class="lobby-competition-leaderboard mt-3">
          <h3 class="h6 mb-0">Итоги команд</h3>
          <div class="lobby-competition-stat-list">
            <div v-for="stat in competitionTeamStats" :key="stat.team_id" class="lobby-competition-stat-row">
              <strong>{{ stat.name }}</strong>
              <span>побед {{ stat.wins }} · поражений {{ stat.losses }} · очков {{ scoreLabel(stat.points) }}</span>
            </div>
          </div>
        </div>
        <div v-if="activeCompetition.rounds.length" class="lobby-rounds mt-3">
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
                    :to="`/runs/${matchPrimaryRunId(match)}/watch`"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Смотреть
                  </RouterLink>
                </div>
              </div>
              <div class="lobby-competition-team-rows">
                <div
                  v-for="teamId in match.team_ids"
                  :key="`${match.match_id}-${teamId}`"
                  class="lobby-competition-team-row"
                  :class="{ winner: match.advanced_team_ids.includes(teamId), loser: isCompetitionMatchLoser(match, teamId) }"
                >
                  <strong>{{ teamLabel(teamId) }}</strong>
                  <span>{{ competitionTeamMatchSummary(match, teamId) }}</span>
                </div>
              </div>
              <div v-if="match.tie_break_reason" class="small text-warning">{{ match.tie_break_reason }}</div>
            </article>
          </section>
        </div>
        <div v-else class="agp-empty-state agp-empty-state--compact mt-3">Сетка появится после старта первого раунда.</div>
      </section>

      <section v-else-if="activeTab === 'archive'" class="agp-card p-3">
        <h2 class="h6 mb-3">Архив соревнований</h2>
        <div class="lobby-match-list">
          <RouterLink
            v-for="item in competitionArchive"
            :key="item.competition_id"
            class="lobby-match-row"
            :to="`/competitions/${item.competition_id}`"
          >
            <span>
              <strong>{{ cleanCompetitionTitle(item.title) }}</strong>
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
import { computed, defineComponent, h, onMounted, onUnmounted, ref, watch, type PropType } from 'vue';
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';

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
  stopLobby,
  updateLobby,
  updateSlotCode,
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

interface EmbeddedGameFrame {
  runId: string;
  status: RunDto['status'];
  tick: number;
  phase: string;
  frame: Record<string, unknown>;
  replayFrameIndex: number;
  replayFrameCount: number;
  participants: Array<{
    run_id: string;
    team_id: string;
    display_name: string;
    captain_user_id: string;
    is_current: boolean;
  }>;
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
const trainingRuns = ref<RunDto[]>([]);
const competitionArchive = ref<LobbyCompetitionDto[]>([]);
const activeTab = ref<'code' | 'lobby' | 'game' | 'competition' | 'archive'>('code');
const activeSlotKey = ref('');
const editorCode = ref('');
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
const lobbySettingsRetentionDays = ref('');
const lobbySettingsTouched = ref(false);
const competitionMatchSize = ref(2);
const competitionAdvanceTopK = ref(1);
const competitionTieBreakPolicy = ref<TieBreakPolicy>('manual');
const competitionCodePolicy = ref<CompetitionCodePolicy>('locked_on_start');
const lastGameRunId = ref('');
const selectedTrainingRunId = ref('');
const displayedGameWatchUrl = ref('');
const matchPage = ref(1);
const matchesPerPage = 5;
const embeddedGameFrame = ref<EmbeddedGameFrame | null>(null);
const showCompetitionDialog = ref(false);
const showPlayerCodeDialog = ref(false);
const showLobbySettingsDialog = ref(false);
const trainingRunsRefreshSignature = ref('');
let isRefreshingTrainingRuns = false;
let codeAutosaveHandle: ReturnType<typeof setTimeout> | null = null;
let lobbyEventSource: EventSource | null = null;
let pollingHandle: ReturnType<typeof setInterval> | null = null;
let competitionPollingHandle: ReturnType<typeof setInterval> | null = null;

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
  return statsByTeam.value[teamId]?.display_name ?? teamId;
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
  const retention = lobbySettingsRetentionDays.value ? Number(lobbySettingsRetentionDays.value) : null;
  return {
    title: lobbySettingsTitle.value.trim(),
    access: lobbySettingsAccess.value,
    access_code: lobbySettingsAccess.value === 'code' && lobbySettingsAccessCode.value.trim() ? lobbySettingsAccessCode.value.trim() : null,
    max_teams: maxTeams,
    auto_delete_training_runs_days: retention,
  };
});
const lobbySettingsValid = computed(() => {
  const payload = lobbySettingsPayload.value;
  if (payload.title.length < 2) return false;
  if (!Number.isFinite(payload.max_teams) || payload.max_teams < 1 || payload.max_teams > 512) return false;
  if (payload.access === 'code' && lobby.value?.access !== 'code' && !payload.access_code) return false;
  if (
    payload.auto_delete_training_runs_days !== null &&
    (!Number.isFinite(payload.auto_delete_training_runs_days) ||
      payload.auto_delete_training_runs_days < 1 ||
      payload.auto_delete_training_runs_days > 3650)
  ) {
    return false;
  }
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
    payload.max_teams !== current.max_teams ||
    payload.auto_delete_training_runs_days !== current.auto_delete_training_runs_days
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
      filledRequiredSlots.value === requiredSlotCount.value &&
      !isDirty.value,
  ),
);
const canStop = computed(
  () => canUseTrainingQueue.value && (lobby.value?.my_status === 'queued' || lobby.value?.my_status === 'playing'),
);
const showPlayAction = computed(() => lobby.value?.my_status !== 'queued' && lobby.value?.my_status !== 'playing');
const showStopAction = computed(() => lobby.value?.my_status === 'queued' || lobby.value?.my_status === 'playing');
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
  if (status === 'open' || status === 'draft') return 'agp-pill--primary';
  if (status === 'running') return 'agp-pill--warning';
  if (status === 'closed' || status === 'stopped') return 'agp-pill--danger';
  return 'agp-pill--neutral';
}

function teamStatusLabel(teamId: string): string {
  if (lobby.value?.playing_team_ids.includes(teamId)) return 'играет';
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
  lobbySettingsRetentionDays.value = lobby.value.auto_delete_training_runs_days === null
    ? ''
    : String(lobby.value.auto_delete_training_runs_days);
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
          lobby.value.auto_delete_training_runs_days,
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
  return 'Цикл лобби запустит матч, когда будет достаточно готовых игроков.';
});
const currentCompetitionMatch = computed(() => {
  const competition = activeCompetition.value;
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!competition) return null;
  const currentRound = competition.rounds.find((round) => round.round_index === competition.current_round_index);
  if (!currentRound) return null;
  if (myTeamId) {
    return currentRound.matches.find(
      (match) =>
        effectiveCompetitionMatchStatus(match) === 'running' &&
        match.team_ids.includes(myTeamId) &&
        Boolean(match.run_ids_by_team[myTeamId]),
    ) ?? null;
  }
  if (!canManage.value) return null;
  return currentRound.matches.find(
    (match) => effectiveCompetitionMatchStatus(match) === 'running' && Boolean(matchPrimaryRunId(match)),
  ) ?? null;
});
const currentCompetitionRun = computed(() => {
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!activeCompetition.value) return null;
  const activeStatuses = new Set(['created', 'queued', 'running']);
  if (!myTeamId && canManage.value) {
    return competitionRuns.value.find((item) => activeStatuses.has(item.status)) ?? null;
  }
  if (!myTeamId) return null;
  return competitionRuns.value.find((item) => item.team_id === myTeamId && activeStatuses.has(item.status)) ?? null;
});
const currentCompetitionRunId = computed(() => {
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!activeCompetition.value) return '';
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
function buildDisplayedGameWatchUrl(runId: string): string {
  if (!runId) return '';
  const params = new URLSearchParams({
    embed: '1',
    autoplay: '1',
    speed_ms: String(lobby.value?.cycle_frame_ms ?? 500),
    show_print: canShowDisplayedRunPrint.value ? '1' : '0',
  });
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
  if (competition.code_policy === 'allowed_between_matches') return Boolean(currentCompetitionRun.value);
  return false;
});
const canEditSelectedCode = computed(() =>
  Boolean(
    codeWorkspaceTeamId.value &&
      activeSlotKey.value &&
      (canManage.value || codeWorkspaceTeamId.value === lobby.value?.my_team_id) &&
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
const currentReplayChoices = computed(() =>
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
const allTrainingMatchGroups = computed(() => [
  ...currentTrainingMatchGroups.value,
  ...archivedTrainingMatchGroups.value,
]);
const matchPageCount = computed(() =>
  Math.max(1, Math.ceil(allTrainingMatchGroups.value.length / matchesPerPage))
);
const pagedTrainingMatchGroups = computed(() => {
  const start = (matchPage.value - 1) * matchesPerPage;
  return allTrainingMatchGroups.value.slice(start, start + matchesPerPage);
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
    return;
  }
  if (selectedTrainingRunId.value && choices.some((choice) => choice.run_id === selectedTrainingRunId.value)) {
    return;
  }
  const preferred = lobby.value?.current_run_id;
  selectedTrainingRunId.value = choices.find((choice) => choice.run_id === preferred)?.run_id ?? choices[0].run_id;
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
const frameGameStats = computed<CurrentGameStatRow[]>(() => {
  const message = embeddedGameFrame.value;
  if (!message || message.runId !== displayedGameRunId.value) return [];
  const players = collectFrameGamePlayers(message);
  return dedupeCurrentGameStats(players.map((player, index) => buildCurrentGameStatFromFrame(message, player, index)));
});
const currentGameStats = computed<CurrentGameStatRow[]>(() =>
  sortCurrentGameStats(frameGameStats.value.length
    ? frameGameStats.value
    : displayedTrainingRunIds.value.flatMap((runId) => {
      const trainingRun = trainingRunsById.value[runId];
      if (trainingRun) {
        return [{
          run_id: trainingRun.run_id,
          team_id: trainingRun.team_id,
          display_name: teamLabel(trainingRun.team_id),
          status: runStatusLabel(trainingRun.status),
          score: runScoreLabel(trainingRun),
          scoreValue: extractRunScore(isRecord(trainingRun.result_payload) ? trainingRun.result_payload : {}, trainingRun.team_id),
          lifePercent: 0,
          shieldPercent: 0,
          meta: '',
          isSelf: trainingRun.team_id === lobby.value?.my_team_id,
        }];
      }
      const competitionRun = competitionRunsById.value[runId];
      if (!competitionRun) return [];
      return [{
        run_id: competitionRun.run_id,
        team_id: competitionRun.team_id,
        display_name: teamLabel(competitionRun.team_id),
        status: runStatusLabel(competitionRun.status as RunDto['status']),
        score: 'пока нет',
        scoreValue: null,
        lifePercent: 0,
        shieldPercent: 0,
        meta: '',
        isSelf: competitionRun.team_id === lobby.value?.my_team_id,
      }];
    })),
);
const currentGameFrameLabel = computed(() => {
  const message = embeddedGameFrame.value;
  if (!message || message.runId !== displayedGameRunId.value) {
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
  if (!message || message.runId !== displayedGameRunId.value) {
    return lobby.value?.cycle_phase_label || (displayedGameRunId.value ? 'ожидаем кадры' : 'нет активной игры');
  }
  return gamePhaseLabel(message.phase, message.status);
});
const gameSignalTone = computed<'red' | 'yellow' | 'green'>(() => {
  const phase = lobby.value?.cycle_phase;
  if (phase === 'replay' || phase === 'result') return 'green';
  if (phase === 'simulation' || phase === 'waiting_viewer' || displayedGameRunId.value) return 'yellow';
  return 'red';
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
  if (!message || message.runId !== displayedGameRunId.value) return false;
  if (message.replayFrameCount > 1) return message.replayFrameIndex >= message.replayFrameCount - 1;
  return message.phase === 'finished';
});
const currentGameLeaderLabel = computed(() => {
  const leader = [...currentGameStats.value].sort((left, right) => {
    const rightScore = right.scoreValue ?? Number.NEGATIVE_INFINITY;
    const leftScore = left.scoreValue ?? Number.NEGATIVE_INFINITY;
    return rightScore - leftScore;
  })[0];
  return leader?.display_name ?? '—';
});
const currentGameWinnerLabel = computed(() => {
  const groupWinners = displayedGameMatchGroup.value?.winner_team_ids ?? [];
  if (groupWinners.length) return groupWinners.map(teamLabel).join(', ');

  const competitionMatch = currentCompetitionMatch.value;
  if (competitionMatch?.advanced_team_ids.length) {
    return competitionMatch.advanced_team_ids.map(teamLabel).join(', ');
  }

  return currentGameLeaderLabel.value;
});
const statsByTeam = computed(() => {
  const result: Record<string, LobbyParticipantStatsDto> = {};
  for (const stat of lobby.value?.participant_stats ?? []) result[stat.team_id] = stat;
  return result;
});
const lobbyLeaderboard = computed(() =>
  [...(lobby.value?.participant_stats ?? [])].sort((left, right) => {
    const rightPoints = totalScore(right);
    const leftPoints = totalScore(left);
    if (rightPoints !== leftPoints) return rightPoints - leftPoints;
    const rightAverage = right.average_score ?? Number.NEGATIVE_INFINITY;
    const leftAverage = left.average_score ?? Number.NEGATIVE_INFINITY;
    if (rightAverage !== leftAverage) return rightAverage - leftAverage;
    if (right.wins !== left.wins) return right.wins - left.wins;
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
  if (canManage.value && codeWorkspaceTeamId.value && codeWorkspaceTeamId.value !== lobby.value?.my_team_id) {
    return isDirty.value
      ? `Есть несохраненные изменения в коде игрока ${selectedCodePlayerName.value}.`
      : `Редактируете код игрока ${selectedCodePlayerName.value}.`;
  }
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
  return value === null ? 'нет данных' : value.toFixed(1);
}

function averageScoreLabel(value: number | null | undefined): string {
  return value === null || value === undefined ? 'нет данных' : value.toFixed(1);
}

function totalScore(stat: LobbyParticipantStatsDto): number {
  if (stat.average_score === null || stat.average_score === undefined) return Number.NEGATIVE_INFINITY;
  return stat.average_score * stat.matches_total;
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
  const winners = matchGroupWinnerIds(group);
  return winners.length ? winners.map(teamLabel).join(', ') : 'не определен';
}

function shouldHideMatchWinner(group: TrainingMatchGroup): boolean {
  return group.status === 'replay';
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
    return [...placements.entries()].filter(([, placement]) => placement === bestPlacement).map(([teamId]) => teamId);
  }
  if (scores.size) {
    const bestScore = Math.max(...scores.values());
    return [...scores.entries()].filter(([, score]) => score === bestScore).map(([teamId]) => teamId);
  }
  return [];
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
  return statsByTeam.value[teamId]?.display_name ?? teamId;
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
        value.team_id !== undefined ||
        value.score !== undefined ||
        value.points !== undefined ||
        value.life !== undefined ||
        value.hp !== undefined ||
        value.shield !== undefined ||
        value.coins !== undefined
      );
    if (hasPlayerShape) {
      const id = String(value.team_id ?? value.key ?? value.role ?? value.name ?? `player-${byId.size + 1}`);
      byId.set(id, value);
    }
    Object.values(value).forEach(visit);
  };

  visit(frame);
  collectSnakeGamePlayers(byId, message);
  return [...byId.values()];
}

function collectRoleMapGamePlayers(byId: Map<string, Record<string, unknown>>, message: EmbeddedGameFrame): void {
  const frame = message.frame;
  const positions = isRecord(frame.positions) ? frame.positions : null;
  if (!positions) return;

  const batteries = isRecord(frame.batteries) ? frame.batteries : {};
  const collected = isRecord(frame.collected) ? frame.collected : {};
  const invalidMoves = isRecord(frame.invalid_moves) ? frame.invalid_moves : {};
  const slotScores = isRecord(frame.slot_scores) ? frame.slot_scores : {};
  Object.keys(positions).forEach((role, index) => {
    const participant = message.participants[index];
    const teamId = participant?.team_id ?? role;
    const collectedValue = numericFrameValue(collected[role]) ?? 0;
    const batteryValue = numericFrameValue(batteries[role]);
    const invalidValue = numericFrameValue(invalidMoves[role]) ?? 0;
    const score = numericFrameValue(slotScores[role])
      ?? Math.max(0, collectedValue * 100 + (batteryValue ?? 0) - invalidValue * 10);
    byId.set(teamId, {
      team_id: teamId,
      name: participant?.display_name || role,
      role,
      score,
      battery: batteryValue,
      collected: collectedValue,
      invalid_moves: invalidValue,
      alive: batteryValue === null ? true : batteryValue > 0,
    });
  });
}

function collectSnakeGamePlayers(byId: Map<string, Record<string, unknown>>, message: EmbeddedGameFrame): void {
  const frame = message.frame;
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

    byId.set(teamId, {
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

function buildCurrentGameStatFromFrame(
  message: EmbeddedGameFrame,
  player: Record<string, unknown>,
  index: number,
): CurrentGameStatRow {
  const teamId = typeof player.team_id === 'string' ? player.team_id : '';
  const name = typeof player.name === 'string' ? player.name : '';
  const scoreValue = numericFrameValue(player.score ?? player.points);
  const life = numericFrameValue(player.life ?? player.hp);
  const shield = numericFrameValue(player.shield);
  const alive = typeof player.alive === 'boolean' ? player.alive : life !== 0;
  return {
    run_id: message.runId,
    team_id: teamId || `frame-player-${index}`,
    display_name: teamId ? teamLabel(teamId) : name || `Игрок ${index + 1}`,
    status: message.phase === 'finished' ? (alive ? 'финиш' : 'выбыл') : alive ? 'в игре' : 'выбыл',
    score: framePlayerScoreLabel(player),
    scoreValue,
    lifePercent: percentFrameValue(life, 50),
    shieldPercent: percentFrameValue(shield, 25),
    meta: framePlayerMetaLabel(player),
    isSelf: teamId === lobby.value?.my_team_id,
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

  const put = (row: CurrentGameStatRow): void => {
    const normalizedName = normalizeGameStatName(row.display_name);
    if (
      isSyntheticFrameTeamId(row.team_id) &&
      normalizedName &&
      concreteNames.some((name) => name.includes(normalizedName) || normalizedName.includes(name))
    ) {
      return;
    }

    const key = isSyntheticFrameTeamId(row.team_id) ? normalizedName || row.team_id : row.team_id;
    const previous = result.get(key);
    if (!previous) {
      result.set(key, row);
      return;
    }

    const previousHasScore = previous.scoreValue !== null;
    const rowHasScore = row.scoreValue !== null;
    if ((!previousHasScore && rowHasScore) || row.meta.length > previous.meta.length) {
      result.set(key, row);
    }
  };

  rows.forEach(put);
  return [...result.values()];
}

function numericFrameValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function percentFrameValue(value: number | null, max: number): number {
  if (value === null) return 0;
  return Math.max(0, Math.min(100, (value / max) * 100));
}

function framePlayerScoreLabel(player: Record<string, unknown>): string {
  const parts: string[] = [];
  const score = player.score;
  if (typeof score === 'number' && Number.isFinite(score)) {
    parts.push(scoreLabel(score));
  }

  const details: Array<[string, string]> = [
    ['очки', 'points'],
    ['монеты', 'coins'],
    ['энергия', 'collected'],
    ['еда', 'food_eaten'],
    ['длина', 'length'],
    ['заряд', 'battery'],
    ['жизни', 'life'],
    ['хиты', 'hits'],
    ['урон', 'damage'],
    ['ошибки', 'invalid_moves'],
  ];
  for (const [label, key] of details) {
    const value = player[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
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
  if (typeof payload.runId !== 'string' || !isRecord(payload.frame)) return;

  embeddedGameFrame.value = {
    runId: payload.runId,
    status: isRunStatus(payload.status) ? payload.status : 'running',
    tick: typeof payload.tick === 'number' && Number.isFinite(payload.tick) ? payload.tick : 0,
    phase: typeof payload.phase === 'string' ? payload.phase : '',
    frame: payload.frame,
    replayFrameIndex: typeof payload.replayFrameIndex === 'number' ? payload.replayFrameIndex : 0,
    replayFrameCount: typeof payload.replayFrameCount === 'number' ? payload.replayFrameCount : 0,
    participants: Array.isArray(payload.participants)
      ? payload.participants.filter(isEmbeddedParticipant)
      : [],
  };
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
    if (slot) slot.code = code;
    if (activeSlotKey.value === slotKey) savedCode.value = code;
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
  codeAutosaveHandle = setTimeout(() => {
    void flushCodeAutosave();
  }, 900);
}

async function selectSlot(slotKey: string): Promise<void> {
  await flushCodeAutosave();
  const slot = slotStates.value.find((item) => item.slot_key === slotKey);
  isHydratingEditor.value = true;
  activeSlotKey.value = slotKey;
  editorCode.value = slot?.code ?? '';
  savedCode.value = slot?.code ?? '';
  requestAnimationFrame(() => {
    isHydratingEditor.value = false;
  });
}

function applyTemplate(): void {
  if (!activeTemplate.value) return;
  editorCode.value = activeTemplate.value;
}

function applyDemoStrategy(): void {
  if (!canUseDemoStrategy.value) return;
  if (!activeDemoStrategy.value) return;
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
    savedCode.value = slot?.code ?? '';
    if (!wasDirty) {
      isHydratingEditor.value = true;
      editorCode.value = savedCode.value;
      requestAnimationFrame(() => {
        isHydratingEditor.value = false;
      });
    }
  }
}

async function refreshCompetitions(): Promise<void> {
  if (!lobby.value) return;
  const lobbyIdValue = lobby.value.lobby_id;
  const competitions = await listCompetitions();
  activeCompetition.value =
    competitions.find(
      (item) => item.lobby_id === lobbyIdValue && item.status !== 'finished',
    ) ?? null;
  competitionRuns.value = activeCompetition.value
    ? await listCompetitionRuns(activeCompetition.value.competition_id)
    : [];
  const archive = await listLobbyCompetitionArchive(lobby.value.lobby_id);
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
  if (!lobby.value) return;
  if (isRefreshingTrainingRuns) return;
  isRefreshingTrainingRuns = true;
  try {
    trainingRuns.value = await listRuns({
      lobby_id: lobby.value.lobby_id,
      run_kind: 'training_match',
    });
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
  if (canManage.value) {
    lobby.value = await getLobby(id);
  } else {
    try {
      lobby.value = await joinLobbyAsUser({
        lobby_id: id,
        access_code: lobbyAccessCode.value.trim() || null,
      });
      lobbyAccessCode.value = '';
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      if (message.includes('код доступа')) {
        joinRequired.value = true;
        lobby.value = null;
        return;
      }
      throw error;
    }
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

async function refreshLobbyOnly(): Promise<void> {
  if (!lobby.value) return;
  lobby.value = await getLobby(lobby.value.lobby_id);
  await refreshTrainingRuns();
  await refreshCompetitions();
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
      auto_delete_training_runs_days: payload.auto_delete_training_runs_days,
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
  if (!lobby.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
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
    await startLobbyCompetition({
      lobby_id: lobby.value.lobby_id,
      title: `${lobby.value.title} / соревнование`,
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
  const source = new EventSource(
    `/api/v1/lobbies/${encodeURIComponent(lobby.value.lobby_id)}/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`
  );
  lobbyEventSource = source;
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
  source.onerror = () => {
    stopLiveUpdates();
    startPolling();
  };
}

function startCompetitionPolling(): void {
  stopCompetitionPolling();
  competitionPollingHandle = setInterval(() => {
    void refreshCompetitions();
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
    void refreshLobbyOnly();
  }, 5000);
}

function stopLiveUpdates(): void {
  if (lobbyEventSource) {
    lobbyEventSource.close();
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
    if (embeddedGameFrame.value?.runId !== runId) embeddedGameFrame.value = null;
    if (runId) lastGameRunId.value = runId;
  }
);

watch(
  () => [
    displayedGameRunId.value,
    lobby.value?.replay_started_at ?? '',
    lobby.value?.cycle_frame_ms ?? 500,
    canShowDisplayedRunPrint.value ? 'print' : 'no-print',
  ].join('|'),
  () => {
    displayedGameWatchUrl.value = buildDisplayedGameWatchUrl(displayedGameRunId.value);
  },
  { immediate: true },
);

watch(editorCode, () => {
  if (isHydratingEditor.value) return;
  scheduleCodeAutosave();
});

watch(activeTab, (_nextTab, previousTab) => {
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

onMounted(async () => {
  window.addEventListener('message', handleEmbeddedGameFrameMessage);
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
  clearCodeAutosave();
  window.removeEventListener('message', handleEmbeddedGameFrameMessage);
  stopLiveUpdates();
  stopCompetitionPolling();
});
</script>

<style scoped>
.lobby-page {
  min-height: 100dvh;
  gap: 0.6rem;
  align-content: start;
  grid-auto-rows: max-content;
  padding: 0;
  background-color: #eef4fb;
  background-image:
    url("data:image/svg+xml,%3Csvg width='160' height='160' viewBox='0 0 160 160' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.12' stroke-width='2'%3E%3Cpath d='M16 16h28v28H16zM116 16h28v28h-28zM16 116h28v28H16zM116 116h28v28h-28z'/%3E%3Cpath d='M64 80h32M80 64v32M0 80h24M136 80h24M80 0v24M80 136v24'/%3E%3C/g%3E%3C/svg%3E"),
    radial-gradient(circle at 12% 8%, rgba(45, 212, 191, 0.22), transparent 26rem),
    radial-gradient(circle at 85% 18%, rgba(251, 191, 36, 0.18), transparent 24rem),
    linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
  background-size: 160px 160px, auto, auto, auto;
}

.lobby-page--game {
  gap: 0;
  background-color: #020617;
  background-image:
    url("data:image/svg+xml,%3Csvg width='144' height='144' viewBox='0 0 144 144' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.14' stroke-width='1.5'%3E%3Cpath d='M18 18h30v30H18zM96 18h30v30H96zM18 96h30v30H18zM96 96h30v30H96z'/%3E%3Cpath d='M72 0v144M0 72h144'/%3E%3C/g%3E%3C/svg%3E"),
    radial-gradient(circle at 14% 12%, rgba(20, 184, 166, 0.24), transparent 28rem),
    radial-gradient(circle at 82% 20%, rgba(59, 130, 246, 0.18), transparent 24rem),
    linear-gradient(135deg, #030712 0%, #071528 50%, #020617 100%);
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
  flex-wrap: nowrap;
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
  width: 2.45rem;
  height: 2.45rem;
  border: 1px solid transparent;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 1rem;
  font-weight: 900;
  line-height: 1;
}

.lobby-ready-icon:disabled {
  opacity: 0.38;
}

.lobby-ready-icon--play {
  background: #0f9f8e;
  box-shadow: 0 8px 18px rgba(15, 159, 142, 0.22);
  color: #fff;
}

.lobby-ready-icon--stop {
  border-color: #d4dde7;
  background: #fff;
  color: #8b98a8;
}

.lobby-action-icon {
  width: 2.25rem;
  height: 2.25rem;
  border: 1px solid rgba(148, 163, 184, 0.42);
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.82);
  color: #334155;
  font-size: 0.95rem;
  font-weight: 900;
  line-height: 1;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.lobby-action-icon:hover:not(:disabled) {
  border-color: rgba(20, 184, 166, 0.7);
  color: #0f766e;
}

.lobby-action-icon:disabled {
  opacity: 0.45;
}

.lobby-action-icon--play {
  border-color: transparent;
  background: #0f9f8e;
  color: #fff;
}

.lobby-action-icon--danger {
  border-color: rgba(244, 63, 94, 0.36);
  color: #be123c;
}

.lobby-access-card {
  justify-content: space-between;
  background: #f8fafc;
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
  border-color: rgba(217, 119, 6, 0.35);
  background: #fff7ed;
}

.lobby-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: grid;
  place-items: start end;
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
  background:
    url("data:image/svg+xml,%3Csvg width='112' height='112' viewBox='0 0 112 112' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2314b8a6' stroke-opacity='.14'%3E%3Cpath d='M16 16h24v24H16zM72 16h24v24H72zM44 64h24v24H44z'/%3E%3Cpath d='M40 28h32M56 40v24'/%3E%3C/g%3E%3C/svg%3E") right 0.8rem bottom 0.8rem / 8rem auto no-repeat,
    #ffffff;
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
  width: 2rem;
  height: 2rem;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: #fff;
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
  font-weight: 800;
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

.lobby-game-signal--red {
  background: #ef4444;
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
  border-color: rgba(34, 211, 238, 0.24);
  background:
    url("data:image/svg+xml,%3Csvg width='128' height='96' viewBox='0 0 128 96' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.12'%3E%3Cpath d='M16 16h24v24H16zM88 16h24v24H88zM52 52h24v24H52z'/%3E%3Cpath d='M40 28h12M76 64h12M64 0v16M64 80v16'/%3E%3C/g%3E%3C/svg%3E") right 0.75rem top 0.75rem / 9rem auto no-repeat,
    linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.98));
  color: #e5f3ff;
  box-shadow: 0 18px 48px rgba(2, 6, 23, 0.2);
}

.lobby-roles::before,
.lobby-editor::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.18rem;
  background: linear-gradient(90deg, #22d3ee, #14b8a6, #facc15);
  opacity: 0.82;
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
  color: #8ea7c1;
  font-size: 0.78rem;
}

.lobby-role-progress {
  height: 0.42rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
}

.lobby-role-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #22d3ee, #14b8a6, #facc15);
  box-shadow: 0 0 18px rgba(34, 211, 238, 0.32);
}

.lobby-role-button {
  position: relative;
  z-index: 1;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 0.55rem;
  background: rgba(15, 23, 42, 0.64);
  color: #dbeafe;
  padding: 0.55rem 0.65rem;
  display: grid;
  gap: 0.1rem;
  text-align: left;
}

.lobby-role-button.active {
  border-color: rgba(45, 212, 191, 0.72);
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.32), rgba(15, 23, 42, 0.72));
  box-shadow: 0 10px 24px rgba(20, 184, 166, 0.12);
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
  box-shadow: 0 0 0 0.18rem rgba(245, 158, 11, 0.12);
}

.lobby-role-button.filled span i {
  background: #14b8a6;
  box-shadow: 0 0 0 0.18rem rgba(20, 184, 166, 0.14);
}

.lobby-role-button span,
.lobby-participant-column h3 {
  font-weight: 850;
}

.lobby-role-button small,
.lobby-player-meta,
.lobby-stat-row span {
  color: var(--agp-text-muted);
}

.lobby-role-button small {
  color: #8ea7c1;
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
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.18rem;
  background: linear-gradient(90deg, #14b8a6, #2563eb, #f59e0b);
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
  background: #edf8f6;
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
  background: #f8fafc;
}

.lobby-competition-stat-list {
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 0.5rem;
}

.lobby-competition-stat-row,
.lobby-competition-team-row {
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  background: #fff;
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
  border-color: rgba(15, 118, 110, 0.28);
  background: #edf8f6;
}

.lobby-competition-team-row.loser {
  background: #fff;
}

.lobby-competition-setting {
  display: grid;
  gap: 0.15rem;
  min-width: 7.2rem;
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
  color: #e5f3ff;
}

.lobby-editor-toolbar p {
  color: #8ea7c1;
}

.lobby-editor-toolbar .btn-outline-secondary {
  border-color: rgba(125, 211, 252, 0.34);
  background: rgba(15, 23, 42, 0.62);
  color: #cfe6f5;
}

.lobby-editor-toolbar .btn-outline-secondary:hover:not(:disabled) {
  border-color: rgba(45, 212, 191, 0.68);
  background: rgba(20, 184, 166, 0.18);
  color: #ffffff;
}

.lobby-editor-toolbar .btn-dark {
  border: 0;
  background: linear-gradient(135deg, #14b8a6, #2563eb);
  color: #ffffff;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
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
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(255, 255, 255, 0.92));
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
  background: #e2f7f4;
  color: #0f766e;
  font-weight: 850;
  font-size: 0.78rem;
}

.lobby-participant-column--playing .lobby-participant-column-head span {
  background: #dbeafe;
  color: #1d4ed8;
}

.lobby-participant-column--queued .lobby-participant-column-head span {
  background: #ccfbf1;
  color: #0f766e;
}

.lobby-participant-column--preparing .lobby-participant-column-head span {
  background: #fef3c7;
  color: #92400e;
}

.lobby-column-empty {
  border: 1px dashed rgba(15, 118, 110, 0.22);
  border-radius: 0.55rem;
  background:
    url("data:image/svg+xml,%3Csvg width='72' height='48' viewBox='0 0 72 48' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2314b8a6' stroke-opacity='.16'%3E%3Cpath d='M12 12h14v14H12zM46 12h14v14H46zM29 26h14v14H29z'/%3E%3C/g%3E%3C/svg%3E") right 0.4rem center / 4.5rem auto no-repeat,
    rgba(240, 253, 250, 0.46);
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
  background: #ffffff;
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
  background: #e2f7f4;
  color: #0f766e;
  font-size: 0.72rem;
  font-weight: 900;
}

.lobby-participant-column--playing .lobby-player-avatar {
  background: #dbeafe;
  color: #1d4ed8;
}

.lobby-participant-column--preparing .lobby-player-avatar {
  background: #fef3c7;
  color: #92400e;
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
  background: #f8fafc;
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
  background: #f8fafc;
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
  font-weight: 850;
}

.lobby-match-group.muted {
  background: #f8fafc;
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
  font-weight: 850;
}

.lobby-match-meta {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-match-meta strong {
  color: var(--agp-text);
}

.lobby-match-replay-badge {
  border: 1px solid rgba(245, 158, 11, 0.28);
  border-radius: 999px;
  background: #fffbeb;
  color: #b45309;
  padding: 0.12rem 0.5rem;
  font-weight: 850;
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
  background: #fff;
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

.lobby-leaderboard-player-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  min-width: 0;
}

.lobby-leaderboard-player-head strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-leaderboard-row span:not(.lobby-leaderboard-place) {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-status-badge {
  flex: none;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 999px;
  background: #f8fafc;
  color: var(--agp-text-muted);
  padding: 0.12rem 0.45rem;
  font-size: 0.7rem;
  font-weight: 850;
  line-height: 1.2;
}

.lobby-status-badge--playing {
  border-color: rgba(37, 99, 235, 0.2);
  background: #dbeafe;
  color: #1d4ed8;
}

.lobby-status-badge--queued {
  border-color: rgba(15, 118, 110, 0.2);
  background: #ccfbf1;
  color: #0f766e;
}

.lobby-status-badge--preparing {
  border-color: rgba(146, 64, 14, 0.18);
  background: #fef3c7;
  color: #92400e;
}

.lobby-remove-player {
  width: 1.75rem;
  height: 1.75rem;
  border: 1px solid rgba(248, 113, 113, 0.28);
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: #fff7f7;
  color: #b91c1c;
  font-size: 1rem;
  font-weight: 900;
  line-height: 1;
}

.lobby-remove-player:hover:not(:disabled) {
  border-color: rgba(220, 38, 38, 0.4);
  background: #fee2e2;
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
  font-weight: 850;
  font-size: 0.78rem;
}

.lobby-game-view {
  position: relative;
  min-height: 0;
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: #020617;
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
  background: rgba(2, 6, 23, 0.6);
  backdrop-filter: blur(4px);
  pointer-events: none;
}

.lobby-game-finished-card {
  display: grid;
  gap: 0.25rem;
  text-align: center;
  padding: 1rem 1.5rem;
  border-radius: 0.6rem;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(135, 226, 255, 0.3);
  color: #e9f7ff;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
}

.lobby-game-finished-card strong {
  font-size: 1.1rem;
}

.lobby-game-finished-card small {
  color: #9bb3c9;
}

.lobby-game-stats {
  min-height: 0;
  padding: 0.85rem;
  overflow: auto;
  border: 0;
  border-left: 1px solid rgba(34, 211, 238, 0.24);
  border-radius: 0;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.98)),
    url("data:image/svg+xml,%3Csvg width='104' height='104' viewBox='0 0 104 104' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23facc15' stroke-opacity='.12'%3E%3Cpath d='M16 52h72M52 16v72M28 28l48 48M76 28 28 76'/%3E%3C/g%3E%3C/svg%3E");
  color: #dbeafe;
  box-shadow: none;
}

.lobby-game-stats .text-muted {
  color: #8ea7c1 !important;
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
  color: #e5f3ff;
}

.lobby-game-stats-head span {
  color: #8ea7c1;
  font-size: 0.78rem;
}

.lobby-game-run-select {
  display: grid;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
}

.lobby-game-run-select span {
  color: #8ea7c1;
  font-size: 0.74rem;
  font-weight: 800;
}

.lobby-game-run-card {
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 8px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.05rem 0.55rem;
  align-items: center;
  background: rgba(15, 23, 42, 0.68);
  color: #dbeafe;
  padding: 0.5rem 0.6rem;
  text-align: left;
}

.lobby-game-run-card:hover,
.lobby-game-run-card.active {
  border-color: rgba(45, 212, 191, 0.55);
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.28), rgba(15, 23, 42, 0.72));
}

.lobby-game-run-card i {
  grid-row: 1 / span 2;
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: rgba(45, 212, 191, 0.16);
  color: #99f6e4;
  font-style: normal;
  font-weight: 900;
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
  color: #8ea7c1;
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
  background: rgba(15, 23, 42, 0.66);
  padding: 0.55rem 0.65rem;
}

.lobby-game-mini-stats span {
  display: block;
  color: #8ea7c1;
  font-size: 0.72rem;
}

.lobby-game-mini-stats strong {
  color: #e5f3ff;
}

.lobby-game-scoreboard {
  gap: 0.5rem;
}

.lobby-game-layout .lobby-stat-row {
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.35rem 0.65rem;
  border-color: rgba(34, 211, 238, 0.18);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.68);
  color: #dbeafe;
}

.lobby-game-layout .lobby-stat-row--self {
  border-color: rgba(45, 212, 191, 0.5);
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.28), rgba(15, 23, 42, 0.7));
}

.lobby-stat-title {
  display: grid;
  gap: 0.05rem;
  min-width: 0;
}

.lobby-stat-title strong {
  overflow: hidden;
  color: #e5f3ff;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-stat-score {
  color: #fef3c7;
  font-weight: 850;
  text-align: right;
}

.lobby-stat-bars {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.3rem;
}

.lobby-stat-bars span {
  height: 0.32rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.24);
}

.lobby-stat-bars i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.lobby-stat-bars span:first-child i {
  background: linear-gradient(90deg, #fb7185, #facc15);
}

.lobby-stat-bars span:last-child i {
  background: linear-gradient(90deg, #38bdf8, #22d3ee);
}

.lobby-game-layout .lobby-stat-row small {
  grid-column: 1 / -1;
  color: #8ea7c1;
}

.lobby-game-empty-stat {
  color: #8ea7c1;
  font-size: 0.86rem;
}

.lobby-empty {
  height: 100%;
  min-height: 24rem;
  display: grid;
  place-content: center;
  gap: 0.25rem;
  border: 1px solid rgba(34, 211, 238, 0.12);
  background:
    url("data:image/svg+xml,%3Csvg width='180' height='120' viewBox='0 0 180 120' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.14' stroke-width='2'%3E%3Cpath d='M32 24h32v32H32zM116 24h32v32h-32zM74 64h32v32H74z'/%3E%3Cpath d='M64 40h52M90 0v24M90 96v24'/%3E%3C/g%3E%3C/svg%3E") center / 16rem auto no-repeat,
    radial-gradient(circle at 50% 45%, rgba(20, 184, 166, 0.18), transparent 18rem),
    #020617;
  color: #e5f3ff;
  text-align: center;
}

.lobby-empty .text-muted {
  color: #8ea7c1 !important;
}

@media (max-width: 980px) {
  .lobby-head,
  .lobby-code-layout,
  .lobby-game-layout,
  .lobby-state-grid,
  .lobby-participant-columns {
    grid-template-columns: 1fr;
    display: grid;
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
</style>
