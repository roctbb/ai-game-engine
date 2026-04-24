<template>
  <section class="agp-grid agp-task-workspace lobby-play-page" :class="lobbyPageStatusClass">
    <header class="agp-task-header lobby-play-header">
      <div class="agp-task-header-main lobby-play-title">
        <RouterLink to="/lobbies" class="agp-back-link" title="К лобби" aria-label="К лобби">←</RouterLink>
        <div class="lobby-play-heading">
          <h1>{{ lobby?.title || 'Лобби' }}</h1>
          <div v-if="lobby" class="lobby-meta-pills">
            <span class="lobby-meta-pill lobby-meta-pill--status">{{ lobbyStatusLabel }}</span>
            <span class="lobby-meta-pill">{{ lobbyAccessLabel }}</span>
            <span class="lobby-meta-pill">{{ lobby.teams.length }}/{{ lobby.max_teams }} игроков</span>
            <span class="lobby-meta-pill">{{ readyTeamCount }} готово</span>
            <span class="lobby-meta-pill">{{ activeRunCount }} в эфире</span>
            <span class="lobby-meta-pill">связь: {{ liveModeLabel }}</span>
            <span v-if="selectedTeam" class="lobby-meta-pill lobby-meta-pill--team">
              <span class="lobby-team-avatar lobby-team-avatar--tiny">{{ teamInitials(selectedTeam.name) }}</span>
              {{ selectedTeam.name }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="lobby" class="agp-task-header-player lobby-play-switcher">
        <button class="agp-panel-toggle" :class="{ 'agp-panel-toggle--active': viewerMode === 'mine' }" @click="viewerMode = 'mine'">
          Мой эфир
        </button>
        <button class="agp-panel-toggle" :class="{ 'agp-panel-toggle--active': viewerMode === 'matches' }" @click="openMatchesPanel">
          Все матчи
        </button>
        <div class="agp-run-status lobby-play-status">
          <span class="agp-run-state-badge" :class="`agp-run-state-badge--${displayedRunTone}`"></span>
          <span class="small text-muted">Эфир</span>
          <strong>{{ displayedRun ? runStatusText(displayedRun.status) : liveEmptyTitle }}</strong>
        </div>
      </div>

      <div v-if="lobby" class="agp-task-header-actions lobby-play-actions">
        <button class="agp-icon-button agp-icon-button--ghost" :disabled="activeRunCount === 0" title="Открыть список матчей" @click="openMatchesPanel">
          ☰
        </button>
        <RouterLink v-if="displayedRun" class="agp-icon-button agp-icon-button--ghost" :to="`/runs/${displayedRun.run_id}/watch`" title="Открыть эфир отдельно">
          ⛶
        </RouterLink>
      </div>
    </header>

    <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка лобби...</article>
    <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>

    <template v-else-if="lobby">
      <div class="lobby-play-columns">
        <article class="agp-card p-3 agp-viewer-card lobby-live-viewer">
          <div class="agp-viewer-overlay agp-viewer-overlay--status">
            <span class="agp-run-state-badge" :class="`agp-run-state-badge--${displayedRunTone}`"></span>
            {{ displayedRun ? runStatusText(displayedRun.status) : liveEmptyTitle }}
          </div>
          <button
            type="button"
            class="agp-viewer-overlay agp-viewer-fullscreen"
            :disabled="activeRunCount === 0"
            title="Другие матчи"
            aria-label="Другие матчи"
            @click="openMatchesPanel"
          >
            ☰
          </button>
          <div v-if="displayedRun" class="agp-viewer-frame lobby-live-frame">
            <iframe
              :key="displayedRun.run_id"
              :src="watchFrameSrc(displayedRun.run_id)"
              title="Прямой эфир игры"
              sandbox="allow-scripts allow-same-origin"
            ></iframe>
            <div class="lobby-live-caption">
              <span class="agp-run-state-badge" :class="`agp-run-state-badge--${displayedRunTone}`"></span>
              <span class="lobby-team-avatar lobby-team-avatar--small">{{ teamInitials(teamName(displayedRun.team_id)) }}</span>
              <strong>{{ teamName(displayedRun.team_id) }}</strong>
              <span>{{ runStatusText(displayedRun.status) }}</span>
              <span class="mono">{{ shortRunId(displayedRun.run_id) }}</span>
            </div>
          </div>
          <div v-else class="lobby-empty-live">
            <div class="lobby-empty-icon">▶</div>
            <h2>{{ liveEmptyTitle }}</h2>
            <p>{{ liveEmptyText }}</p>
            <div class="lobby-empty-checklist" aria-label="Что нужно для запуска эфира">
              <span :class="{ 'lobby-empty-checklist--done': Boolean(selectedTeamId) }">вы вошли</span>
              <span :class="{ 'lobby-empty-checklist--done': Boolean(editorCode.trim() && !isDirty) }">код сохранен</span>
              <span :class="{ 'lobby-empty-checklist--done': isSelectedTeamReady }">готовность включена</span>
            </div>
            <div class="d-flex flex-wrap gap-2 justify-content-center">
              <button class="btn btn-dark" :disabled="!canRunPrimaryTeamAction" @click="runPrimaryTeamAction">
                {{ primaryTeamActionLabel }}
              </button>
              <button class="btn btn-outline-light" :disabled="activeRunCount === 0" @click="openMatchesPanel">
                Смотреть другие матчи
              </button>
            </div>
          </div>
        </article>

        <aside class="agp-card p-0 agp-code-panel lobby-side-panel">
          <div class="lobby-side-scroll">
            <section class="lobby-side-section lobby-team-strip">
              <div class="lobby-room-strip" aria-label="Состояние лобби">
                <div>
                  <span>статус</span>
                  <strong>{{ lobbyStatusLabel }}</strong>
                </div>
                <div>
                  <span>готовы</span>
                  <strong>{{ readyTeamCount }}/{{ lobby.teams.length }}</strong>
                </div>
                <div>
                  <span>эфир</span>
                  <strong>{{ activeRunCount }}</strong>
                </div>
              </div>

              <div v-if="displayedRun" class="lobby-now-card" :class="`lobby-now-card--${displayedRunTone}`">
                <span class="lobby-team-avatar lobby-team-avatar--small">{{ teamInitials(teamName(displayedRun.team_id)) }}</span>
                <div>
                  <span>сейчас в эфире</span>
                  <strong>{{ teamName(displayedRun.team_id) }}</strong>
                  <small>{{ runStatusText(displayedRun.status) }} · {{ shortRunId(displayedRun.run_id) }}</small>
                </div>
                <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/runs/${displayedRun.run_id}/watch`">
                  ⛶
                </RouterLink>
              </div>

              <div class="lobby-side-title-row">
                <div>
                  <h2>Участие</h2>
                  <p>{{ nextTeamActionHint }}</p>
                </div>
                <span class="agp-pill" :class="isSelectedTeamReady ? 'agp-pill--primary' : 'agp-pill--warning'">
                  {{ selectedTeamLobbyState ? (isSelectedTeamReady ? 'готов' : 'не готов') : 'входим...' }}
                </span>
              </div>

              <div class="lobby-flow-steps" aria-label="Прогресс подготовки">
                <span :class="{ 'lobby-flow-step--done': Boolean(selectedTeamId) }">1. вход</span>
                <span :class="{ 'lobby-flow-step--done': Boolean(selectedTeamId && !isDirty && editorCode.trim()) }">2. код</span>
                <span :class="{ 'lobby-flow-step--done': isSelectedTeamReady }">3. готовность</span>
              </div>
              <div class="lobby-flow-meter" aria-hidden="true">
                <span :style="{ width: `${teamPreparationPercent}%` }"></span>
              </div>

              <div
                v-if="selectedTeam"
                class="lobby-selected-team-card"
                :class="{
                  'lobby-selected-team-card--joined': Boolean(selectedTeamLobbyState),
                  'lobby-selected-team-card--ready': isSelectedTeamReady,
                }"
              >
                <div class="lobby-team-identity">
                  <span class="lobby-team-avatar">{{ teamInitials(selectedTeam.name) }}</span>
                  <div>
                    <span>вы в лобби как</span>
                    <strong>{{ selectedTeam.name }}</strong>
                  </div>
                </div>
              </div>
              <div v-else class="lobby-empty-code">
                {{ isCreatingTeam ? 'Создаем участника и входим в лобби...' : 'Готовим вход в лобби...' }}
              </div>
              <div v-if="selectedTeam" class="lobby-my-run-strip" aria-label="Матчи выбранной команды">
                <div>
                  <span>мои матчи</span>
                  <strong>{{ selectedTeamRuns.length }}</strong>
                </div>
                <div>
                  <span>активные</span>
                  <strong>{{ selectedTeamActiveRuns.length }}</strong>
                </div>
                <div>
                  <span>завершены</span>
                  <strong>{{ selectedTeamFinishedRuns.length }}</strong>
                </div>
              </div>

              <div class="lobby-quick-actions">
                <button class="btn btn-sm btn-dark lobby-primary-action" :disabled="!canRunPrimaryTeamAction" @click="runPrimaryTeamAction">
                  {{ primaryTeamActionLabel }}
                </button>
              </div>
            </section>

            <section class="lobby-side-section">
              <div class="lobby-side-title-row">
                <div>
                  <h2>Игроки</h2>
                  <p>{{ lobby.teams.length === 0 ? 'Пока никого нет.' : 'Кто уже вошел и готов играть.' }}</p>
                </div>
                <strong class="lobby-section-count">{{ readyTeamCount }}/{{ lobby.teams.length }}</strong>
              </div>
              <div v-if="lobby.teams.length === 0" class="small text-muted">Пока никто не вошел.</div>
              <div v-else class="lobby-team-list">
                <div v-for="team in lobby.teams" :key="team.team_id" class="lobby-team-row" :class="teamStateClass(team)">
                  <div class="lobby-row-identity">
                    <span class="lobby-team-avatar lobby-team-avatar--small">{{ teamInitials(teamName(team.team_id)) }}</span>
                    <div>
                      <div class="fw-semibold">{{ teamName(team.team_id) }}</div>
                      <div class="small text-muted">{{ team.blocker_reason || teamStateDescription(team) }}</div>
                    </div>
                  </div>
                  <span class="agp-pill" :class="team.ready ? 'agp-pill--primary' : team.blocker_reason ? 'agp-pill--danger' : 'agp-pill--warning'">
                    {{ teamStateLabel(team) }}
                  </span>
                </div>
              </div>
            </section>

            <section class="lobby-side-section lobby-code-section">
              <div class="lobby-side-title-row lobby-code-title-row">
                <div>
                  <h2>Код бота</h2>
                  <p>{{ canEditSelectedTeamCode ? 'Заполните код и нажмите “Готов”. Матч стартует сам, когда игроков достаточно.' : codeReadonlyHint }}</p>
                </div>
                <div class="lobby-code-badges">
                  <span class="agp-pill agp-pill--neutral">{{ slotStates.length || 0 }} ролей</span>
                  <span class="agp-pill" :class="isDirty ? 'agp-pill--warning' : 'agp-pill--neutral'">
                    {{ isDirty ? 'изменен' : 'сохранен' }}
                  </span>
                </div>
              </div>

              <div v-if="workspaceError" class="small text-danger mb-2">{{ workspaceError }}</div>
              <div v-else-if="selectedTeamId && !canEditSelectedTeamCode" class="lobby-readonly-note">
                {{ codeReadonlyHint }}
              </div>
              <div v-if="!selectedTeamId" class="lobby-empty-code">Создаем участника и открываем редактор.</div>
              <template v-else>
                <div v-if="slotStates.length > 1" class="lobby-role-tabs" role="tablist" aria-label="Роли команды">
                  <button
                    v-for="slot in slotStates"
                    :key="slot.slot_key"
                    type="button"
                    class="lobby-role-tab"
                    :class="[
                      slotStateClass(slot),
                      { 'lobby-role-tab--active': selectedSlotKey === slot.slot_key },
                    ]"
                    @click="selectSlot(slot.slot_key)"
                  >
                    <span class="lobby-role-name">
                      {{ slot.slot_key }}
                      <small v-if="slot.required">обяз.</small>
                    </span>
                    <span class="lobby-role-state">{{ slotStateLabel(slot.state) }}</span>
                  </button>
                </div>

                <div v-if="selectedSlot" class="lobby-role-summary">
                  <div>
                    <span>текущая роль</span>
                    <strong class="mono">{{ selectedSlot.slot_key }}</strong>
                  </div>
                  <div>
                    <span>статус</span>
                    <strong>{{ slotStateLabel(selectedSlot.state) }}</strong>
                  </div>
                  <div>
                    <span>тип</span>
                    <strong>{{ selectedSlot.required ? 'обязательная' : 'доп.' }}</strong>
                  </div>
                </div>

                <div class="lobby-code-toolbar">
                  <div class="lobby-code-toolbar-title">
                    <span class="lobby-save-state-dot" :class="codeStateDotClass"></span>
                    <span class="small text-muted">роль</span>
                    <strong class="mono">{{ selectedSlotKey || '—' }}</strong>
                  </div>
                  <div class="lobby-code-toolbar-actions">
                    <button class="btn btn-sm btn-outline-secondary" :disabled="!selectedSlotTemplateCode || !canEditSelectedTeamCode" @click="applyTemplateToSelectedSlot">Шаблон</button>
                    <button class="btn btn-sm btn-outline-secondary" :disabled="!selectedSlotDemoCode || !canEditSelectedTeamCode" @click="applyDemoToSelectedSlot">Демо</button>
                    <button class="btn btn-sm btn-dark lobby-save-button" :class="{ 'lobby-save-button--dirty': isDirty }" :disabled="!canSaveSelectedCode" @click="saveSelectedSlotCode">
                      {{ saveButtonLabel }}
                    </button>
                  </div>
                </div>
                <div class="lobby-code-hint" :class="codeStateHintClass">
                  {{ codeStateHint }}
                </div>

                <CodeEditor v-model="editorCode" :readonly="!selectedSlotKey || isSavingCode || !canEditSelectedTeamCode" language="python" />
              </template>
            </section>

            <details class="lobby-side-section lobby-compact-details">
              <summary class="agp-details-summary lobby-details-summary">
                <span>Статистика</span>
                <strong>{{ lobbyRuns.length }} матчей</strong>
              </summary>
              <div class="lobby-stat-grid mt-2">
                <div class="lobby-stat"><span>готовы</span><strong>{{ readyTeamCount }}</strong></div>
                <div class="lobby-stat"><span>ждут</span><strong>{{ waitingTeamCount }}</strong></div>
                <div class="lobby-stat"><span>ошибки</span><strong>{{ blockedTeamCount }}</strong></div>
                <div class="lobby-stat"><span>матчи</span><strong>{{ lobbyRuns.length }}</strong></div>
              </div>
            </details>

            <details v-if="canManageLobbyLifecycle" class="lobby-side-section lobby-compact-details">
              <summary class="agp-details-summary lobby-details-summary">
                <span>Инструменты учителя</span>
                <strong>{{ lobbyStatusLabel }}</strong>
              </summary>
              <div class="lobby-teacher-grid mt-2">
                <button class="btn btn-sm btn-outline-warning" :disabled="!canPauseLobby" @click="pauseLobby">Пауза</button>
                <button class="btn btn-sm btn-outline-primary" :disabled="!canResumeLobby" @click="resumeLobby">Продолжить</button>
                <button class="btn btn-sm btn-outline-danger" :disabled="!canCloseLobby" @click="closeLobby">Закрыть</button>
                <button class="btn btn-sm btn-outline-dark" :disabled="!canCreateCompetitionFromLobby || isCreatingCompetition" @click="createCompetitionFromLobby">
                  {{ isCreatingCompetition ? '...' : 'Турнир' }}
                </button>
                <button class="btn btn-sm btn-outline-success" :disabled="!canRunMatchmakingTick" @click="runMatchmakingTick">
                  {{ isTickingMatchmaking ? '...' : 'Матчмейкинг' }}
                </button>
                <button class="btn btn-sm btn-outline-primary" :disabled="!canLaunchTrainingRun" @click="launchTrainingRun">
                  {{ isLaunchingRun ? '...' : 'Запуск' }}
                </button>
                <button class="btn btn-sm btn-outline-danger" :disabled="!canCancelRun" @click="cancelTrainingRun">
                  {{ isCancellingRun ? '...' : 'Остановить' }}
                </button>
              </div>
            </details>
          </div>
        </aside>
      </div>

      <button
        v-if="matchesPanelOpen"
        type="button"
        class="lobby-drawer-backdrop"
        aria-label="Закрыть список матчей"
        @click="matchesPanelOpen = false"
      ></button>
      <aside v-if="matchesPanelOpen" class="lobby-matches-drawer" aria-label="Матчи лобби">
        <header class="lobby-drawer-header">
          <div>
            <h2 class="h5 mb-1">Матчи лобби</h2>
            <div class="small text-muted">Активные и последние запуски. Можно открыть матч слева или отдельно.</div>
          </div>
          <div class="lobby-drawer-counters" aria-label="Сводка матчей">
            <span>{{ activeRunCount }} активных</span>
            <span>{{ orderedLobbyRuns.length }} всего</span>
          </div>
          <button class="btn btn-sm btn-outline-secondary" @click="matchesPanelOpen = false">Закрыть</button>
        </header>

        <div v-if="orderedLobbyRuns.length === 0" class="small text-muted">Игр в этом лобби пока не было.</div>
        <div v-else class="lobby-match-list">
          <article
            v-for="run in orderedLobbyRuns"
            :key="run.run_id"
            class="lobby-match-row"
            :class="[runStatusClass(run.status), { 'lobby-match-row--selected': displayedRun?.run_id === run.run_id }]"
          >
            <div class="lobby-row-identity">
              <span class="lobby-team-avatar lobby-team-avatar--small">{{ teamInitials(teamName(run.team_id)) }}</span>
              <div>
              <div class="fw-semibold">{{ teamName(run.team_id) }}</div>
              <div class="lobby-match-status-line">
                <span class="agp-run-state-badge" :class="`agp-run-state-badge--${runStatusTone(run.status)}`"></span>
                <span>{{ runStatusText(run.status) }}</span>
                <span class="mono">{{ shortRunId(run.run_id) }}</span>
                <RunReasonBadge v-if="run.error_message" :reason="run.error_message" />
              </div>
              </div>
            </div>
            <div class="d-flex gap-2 flex-wrap justify-content-end">
              <button
                class="btn btn-sm"
                :class="displayedRun?.run_id === run.run_id ? 'btn-dark' : 'btn-outline-dark'"
                :disabled="displayedRun?.run_id === run.run_id"
                @click="showRunInViewer(run.run_id)"
              >
                {{ displayedRun?.run_id === run.run_id ? 'В эфире' : 'Показать' }}
              </button>
              <button class="btn btn-sm btn-outline-secondary" @click="inspectRunReplay(run.run_id)">Повтор</button>
              <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/runs/${run.run_id}/watch`">Отдельно</RouterLink>
            </div>
          </article>
        </div>

        <article v-if="inspectedRunId" class="agp-card p-3 mt-3">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h3 class="h6 mb-0">Данные повтора</h3>
            <span class="mono small">{{ shortRunId(inspectedRunId) }}</span>
          </div>
          <div v-if="isInspectReplayLoading" class="text-muted small">Загрузка повтора...</div>
          <div v-else-if="inspectReplayError" class="text-danger small">{{ inspectReplayError }}</div>
          <div v-else-if="inspectedReplay">
            <div class="small text-muted mb-2">кадров: <span class="mono">{{ inspectedReplay.frames.length }}</span></div>
            <pre class="mono small mb-0">{{ inspectedReplaySummary }}</pre>
          </div>
          <div v-else class="text-muted small">Для выбранной игры повтор пока недоступен.</div>
        </article>
      </aside>
    </template>
  </section>
</template>


<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import CodeEditor from '../components/CodeEditor.vue';
import RunReasonBadge from '../components/RunReasonBadge.vue';
import {
  cancelRun,
  createCompetition,
  createLobby,
  createRun,
  createTeam,
  getGameTemplates,
  getLobby,
  getRun,
  getRunReplay,
  getWorkspace,
  joinLobby,
  leaveLobby,
  listGames,
  listLobbies,
  listRuns,
  listTeamsByGame,
  queueRun,
  registerCompetitionTeam,
  runLobbyMatchmakingTick,
  setLobbyReady,
  setLobbyStatus,
  updateSlotCode,
  type GameTemplatesDto,
  type LobbyDto,
  type LobbyTeamStateDto,
  type ReplayDto,
  type RunDto,
  type SlotStateDto,
  type StreamEnvelopeDto,
  type TeamDto,
  type TeamWorkspaceDto,
} from '../lib/api';
import { loadTeamMapping, saveTeamMapping } from '../lib/teamMapping';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();

const lobby = ref<LobbyDto | null>(null);
const teamsByGame = ref<TeamDto[]>([]);
const selectedTeamId = ref('');
const workspace = ref<TeamWorkspaceDto | null>(null);
const templates = ref<GameTemplatesDto | null>(null);
const selectedSlotKey = ref('');
const editorCode = ref('');
const savedCode = ref('');
const currentRun = ref<RunDto | null>(null);
const lobbyRuns = ref<RunDto[]>([]);
const inspectedRunId = ref('');
const inspectedReplay = ref<ReplayDto | null>(null);
const inspectReplayError = ref('');
const isInspectReplayLoading = ref(false);
const viewerMode = ref<'mine' | 'matches'>('mine');
const focusedRunId = ref('');
const matchesPanelOpen = ref(false);

const isLoading = ref(false);
const isCreatingTeam = ref(false);
const isCreatingCompetition = ref(false);
const isSavingCode = ref(false);
const isTickingMatchmaking = ref(false);
const isLaunchingRun = ref(false);
const isCancellingRun = ref(false);
const errorMessage = ref('');
const workspaceError = ref('');
const lobbyLiveMode = ref<'idle' | 'sse' | 'polling'>('idle');
let runPollingHandle: ReturnType<typeof setInterval> | null = null;
let lobbyPollingHandle: ReturnType<typeof setInterval> | null = null;
let lobbyEventSource: EventSource | null = null;

const selectedTeamLobbyState = computed(() => {
  if (!lobby.value || !selectedTeamId.value) return null;
  return lobby.value.teams.find((item) => item.team_id === selectedTeamId.value) ?? null;
});

const selectedTeam = computed(() => teamsByGame.value.find((team) => team.team_id === selectedTeamId.value) ?? null);
const lobbyPageStatusClass = computed(() => {
  const status = lobby.value?.status;
  return {
    'lobby-play-page--running': status === 'running',
    'lobby-play-page--paused': status === 'paused',
    'lobby-play-page--closed': status === 'closed',
    'lobby-play-page--updating': status === 'updating',
  };
});
const slotStates = computed<SlotStateDto[]>(() => workspace.value?.slot_states ?? []);
const selectedSlot = computed(() => slotStates.value.find((slot) => slot.slot_key === selectedSlotKey.value) ?? null);
const isSelectedTeamReady = computed(() => Boolean(selectedTeamLobbyState.value?.ready));
const canEditSelectedTeamCode = computed(
  () => Boolean(selectedTeam.value) && (selectedTeam.value!.captain_user_id === sessionStore.nickname || canManageLobbyLifecycle.value)
);
const codeReadonlyHint = computed(() => {
  if (!selectedTeam.value) return 'Выберите команду, чтобы открыть редактор.';
  return `Код редактирует капитан ${selectedTeam.value.captain_user_id} или учитель.`;
});
const codeStateHint = computed(() => {
  if (!selectedTeamId.value) return 'После выбора команды здесь появится код ролей.';
  if (!selectedSlotKey.value) return 'Выберите роль, чтобы открыть код.';
  if (!canEditSelectedTeamCode.value) return codeReadonlyHint.value;
  if (isDirty.value) return 'Есть несохраненные изменения. Перед готовностью они будут сохранены автоматически.';
  if (!editorCode.value.trim()) return 'Код роли пустой. Можно вставить шаблон или демо-стратегию.';
  return activeSelectedRun.value
    ? 'Код сохранен. Текущий матч продолжает старый snapshot, изменения пойдут в следующий запуск.'
    : 'Код сохранен и готов для следующего запуска.';
});
const codeStateHintClass = computed(() => ({
  'lobby-code-hint--success': Boolean(selectedTeamId.value && selectedSlotKey.value && editorCode.value.trim() && !isDirty.value && canEditSelectedTeamCode.value),
  'lobby-code-hint--warning': isDirty.value,
  'lobby-code-hint--readonly': Boolean(selectedTeamId.value && !canEditSelectedTeamCode.value),
}));
const codeStateDotClass = computed(() => ({
  'lobby-save-state-dot--success': Boolean(selectedTeamId.value && selectedSlotKey.value && editorCode.value.trim() && !isDirty.value && canEditSelectedTeamCode.value),
  'lobby-save-state-dot--warning': isDirty.value,
  'lobby-save-state-dot--muted': !selectedTeamId.value || !selectedSlotKey.value || !editorCode.value.trim(),
  'lobby-save-state-dot--readonly': Boolean(selectedTeamId.value && !canEditSelectedTeamCode.value),
}));
const saveButtonLabel = computed(() => {
  if (isSavingCode.value) return 'Сохраняю...';
  if (isDirty.value) return 'Сохранить изменения';
  return 'Сохранено';
});
const primaryTeamActionLabel = computed(() => {
  if (!selectedTeamId.value) return 'Входим...';
  if (!selectedTeamLobbyState.value) return 'Подключиться';
  return isSelectedTeamReady.value ? 'Снять готовность' : 'Стать готовым';
});
const nextTeamActionHint = computed(() => {
  if (!selectedTeamId.value) return 'автоматически создаем вашего участника';
  if (!selectedTeamLobbyState.value) return 'автоматически подключаем вас к лобби';
  if (!editorCode.value.trim()) return 'добавьте код, затем подтвердите готовность';
  if (isDirty.value) return 'сохраните код перед готовностью';
  return isSelectedTeamReady.value ? 'вы готовы к подбору игры' : 'код сохранен, можно становиться готовым';
});
const teamPreparationPercent = computed(() => {
  if (isSelectedTeamReady.value) return 100;
  if (selectedTeamId.value && !isDirty.value && editorCode.value.trim()) return 66;
  if (selectedTeamId.value) return 33;
  return 0;
});
const canJoin = computed(
  () => Boolean(lobby.value && selectedTeamId.value) && !selectedTeamLobbyState.value && ['open', 'draft'].includes(lobby.value!.status)
);
const canToggleReady = computed(
  () => Boolean(lobby.value && selectedTeamId.value && selectedTeamLobbyState.value) && ['open', 'draft'].includes(lobby.value!.status)
);
const canBecomeReady = computed(() => Boolean(editorCode.value.trim() && !isDirty.value));
const canRunPrimaryTeamAction = computed(
  () => canJoin.value || (canToggleReady.value && (isSelectedTeamReady.value || canBecomeReady.value))
);
const canLeave = computed(
  () => Boolean(lobby.value && selectedTeamId.value && selectedTeamLobbyState.value) && lobby.value!.status !== 'closed'
);
const canManageLobbyLifecycle = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const canPauseLobby = computed(
  () => Boolean(lobby.value) && canManageLobbyLifecycle.value && ['open', 'running'].includes(lobby.value!.status)
);
const canResumeLobby = computed(
  () => Boolean(lobby.value) && canManageLobbyLifecycle.value && lobby.value!.status === 'paused'
);
const canCloseLobby = computed(
  () => Boolean(lobby.value) && canManageLobbyLifecycle.value && !['closed', 'updating'].includes(lobby.value!.status)
);
const canRunMatchmakingTick = computed(
  () => Boolean(lobby.value) && ['open', 'running'].includes(lobby.value!.status) && !isTickingMatchmaking.value
);
const canCreateCompetitionFromLobby = computed(
  () => Boolean(lobby.value) && canManageLobbyLifecycle.value && lobby.value!.teams.length >= 2
);
const canLaunchTrainingRun = computed(() => Boolean(lobby.value && selectedTeamId.value) && !activeSelectedRun.value);
const canCancelRun = computed(() => Boolean(activeSelectedRun.value) && !isCancellingRun.value);
const inspectedReplaySummary = computed(() => JSON.stringify(inspectedReplay.value?.summary ?? {}, null, 2));
const lobbyStatusLabel = computed(() => {
  if (!lobby.value) return '';
  const labels: Record<LobbyDto['status'], string> = {
    draft: 'готовится',
    open: 'открыто',
    running: 'игра идет',
    paused: 'пауза',
    updating: 'обновляется',
    closed: 'закрыто',
  };
  return labels[lobby.value.status];
});
const selectedSlotTemplateCode = computed(
  () => templates.value?.templates.find((item) => item.slot_key === selectedSlotKey.value)?.code ?? ''
);
const selectedSlotDemoCode = computed(
  () => templates.value?.demo_strategies.find((item) => item.slot_key === selectedSlotKey.value)?.code ?? ''
);
const isDirty = computed(() => editorCode.value !== savedCode.value);
const canSaveSelectedCode = computed(
  () =>
    Boolean(selectedTeamId.value && selectedSlotKey.value && editorCode.value.trim() && isDirty.value && canEditSelectedTeamCode.value) &&
    !isSavingCode.value
);
const readyTeamCount = computed(() => lobby.value?.teams.filter((team) => team.ready).length ?? 0);
const blockedTeamCount = computed(() => lobby.value?.teams.filter((team) => Boolean(team.blocker_reason)).length ?? 0);
const waitingTeamCount = computed(() =>
  Math.max(0, (lobby.value?.teams.length ?? 0) - readyTeamCount.value - blockedTeamCount.value)
);
const orderedLobbyRuns = computed(() =>
  [...lobbyRuns.value].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
);
const activeLobbyRuns = computed(() => orderedLobbyRuns.value.filter((run) => isActiveRunStatus(run.status)));
const activeRunCount = computed(() => activeLobbyRuns.value.length);
const selectedTeamRuns = computed(() => orderedLobbyRuns.value.filter((run) => run.team_id === selectedTeamId.value));
const selectedTeamActiveRuns = computed(() => selectedTeamRuns.value.filter((run) => isActiveRunStatus(run.status)));
const selectedTeamFinishedRuns = computed(() => selectedTeamRuns.value.filter((run) => run.status === 'finished'));
const latestSelectedTeamRun = computed(() => selectedTeamRuns.value[0] ?? null);
const activeSelectedRun = computed(() => {
  const fromList = selectedTeamActiveRuns.value[0] ?? null;
  if (fromList) return fromList;
  if (currentRun.value && currentRun.value.team_id === selectedTeamId.value && isActiveRunStatus(currentRun.value.status)) {
    return currentRun.value;
  }
  return null;
});
const focusedRun = computed(() => orderedLobbyRuns.value.find((run) => run.run_id === focusedRunId.value) ?? null);
const displayedRun = computed(() => {
  if (viewerMode.value === 'mine') return activeSelectedRun.value;
  return focusedRun.value ?? activeLobbyRuns.value[0] ?? orderedLobbyRuns.value[0] ?? null;
});
const displayedRunTone = computed<'idle' | 'active' | 'success' | 'danger'>(() => {
  return runStatusTone(displayedRun.value?.status);
});
const lobbyAccessLabel = computed(() => {
  if (!lobby.value) return '';
  return lobby.value.access === 'code' ? 'вход по коду' : 'открытое лобби';
});
const liveModeLabel = computed(() => {
  if (lobbyLiveMode.value === 'sse') return 'онлайн';
  if (lobbyLiveMode.value === 'polling') return 'опрос';
  return 'ожидание';
});
const shortVersionId = computed(() => {
  const versionId = lobby.value?.game_version_id ?? '';
  return versionId.length > 14 ? `${versionId.slice(0, 8)}...${versionId.slice(-4)}` : versionId;
});
const liveEmptyTitle = computed(() => {
  if (!selectedTeamId.value) return 'Входим в лобби';
  if (!selectedTeamLobbyState.value) return 'Подключаем участника';
  if (!isSelectedTeamReady.value) return 'Вы еще не готовы';
  return 'Ваш матч еще не запущен';
});
const liveEmptyText = computed(() => {
  if (!selectedTeamId.value) return 'Система сама создаст участника для вашего аккаунта.';
  if (!selectedTeamLobbyState.value) return 'Подключаем вашего участника, чтобы он попал в подбор игры.';
  if (!isSelectedTeamReady.value) return 'Нажмите “Готов”, когда код сохранен. Игра стартует автоматически, когда игроков достаточно.';
  return activeRunCount.value > 0
    ? 'В лобби уже идут другие матчи. Их можно открыть через панель “Все матчи”.'
    : 'Ожидаем соперников или запуска матчмейкинга.';
});

function teamName(teamId: string): string {
  const found = teamsByGame.value.find((item) => item.team_id === teamId);
  return found?.name ?? teamId;
}

function teamInitials(name: string): string {
  const parts = name
    .replace(/[_/-]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean);
  const first = parts[0]?.[0] ?? '?';
  const second = parts.length > 1 ? parts[1]?.[0] : parts[0]?.[1];
  return `${first}${second ?? ''}`.toUpperCase();
}

function isActiveRunStatus(status: RunDto['status']): boolean {
  return status === 'created' || status === 'queued' || status === 'running';
}

function runStatusText(status: RunDto['status']): string {
  const labels: Record<RunDto['status'], string> = {
    created: 'создано',
    queued: 'в очереди',
    running: 'игра идет',
    finished: 'готово',
    failed: 'ошибка',
    timeout: 'слишком долго',
    canceled: 'остановлено',
  };
  return labels[status];
}

function slotStateLabel(state: SlotStateDto['state']): string {
  const labels: Record<SlotStateDto['state'], string> = {
    filled: 'заполнен',
    empty: 'пустой',
    dirty: 'изменен',
    locked: 'закрыт',
    incompatible: 'лишний',
  };
  return labels[state];
}

function slotStateClass(slot: SlotStateDto): Record<string, boolean> {
  return {
    'lobby-role-tab--filled': slot.state === 'filled',
    'lobby-role-tab--empty': slot.state === 'empty',
    'lobby-role-tab--dirty': slot.state === 'dirty',
    'lobby-role-tab--locked': slot.state === 'locked',
    'lobby-role-tab--incompatible': slot.state === 'incompatible',
  };
}

function teamStateLabel(team: LobbyTeamStateDto): string {
  if (team.blocker_reason) return 'ошибка';
  if (team.ready) return 'готова';
  return 'не готова';
}

function teamStateDescription(team: LobbyTeamStateDto): string {
  if (team.ready) return 'Команда готова к подбору матча.';
  return 'Команда в лобби, но еще не подтвердила готовность.';
}

function teamStateClass(team: LobbyTeamStateDto): Record<string, boolean> {
  return {
    'lobby-team-row--current': team.team_id === selectedTeamId.value,
    'lobby-team-row--ready': team.ready,
    'lobby-team-row--blocked': Boolean(team.blocker_reason),
  };
}

function shortRunId(runId: string): string {
  return runId.length > 18 ? `${runId.slice(0, 10)}...${runId.slice(-6)}` : runId;
}

function runStatusTone(status?: RunDto['status']): 'idle' | 'active' | 'success' | 'danger' {
  if (!status || status === 'created') return 'idle';
  if (status === 'queued' || status === 'running') return 'active';
  if (status === 'finished') return 'success';
  return 'danger';
}

function runStatusClass(status: RunDto['status']): Record<string, boolean> {
  return {
    'lobby-match-row--active': status === 'created' || status === 'queued' || status === 'running',
    'lobby-match-row--finished': status === 'finished',
    'lobby-match-row--failed': status === 'failed' || status === 'timeout' || status === 'canceled',
  };
}

function watchFrameSrc(runId: string): string {
  return `/runs/${encodeURIComponent(runId)}/watch?embed=1`;
}

function openMatchesPanel(): void {
  viewerMode.value = 'matches';
  matchesPanelOpen.value = true;
}

function showRunInViewer(runId: string): void {
  focusedRunId.value = runId;
  viewerMode.value = 'matches';
  matchesPanelOpen.value = false;
}

async function runPrimaryTeamAction(): Promise<void> {
  if (canJoin.value) {
    await joinSelectedTeam();
    return;
  }
  if (canToggleReady.value) {
    await toggleReadySelectedTeam();
  }
}

function selectSlot(slotKey: string): void {
  selectedSlotKey.value = slotKey;
  const slot = slotStates.value.find((item) => item.slot_key === slotKey);
  editorCode.value = slot?.code ?? '';
  savedCode.value = slot?.code ?? '';
}

function persistSelectedTeamForGame(gameId: string, teamId: string): void {
  saveTeamMapping(gameId, sessionStore.nickname, teamId);
}

function syncSelectedTeamFromStorage(): void {
  if (!lobby.value) return;
  const mapped = loadTeamMapping(lobby.value.game_id, sessionStore.nickname);
  if (mapped && teamsByGame.value.some((team) => team.team_id === mapped && team.captain_user_id === sessionStore.nickname)) {
    selectedTeamId.value = mapped;
    return;
  }
  const ownTeam = teamsByGame.value.find((team) => team.captain_user_id === sessionStore.nickname);
  if (ownTeam) {
    selectedTeamId.value = ownTeam.team_id;
    persistSelectedTeamForGame(lobby.value.game_id, ownTeam.team_id);
    return;
  }
  selectedTeamId.value = '';
}

async function ensureOwnTeamInLobby(): Promise<void> {
  if (!lobby.value) return;
  isCreatingTeam.value = true;
  errorMessage.value = '';
  try {
    let ownTeam = teamsByGame.value.find((team) => team.captain_user_id === sessionStore.nickname) ?? null;
    if (!ownTeam) {
      ownTeam = await createTeam({
        game_id: lobby.value.game_id,
        name: sessionStore.nickname,
        captain_user_id: sessionStore.nickname,
      });
      teamsByGame.value = await listTeamsByGame(lobby.value.game_id);
    }

    selectedTeamId.value = ownTeam.team_id;
    persistSelectedTeamForGame(lobby.value.game_id, ownTeam.team_id);

    const isAlreadyInside = lobby.value.teams.some((team) => team.team_id === ownTeam!.team_id);
    if (!isAlreadyInside && ['open', 'draft'].includes(lobby.value.status)) {
      lobby.value = await joinLobby({
        lobby_id: lobby.value.lobby_id,
        team_id: ownTeam.team_id,
      });
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось войти в лобби';
  } finally {
    isCreatingTeam.value = false;
  }
}

function syncEditorFromWorkspace(payload: TeamWorkspaceDto): void {
  selectedSlotKey.value = payload.slot_states[0]?.slot_key ?? '';
  const slot = payload.slot_states.find((item) => item.slot_key === selectedSlotKey.value);
  const initialCode = slot?.code ?? selectedSlotTemplateCode.value ?? selectedSlotDemoCode.value ?? '';
  editorCode.value = initialCode;
  savedCode.value = slot?.code ?? '';
}

async function ensureTemplatesLoaded(): Promise<void> {
  if (!lobby.value) return;
  if (templates.value?.game_id === lobby.value.game_id) return;
  templates.value = await getGameTemplates(lobby.value.game_id);
}

async function loadSelectedTeamWorkspace(): Promise<void> {
  workspace.value = null;
  selectedSlotKey.value = '';
  editorCode.value = '';
  savedCode.value = '';
  workspaceError.value = '';
  if (!selectedTeamId.value || !lobby.value) return;

  try {
    await ensureTemplatesLoaded();
    workspace.value = await getWorkspace(selectedTeamId.value);
    syncEditorFromWorkspace(workspace.value);
  } catch (error) {
    workspaceError.value = error instanceof Error ? error.message : 'Не удалось загрузить код команды';
  }
}

function applyTemplateToSelectedSlot(): void {
  if (!selectedSlotTemplateCode.value) return;
  editorCode.value = selectedSlotTemplateCode.value;
}

function applyDemoToSelectedSlot(): void {
  if (!selectedSlotDemoCode.value) return;
  editorCode.value = selectedSlotDemoCode.value;
}

async function saveSelectedSlotCode(): Promise<void> {
  if (!selectedTeamId.value || !selectedSlotKey.value || !editorCode.value.trim()) return;
  isSavingCode.value = true;
  workspaceError.value = '';
  try {
    await updateSlotCode({
      team_id: selectedTeamId.value,
      slot_key: selectedSlotKey.value,
      actor_user_id: sessionStore.nickname,
      code: editorCode.value,
    });
    savedCode.value = editorCode.value;
    workspace.value = await getWorkspace(selectedTeamId.value);
  } catch (error) {
    workspaceError.value = error instanceof Error ? error.message : 'Не удалось сохранить код';
  } finally {
    isSavingCode.value = false;
  }
}

async function saveCodeIfDirty(): Promise<void> {
  if (editorCode.value && editorCode.value !== savedCode.value) {
    await saveSelectedSlotCode();
  }
}

async function refreshLobbyRuns(): Promise<void> {
  if (!lobby.value) return;
  lobbyRuns.value = await listRuns({ lobby_id: lobby.value.lobby_id });
}

async function inspectRunReplay(runId: string): Promise<void> {
  inspectedRunId.value = runId;
  inspectedReplay.value = null;
  inspectReplayError.value = '';
  isInspectReplayLoading.value = true;
  try {
    inspectedReplay.value = await getRunReplay(runId);
  } catch (error) {
    inspectReplayError.value = error instanceof Error ? error.message : 'Replay недоступен';
  } finally {
    isInspectReplayLoading.value = false;
  }
}

async function ensureLobbyLoaded(): Promise<void> {
  const lobbyIdFromRoute = String(route.params.lobbyId || '').trim();
  if (!lobbyIdFromRoute) {
    errorMessage.value = 'Не передан lobbyId';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await getLobby(lobbyIdFromRoute);
  } catch (error) {
    const isDemoRoute = lobbyIdFromRoute === 'demo-lobby';
    if (!isDemoRoute) {
      errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить лобби';
      isLoading.value = false;
      return;
    }
    lobby.value = await bootstrapDemoLobby();
  }

  if (lobby.value) {
    await ensureTemplatesLoaded();
    teamsByGame.value = await listTeamsByGame(lobby.value.game_id);
    await ensureOwnTeamInLobby();
    await refreshLobbyRuns();
    syncSelectedTeamFromStorage();
    await loadSelectedTeamWorkspace();
  }
  isLoading.value = false;
}

async function bootstrapDemoLobby(): Promise<LobbyDto> {
  const existing = await listLobbies();
  if (existing.length > 0) {
    return existing[0];
  }
  const games = await listGames();
  const candidate = games.find((game) => game.mode !== 'single_task') ?? games[0];
  if (!candidate) {
    throw new Error('В каталоге нет игр для создания demo-лобби');
  }
  return createLobby({
    game_id: candidate.game_id,
    title: `Demo Lobby / ${candidate.title}`,
    kind: 'training',
    access: 'public',
    max_teams: 16,
  });
}

async function refreshLobbyAndTeams(): Promise<void> {
  if (!lobby.value) return;
  lobby.value = await getLobby(lobby.value.lobby_id);
  teamsByGame.value = await listTeamsByGame(lobby.value.game_id);
  await refreshLobbyRuns();
  syncSelectedTeamFromStorage();
  await loadSelectedTeamWorkspace();
}

function startLobbyLiveUpdates(lobbyId: string): void {
  stopLobbyLiveUpdates();
  if (typeof EventSource === 'undefined') {
    startLobbyPolling(lobbyId);
    return;
  }

  lobbyEventSource = new EventSource(
    `/api/v1/lobbies/${encodeURIComponent(lobbyId)}/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`,
  );
  lobbyLiveMode.value = 'sse';

  const applyLobbySnapshot = async (payload: LobbyDto | null): Promise<void> => {
    if (!payload) return;
    lobby.value = payload;
    teamsByGame.value = await listTeamsByGame(payload.game_id);
    syncSelectedTeamFromStorage();
    await refreshLobbyRuns();
  };

  lobbyEventSource.addEventListener('agp.update', (event: MessageEvent) => {
    try {
      const envelope = JSON.parse(event.data) as StreamEnvelopeDto<LobbyDto>;
      if (envelope.channel !== 'lobby') return;
      void applyLobbySnapshot(envelope.payload ?? null);
    } catch {
      // ignore malformed stream payload
    }
  });

  lobbyEventSource.addEventListener('lobby', (event: MessageEvent) => {
    try {
      void applyLobbySnapshot(JSON.parse(event.data) as LobbyDto);
    } catch {
      // ignore malformed legacy stream payload
    }
  });

  const onTerminal = (): void => {
    stopLobbyLiveUpdates();
  };
  lobbyEventSource.addEventListener('agp.terminal', onTerminal);
  lobbyEventSource.addEventListener('terminal', onTerminal);

  lobbyEventSource.onerror = () => {
    if (lobby.value?.status === 'closed') {
      stopLobbyLiveUpdates();
      return;
    }
    stopLobbyLiveUpdates();
    startLobbyPolling(lobbyId);
  };
}

function startLobbyPolling(lobbyId: string): void {
  stopLobbyPolling();
  lobbyLiveMode.value = 'polling';
  lobbyPollingHandle = setInterval(async () => {
    try {
      lobby.value = await getLobby(lobbyId);
      if (lobby.value) {
        teamsByGame.value = await listTeamsByGame(lobby.value.game_id);
        syncSelectedTeamFromStorage();
        await refreshLobbyRuns();
      }
      if (lobby.value?.status === 'closed') {
        stopLobbyLiveUpdates();
      }
    } catch {
      // transient API errors are ignored in polling mode
    }
  }, 2000);
}

function stopLobbyPolling(): void {
  if (!lobbyPollingHandle) return;
  clearInterval(lobbyPollingHandle);
  lobbyPollingHandle = null;
}

function stopLobbyEventStream(): void {
  if (!lobbyEventSource) return;
  lobbyEventSource.close();
  lobbyEventSource = null;
}

function stopLobbyLiveUpdates(): void {
  stopLobbyEventStream();
  stopLobbyPolling();
  lobbyLiveMode.value = 'idle';
}

async function createTeamForLobbyGame(): Promise<void> {
  if (!lobby.value) return;
  await ensureOwnTeamInLobby();
  await loadSelectedTeamWorkspace();
}

async function joinSelectedTeam(): Promise<void> {
  if (!lobby.value || !selectedTeamId.value) return;
  errorMessage.value = '';
  try {
    lobby.value = await joinLobby({
      lobby_id: lobby.value.lobby_id,
      team_id: selectedTeamId.value,
    });
    persistSelectedTeamForGame(lobby.value.game_id, selectedTeamId.value);
    await loadSelectedTeamWorkspace();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось подключить команду к лобби';
  }
}

async function toggleReadySelectedTeam(): Promise<void> {
  if (!lobby.value || !selectedTeamId.value || !selectedTeamLobbyState.value) return;
  errorMessage.value = '';
  try {
    if (!selectedTeamLobbyState.value.ready) {
      await saveCodeIfDirty();
    }
    lobby.value = await setLobbyReady({
      lobby_id: lobby.value.lobby_id,
      team_id: selectedTeamId.value,
      ready: !selectedTeamLobbyState.value.ready,
    });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось изменить готовность команды';
  }
}

async function createCompetitionFromLobby(): Promise<void> {
  if (!lobby.value || !canCreateCompetitionFromLobby.value) return;
  isCreatingCompetition.value = true;
  errorMessage.value = '';
  try {
    const created = await createCompetition({
      game_id: lobby.value.game_id,
      title: `${lobby.value.title} / соревнование`,
      format: 'single_elimination',
      tie_break_policy: 'manual',
      advancement_top_k: 1,
      match_size: 2,
    });
    for (const team of lobby.value.teams) {
      await registerCompetitionTeam({
        competition_id: created.competition_id,
        team_id: team.team_id,
      });
    }
    await router.push(`/competitions/${created.competition_id}`);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось создать соревнование из лобби';
  } finally {
    isCreatingCompetition.value = false;
  }
}

async function leaveSelectedTeam(): Promise<void> {
  if (!lobby.value || !selectedTeamId.value || !selectedTeamLobbyState.value) return;
  errorMessage.value = '';
  try {
    lobby.value = await leaveLobby({
      lobby_id: lobby.value.lobby_id,
      team_id: selectedTeamId.value,
    });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось вывести команду из лобби';
  }
}

async function pauseLobby(): Promise<void> {
  if (!lobby.value || !canPauseLobby.value) return;
  errorMessage.value = '';
  try {
    lobby.value = await setLobbyStatus({
      lobby_id: lobby.value.lobby_id,
      status: 'paused',
    });
    await refreshLobbyRuns();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось поставить лобби на паузу';
  }
}

async function resumeLobby(): Promise<void> {
  if (!lobby.value || !canResumeLobby.value) return;
  errorMessage.value = '';
  try {
    lobby.value = await setLobbyStatus({
      lobby_id: lobby.value.lobby_id,
      status: 'open',
    });
    await refreshLobbyRuns();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось возобновить лобби';
  }
}

async function closeLobby(): Promise<void> {
  if (!lobby.value || !canCloseLobby.value) return;
  errorMessage.value = '';
  try {
    lobby.value = await setLobbyStatus({
      lobby_id: lobby.value.lobby_id,
      status: 'closed',
    });
    await refreshLobbyRuns();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось закрыть лобби';
  }
}

async function launchTrainingRun(): Promise<void> {
  if (!lobby.value || !selectedTeamId.value) return;
  isLaunchingRun.value = true;
  errorMessage.value = '';
  try {
    await saveCodeIfDirty();
    const created = await createRun({
      team_id: selectedTeamId.value,
      game_id: lobby.value.game_id,
      requested_by: sessionStore.nickname,
      run_kind: 'training_match',
      lobby_id: lobby.value.lobby_id,
    });
    currentRun.value = await queueRun(created.run_id);
    focusedRunId.value = currentRun.value.run_id;
    viewerMode.value = 'mine';
    await refreshLobbyAndTeams();
    startRunPolling();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось запустить тренировочную игру';
  } finally {
    isLaunchingRun.value = false;
  }
}

async function runMatchmakingTick(): Promise<void> {
  if (!lobby.value) return;
  isTickingMatchmaking.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await runLobbyMatchmakingTick({
      lobby_id: lobby.value.lobby_id,
      requested_by: sessionStore.nickname,
    });
    await refreshLobbyAndTeams();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось запустить matchmaking tick';
  } finally {
    isTickingMatchmaking.value = false;
  }
}

async function cancelTrainingRun(): Promise<void> {
  const runToCancel = activeSelectedRun.value;
  if (!runToCancel) return;
  isCancellingRun.value = true;
  errorMessage.value = '';
  try {
    currentRun.value = await cancelRun(runToCancel.run_id);
    await refreshLobbyRuns();
    stopRunPolling();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось остановить игру';
  } finally {
    isCancellingRun.value = false;
  }
}

function startRunPolling(): void {
  stopRunPolling();
  runPollingHandle = setInterval(async () => {
    if (!currentRun.value) return;
    try {
      const fresh = await getRun(currentRun.value.run_id);
      currentRun.value = fresh;
      if (!isActiveRunStatus(fresh.status)) {
        await refreshLobbyRuns();
        stopRunPolling();
      }
    } catch {
      // transient errors are ignored here
    }
  }, 1200);
}

function stopRunPolling(): void {
  if (runPollingHandle) {
    clearInterval(runPollingHandle);
    runPollingHandle = null;
  }
}

onMounted(async () => {
  await ensureLobbyLoaded();
  if (lobby.value) {
    startLobbyLiveUpdates(lobby.value.lobby_id);
  }
});

onUnmounted(() => {
  stopRunPolling();
  stopLobbyLiveUpdates();
});

watch(selectedTeamId, async (nextTeamId) => {
  if (lobby.value && nextTeamId) {
    persistSelectedTeamForGame(lobby.value.game_id, nextTeamId);
  }
  viewerMode.value = 'mine';
  await loadSelectedTeamWorkspace();
});
</script>

<style scoped>
.lobby-play-page {
  min-height: 100dvh;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 0.5rem;
  padding: 0.5rem;
  background: #06101f;
}

.lobby-play-page--running .lobby-play-header {
  border-color: rgba(37, 99, 235, 0.45);
}

.lobby-play-page--paused .lobby-play-header {
  border-color: rgba(217, 119, 6, 0.5);
}

.lobby-play-page--closed .lobby-play-header,
.lobby-play-page--updating .lobby-play-header {
  border-color: rgba(220, 38, 38, 0.42);
}

.lobby-play-header {
  min-height: 3.4rem;
  grid-template-columns: minmax(15rem, 0.9fr) minmax(20rem, 1.2fr) auto;
  padding: 0.45rem 0.6rem;
}

.lobby-play-title {
  min-width: 0;
}

.lobby-play-heading {
  min-width: 0;
}

.lobby-play-heading h1 {
  max-width: 34rem;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-play-heading .small {
  display: block;
  max-width: 38rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-meta-pills {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  max-width: 40rem;
  overflow: hidden;
}

.lobby-meta-pill {
  min-width: 0;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #9aa8bb;
  padding: 0.12rem 0.42rem;
  font-size: 0.72rem;
  font-weight: 750;
  white-space: nowrap;
}

.lobby-meta-pill--status {
  border-color: rgba(20, 184, 166, 0.28);
  color: #b7efe5;
}

.lobby-play-page--running .lobby-meta-pill--status {
  border-color: rgba(96, 165, 250, 0.36);
  color: #bfdbfe;
}

.lobby-play-page--paused .lobby-meta-pill--status {
  border-color: rgba(251, 191, 36, 0.42);
  color: #fde68a;
}

.lobby-play-page--closed .lobby-meta-pill--status,
.lobby-play-page--updating .lobby-meta-pill--status {
  border-color: rgba(248, 113, 113, 0.38);
  color: #fecaca;
}

.lobby-meta-pill--team {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  max-width: 11rem;
  color: #e5edf8;
}

.lobby-play-switcher {
  justify-content: center;
  min-width: 0;
}

.lobby-play-status {
  min-width: 10rem;
}

.lobby-play-status strong {
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-play-actions {
  gap: 0.35rem;
}

.lobby-play-actions a.agp-icon-button {
  text-decoration: none;
}

.lobby-play-columns {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(22rem, 34vw, 30rem);
  gap: 0.55rem;
  align-items: stretch;
}

.lobby-live-viewer {
  min-height: 0;
  display: grid;
  padding: 0 !important;
  overflow: hidden;
  background: #020617;
}

.lobby-live-viewer .agp-viewer-overlay {
  z-index: 3;
}

.lobby-live-frame {
  min-height: 0;
  height: 100%;
  border-radius: inherit;
}

.lobby-live-frame iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: #020617;
}

.lobby-live-caption {
  position: absolute;
  left: 0.65rem;
  right: 0.65rem;
  bottom: 0.65rem;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
  width: max-content;
  max-width: calc(100% - 1.3rem);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  background: rgba(2, 6, 23, 0.82);
  color: #dbe7f5;
  box-shadow: 0 0.75rem 2rem rgba(2, 6, 23, 0.26);
  padding: 0.36rem 0.58rem;
  font-size: 0.76rem;
  backdrop-filter: blur(12px);
}

.lobby-team-avatar {
  width: 2.2rem;
  height: 2.2rem;
  flex: 0 0 auto;
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: 0.7rem;
  display: grid;
  place-items: center;
  background: #ecfdf5;
  color: #0f766e;
  font-size: 0.78rem;
  font-weight: 900;
  letter-spacing: 0.02em;
}

.lobby-team-avatar--small {
  width: 1.65rem;
  height: 1.65rem;
  border-radius: 0.52rem;
  font-size: 0.62rem;
}

.lobby-team-avatar--tiny {
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 0.35rem;
  font-size: 0.48rem;
}

.lobby-live-caption .lobby-team-avatar {
  border-color: rgba(148, 163, 184, 0.28);
  background: rgba(15, 23, 42, 0.76);
  color: #dff8f2;
}

.lobby-live-caption strong,
.lobby-live-caption span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-live-caption .mono {
  color: #93a4b9;
}

.lobby-empty-live {
  align-self: center;
  justify-self: center;
  max-width: 31rem;
  color: #e5edf8;
  text-align: center;
  padding: 1.5rem;
}

.lobby-empty-live h2 {
  margin-bottom: 0.35rem;
  font-size: 1.25rem;
  font-weight: 850;
}

.lobby-empty-live p {
  color: #9fb0c5;
}

.lobby-empty-checklist {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.38rem;
  margin: 0.95rem auto 1rem;
}

.lobby-empty-checklist span {
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: #a8b6c9;
  padding: 0.28rem 0.52rem;
  font-size: 0.74rem;
  font-weight: 800;
}

.lobby-empty-checklist .lobby-empty-checklist--done {
  border-color: rgba(20, 184, 166, 0.35);
  background: rgba(15, 118, 110, 0.28);
  color: #ccfbf1;
}

.lobby-empty-icon {
  width: 2.75rem;
  height: 2.75rem;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 999px;
  display: grid;
  place-items: center;
  margin: 0 auto 0.7rem;
  color: #f8fafc;
  background: #111827;
}

.lobby-side-panel {
  min-height: 0;
  display: grid;
  overflow: hidden;
  background: #f8fafc;
}

.lobby-side-scroll {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  gap: 0.55rem;
  overflow-y: auto;
  padding: 0.6rem;
}

.lobby-side-section {
  border: 1px solid #dbe4ee;
  border-radius: 0.8rem;
  background: #ffffff;
  padding: 0.65rem;
}

.lobby-team-strip {
  border-color: rgba(15, 118, 110, 0.22);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.03);
}

.lobby-room-strip {
  display: grid;
  grid-template-columns: 1.1fr 0.75fr 0.55fr;
  gap: 0.35rem;
  margin-bottom: 0.55rem;
}

.lobby-room-strip div {
  min-width: 0;
  border: 1px solid #dfe7ef;
  border-radius: 0.62rem;
  background: #f8fafc;
  padding: 0.38rem 0.45rem;
}

.lobby-room-strip span {
  display: block;
  color: var(--agp-muted);
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.lobby-room-strip strong {
  display: block;
  margin-top: 0.03rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.82rem;
}

.lobby-now-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
  border: 1px solid rgba(37, 99, 235, 0.18);
  border-radius: 0.75rem;
  background: #eff6ff;
  padding: 0.48rem;
  margin-bottom: 0.55rem;
}

.lobby-now-card--idle {
  border-color: #dbe4ee;
  background: #f8fafc;
}

.lobby-now-card--active {
  border-color: rgba(37, 99, 235, 0.18);
  background: #eff6ff;
}

.lobby-now-card--success {
  border-color: rgba(15, 118, 110, 0.2);
  background: #ecfdf5;
}

.lobby-now-card--danger {
  border-color: rgba(220, 38, 38, 0.18);
  background: #fef2f2;
}

.lobby-now-card > div {
  min-width: 0;
}

.lobby-now-card span:not(.lobby-team-avatar) {
  display: block;
  color: #64748b;
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.lobby-now-card strong,
.lobby-now-card small {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-now-card strong {
  color: #172033;
  font-size: 0.85rem;
}

.lobby-now-card small {
  color: #64748b;
  font-size: 0.72rem;
}

.lobby-now-card a {
  text-decoration: none;
}

.lobby-side-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.65rem;
  margin-bottom: 0.55rem;
}

.lobby-side-title-row h2 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 850;
}

.lobby-side-title-row p {
  margin: 0.12rem 0 0;
  color: var(--agp-muted);
  font-size: 0.76rem;
  line-height: 1.25;
}

.lobby-section-count {
  min-width: 3.2rem;
  padding: 0.35rem 0.55rem;
  border: 1px solid rgba(125, 211, 252, 0.26);
  border-radius: 999px;
  color: #d8fbff;
  background: rgba(8, 47, 73, 0.56);
  text-align: center;
}

.lobby-team-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.4rem;
}

.lobby-flow-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.3rem;
  margin-bottom: 0.45rem;
}

.lobby-flow-steps span {
  min-width: 0;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  background: #f8fafc;
  color: #64748b;
  padding: 0.24rem 0.42rem;
  font-size: 0.68rem;
  font-weight: 800;
  text-align: center;
  white-space: nowrap;
}

.lobby-flow-steps .lobby-flow-step--done {
  border-color: rgba(15, 118, 110, 0.25);
  background: #ecfdf5;
  color: #0f766e;
}

.lobby-flow-meter {
  height: 0.38rem;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
  margin: -0.12rem 0 0.5rem;
}

.lobby-flow-meter span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #0f766e;
  transition: width 180ms ease;
}

.lobby-selected-team-card,
.lobby-role-summary {
  display: grid;
  gap: 0.35rem;
  border: 1px solid #dfe7ef;
  border-radius: 0.72rem;
  background: #f8fafc;
  padding: 0.5rem;
  margin-top: 0.45rem;
}

.lobby-selected-team-card {
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.85fr);
}

.lobby-selected-team-card--joined {
  border-color: rgba(37, 99, 235, 0.2);
  background: #eff6ff;
}

.lobby-selected-team-card--ready {
  border-color: rgba(15, 118, 110, 0.22);
  background: #ecfdf5;
}

.lobby-my-run-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.35rem;
  margin-top: 0.45rem;
}

.lobby-my-run-strip div {
  min-width: 0;
  border: 1px solid #dfe7ef;
  border-radius: 0.62rem;
  background: #fff;
  padding: 0.36rem 0.42rem;
}

.lobby-my-run-strip span {
  display: block;
  color: var(--agp-muted);
  font-size: 0.58rem;
  font-weight: 850;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.lobby-my-run-strip strong {
  display: block;
  margin-top: 0.03rem;
  color: #172033;
  font-size: 0.86rem;
}

.lobby-team-identity,
.lobby-row-identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.lobby-row-identity {
  align-items: flex-start;
}

.lobby-row-identity > div,
.lobby-team-identity > div {
  min-width: 0;
}

.lobby-selected-team-card span,
.lobby-role-summary span {
  display: block;
  color: var(--agp-muted);
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.lobby-selected-team-card strong,
.lobby-role-summary strong {
  display: block;
  min-width: 0;
  margin-top: 0.04rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.82rem;
}

.lobby-quick-actions,
.lobby-teacher-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.4rem;
  margin-top: 0.45rem;
}

.lobby-teacher-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.lobby-quick-actions .btn,
.lobby-teacher-grid .btn {
  min-width: 0;
  white-space: nowrap;
}

.lobby-primary-action {
  min-height: 2.15rem;
  font-weight: 850;
}

.lobby-leave-button {
  color: #64748b;
  text-decoration: none;
  font-weight: 800;
}

.lobby-leave-button:hover:not(:disabled) {
  color: #334155;
  text-decoration: underline;
}

.lobby-code-section {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  overflow: hidden;
}

.lobby-code-title-row {
  margin-bottom: 0.45rem;
}

.lobby-code-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  justify-content: flex-end;
}

.lobby-code-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.45rem;
}

.lobby-code-toolbar-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  border: 1px solid #dbe4ee;
  border-radius: 0.7rem;
  background: #f8fafc;
  padding: 0.36rem 0.5rem;
}

.lobby-code-toolbar-title .small {
  text-transform: uppercase;
  font-size: 0.62rem;
  font-weight: 850;
  letter-spacing: 0.03em;
}

.lobby-code-toolbar-title strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-code-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.lobby-code-toolbar-actions .btn {
  white-space: nowrap;
}

.lobby-save-state-dot {
  width: 0.58rem;
  height: 0.58rem;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #94a3b8;
  box-shadow: 0 0 0 0.18rem rgba(148, 163, 184, 0.16);
}

.lobby-save-state-dot--success {
  background: #0f766e;
  box-shadow: 0 0 0 0.18rem rgba(15, 118, 110, 0.16);
}

.lobby-save-state-dot--warning {
  background: #d97706;
  box-shadow: 0 0 0 0.18rem rgba(217, 119, 6, 0.16);
}

.lobby-save-state-dot--readonly {
  background: #ea580c;
  box-shadow: 0 0 0 0.18rem rgba(234, 88, 12, 0.16);
}

.lobby-save-state-dot--muted {
  background: #94a3b8;
  box-shadow: 0 0 0 0.18rem rgba(148, 163, 184, 0.14);
}

.lobby-save-button--dirty {
  box-shadow: 0 0 0 0.16rem rgba(15, 23, 42, 0.08);
}

.lobby-code-hint {
  border: 1px solid #dbe4ee;
  border-radius: 0.7rem;
  background: #f8fafc;
  color: #526170;
  padding: 0.42rem 0.52rem;
  margin: -0.12rem 0 0.45rem;
  font-size: 0.76rem;
  line-height: 1.35;
}

.lobby-code-hint--success {
  border-color: rgba(15, 118, 110, 0.2);
  background: #ecfdf5;
  color: #0f766e;
}

.lobby-code-hint--warning {
  border-color: #fde68a;
  background: #fffbeb;
  color: #92400e;
}

.lobby-code-hint--readonly {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #9a3412;
}

.lobby-code-section .agp-code-editor {
  min-height: 0;
  height: 100%;
}

.lobby-role-tabs {
  display: flex;
  gap: 0.35rem;
  overflow-x: auto;
  padding-bottom: 0.25rem;
  margin-bottom: 0.4rem;
}

.lobby-role-tab {
  min-width: 6.8rem;
  border: 1px solid #d7e1eb;
  border-radius: 0.68rem;
  background: #fff;
  color: #172033;
  padding: 0.38rem 0.52rem;
  display: grid;
  gap: 0.08rem;
  text-align: left;
  transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
}

.lobby-role-tab:hover {
  border-color: rgba(15, 118, 110, 0.38);
  transform: translateY(-1px);
}

.lobby-role-name {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  min-width: 0;
  font-weight: 800;
}

.lobby-role-name small {
  flex: 0 0 auto;
  border: 1px solid #dbe4ee;
  border-radius: 999px;
  color: #64748b;
  padding: 0.02rem 0.28rem;
  font-size: 0.58rem;
  font-weight: 850;
}

.lobby-role-tab--active {
  border-color: rgba(15, 118, 110, 0.62);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.2);
}

.lobby-role-tab--filled {
  border-left: 0.22rem solid #0f766e;
}

.lobby-role-tab--empty {
  border-left: 0.22rem solid #cbd5e1;
}

.lobby-role-tab--dirty {
  border-left: 0.22rem solid #d97706;
}

.lobby-role-tab--locked,
.lobby-role-tab--incompatible {
  border-left: 0.22rem solid #dc2626;
}

.lobby-role-state {
  color: var(--agp-muted);
  font-size: 0.68rem;
  font-weight: 750;
}

.lobby-role-summary {
  grid-template-columns: minmax(0, 1fr) 5rem 4.5rem;
  margin: -0.05rem 0 0.45rem;
}

.lobby-empty-code {
  border: 1px dashed #cbd5e1;
  border-radius: 0.75rem;
  color: var(--agp-muted);
  padding: 0.85rem;
}

.lobby-readonly-note {
  border: 1px solid #fde68a;
  border-radius: 0.72rem;
  background: #fffbeb;
  color: #92400e;
  padding: 0.48rem 0.58rem;
  margin-bottom: 0.45rem;
  font-size: 0.78rem;
}

.lobby-compact-details {
  padding: 0.6rem 0.65rem;
}

.lobby-details-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
}

.lobby-details-summary strong {
  flex: 0 0 auto;
  border: 1px solid #dbe4ee;
  border-radius: 999px;
  background: #f8fafc;
  color: #64748b;
  padding: 0.12rem 0.42rem;
  font-size: 0.68rem;
  font-weight: 850;
}

.lobby-stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.35rem;
}

.lobby-stat {
  border: 1px solid #dce5ee;
  border-radius: 0.65rem;
  background: #fff;
  padding: 0.45rem;
}

.lobby-stat span {
  display: block;
  color: var(--agp-muted);
  font-size: 0.62rem;
  text-transform: uppercase;
  font-weight: 800;
  letter-spacing: 0.03em;
}

.lobby-stat strong {
  display: block;
  margin-top: 0.08rem;
  font-size: 0.86rem;
  overflow-wrap: anywhere;
}

.lobby-team-list,
.lobby-match-list {
  display: grid;
  gap: 0.4rem;
}

.lobby-team-row,
.lobby-match-row {
  border: 1px solid #dde6ef;
  border-left: 0.24rem solid transparent;
  border-radius: 0.72rem;
  background: #fff;
  padding: 0.55rem;
  display: flex;
  justify-content: space-between;
  gap: 0.6rem;
  align-items: flex-start;
  transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
}

.lobby-match-row:hover {
  border-color: rgba(15, 118, 110, 0.3);
  box-shadow: 0 0.55rem 1.35rem rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.lobby-team-row--ready {
  border-left-color: var(--agp-primary);
  background: #f0fdfa;
}

.lobby-team-row--blocked {
  border-left-color: #dc2626;
  background: #fef2f2;
}

.lobby-team-row--current {
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.28);
}

.lobby-match-status-line {
  display: flex;
  align-items: center;
  gap: 0.38rem;
  color: var(--agp-muted);
  font-size: 0.76rem;
}

.lobby-match-row--selected {
  border-color: rgba(15, 118, 110, 0.42);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.18);
}

.lobby-match-row--active {
  border-left-color: #2563eb;
}

.lobby-match-row--finished {
  border-left-color: #0f766e;
}

.lobby-match-row--failed {
  border-left-color: #dc2626;
}

.lobby-drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 35;
  border: 0;
  background: rgba(2, 6, 23, 0.56);
}

.lobby-matches-drawer {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 36;
  width: min(32rem, 94vw);
  overflow-y: auto;
  background: #f8fafc;
  border-right: 1px solid #dbe4ee;
  box-shadow: 20px 0 50px rgba(2, 6, 23, 0.28);
  padding: 0.85rem;
}

.lobby-drawer-header {
  position: sticky;
  top: -0.85rem;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  background: #f8fafc;
  border-bottom: 1px solid #dbe4ee;
  margin: -0.85rem -0.85rem 0.8rem;
  padding: 0.85rem;
}

.lobby-drawer-counters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-left: auto;
}

.lobby-drawer-counters span {
  border: 1px solid #dbe4ee;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  padding: 0.22rem 0.48rem;
  font-size: 0.72rem;
  font-weight: 800;
  white-space: nowrap;
}

.lobby-matches-drawer pre {
  max-height: 18rem;
  overflow: auto;
}

@media (max-width: 1180px) {
  .lobby-play-header {
    grid-template-columns: 1fr;
  }

  .lobby-play-switcher,
  .lobby-play-actions {
    justify-content: flex-start;
  }

  .lobby-play-columns {
    grid-template-columns: 1fr;
  }

  .lobby-live-viewer {
    min-height: 34rem;
  }

  .lobby-side-scroll {
    max-height: none;
  }
}

@media (max-width: 720px) {
  .lobby-play-page {
    min-height: auto;
    padding: 0.35rem;
  }

  .lobby-play-heading h1,
  .lobby-play-heading .small,
  .lobby-play-status strong {
    max-width: 100%;
  }

  .lobby-play-switcher,
  .lobby-play-actions,
  .lobby-team-controls,
  .lobby-code-toolbar,
  .lobby-code-toolbar-actions,
  .lobby-selected-team-card,
  .lobby-my-run-strip,
  .lobby-quick-actions,
  .lobby-teacher-grid,
  .lobby-stat-grid,
  .lobby-role-summary,
  .lobby-team-row,
  .lobby-match-row {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }

  .lobby-live-viewer {
    min-height: 28rem;
  }
}
</style>
