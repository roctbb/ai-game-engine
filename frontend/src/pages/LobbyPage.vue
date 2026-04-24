<template>
  <section class="agp-grid">
    <header>
      <RouterLink to="/lobbies" class="small text-decoration-none">← К лобби</RouterLink>
      <h1 class="h3 mb-1">{{ lobby?.title || 'Лобби' }}</h1>
      <p class="text-muted mb-0">
        Выберите команду, вставьте код и нажмите “Готов”. Когда игра начнется, здесь появится просмотр.
      </p>
    </header>

    <div v-if="isLoading" class="agp-card p-4 text-muted">Загрузка лобби...</div>
    <div v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</div>

    <template v-else-if="lobby">
      <LobbyStatusBanner :status="lobby.status" />

      <div class="agp-lobby-layout">
        <article class="agp-card p-3">
          <div class="d-flex justify-content-between align-items-start gap-2 mb-3">
            <div>
              <h2 class="h6 mb-1">Команды</h2>
              <div class="small text-muted">{{ lobby.teams.length }} из {{ lobby.max_teams }}</div>
            </div>
            <span class="agp-pill" :class="lobby.status === 'running' ? 'agp-pill--warning' : 'agp-pill--primary'">
              {{ lobbyStatusLabel }}
            </span>
          </div>

          <div v-if="lobby.teams.length === 0" class="small text-muted">
            Пока никто не вошел. Создайте команду или вернитесь к списку лобби и нажмите “Войти”.
          </div>
          <div v-else class="agp-grid">
            <div
              v-for="team in lobby.teams"
              :key="team.team_id"
              class="agp-card-soft p-3 d-flex justify-content-between gap-3 align-items-start"
            >
              <div>
                <div class="fw-semibold">{{ teamName(team.team_id) }}</div>
                <div v-if="team.blocker_reason" class="small text-danger mt-1">{{ team.blocker_reason }}</div>
              </div>
              <span class="agp-pill" :class="team.ready ? 'agp-pill--primary' : 'agp-pill--warning'">
                {{ team.ready ? 'готов' : 'ждет' }}
              </span>
            </div>
          </div>
        </article>

        <article class="agp-card p-3">
          <h2 class="h6">Моя команда</h2>
          <div v-if="!canManageLobbyLifecycle" class="small text-warning-emphasis mb-2">
            Управление лобби доступно учителю или администратору.
          </div>

          <label class="form-label small">Выбранная команда</label>
          <select v-model="selectedTeamId" class="form-select mb-3">
            <option value="">Выберите команду</option>
            <option v-for="team in teamsByGame" :key="team.team_id" :value="team.team_id">
              {{ team.name }}
            </option>
          </select>

          <div class="d-flex flex-wrap gap-2 mb-2">
            <button class="btn btn-sm btn-outline-secondary" :disabled="isCreatingTeam" @click="createTeamForLobbyGame">
              {{ isCreatingTeam ? 'Создание...' : 'Создать команду' }}
            </button>
            <button class="btn btn-sm btn-dark" :disabled="!canJoin" @click="joinSelectedTeam">
              Войти в лобби
            </button>
            <button class="btn btn-sm btn-outline-dark" :disabled="!canToggleReady" @click="toggleReadySelectedTeam">
              {{ isSelectedTeamReady ? 'Снять готовность' : 'Готов' }}
            </button>
            <button class="btn btn-sm btn-outline-secondary" :disabled="!canLeave" @click="leaveSelectedTeam">
              Выйти
            </button>
          </div>

          <details v-if="canManageLobbyLifecycle" class="mt-3">
            <summary class="agp-details-summary">Инструменты учителя</summary>
            <div class="agp-grid mt-3">
              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-sm btn-outline-warning" :disabled="!canPauseLobby" @click="pauseLobby">
                  Пауза
                </button>
                <button class="btn btn-sm btn-outline-primary" :disabled="!canResumeLobby" @click="resumeLobby">
                  Продолжить
                </button>
                <button class="btn btn-sm btn-outline-danger" :disabled="!canCloseLobby" @click="closeLobby">
                  Закрыть
                </button>
                <button class="btn btn-sm btn-outline-dark" :disabled="!canCreateCompetitionFromLobby || isCreatingCompetition" @click="createCompetitionFromLobby">
                  {{ isCreatingCompetition ? 'Создание...' : 'Сделать турнир' }}
                </button>
              </div>
              <button class="btn btn-sm btn-outline-success" :disabled="!canRunMatchmakingTick" @click="runMatchmakingTick">
                {{ isTickingMatchmaking ? 'Запуск игры...' : 'Запустить подбор игры' }}
              </button>
            </div>
          </details>

          <div class="d-flex flex-wrap gap-2 mt-3">
            <button class="btn btn-sm btn-outline-primary" :disabled="!canLaunchTrainingRun" @click="launchTrainingRun">
              {{ isLaunchingRun ? 'Запуск...' : 'Запустить игру' }}
            </button>
            <button class="btn btn-sm btn-outline-danger" :disabled="!canCancelRun" @click="cancelTrainingRun">
              {{ isCancellingRun ? 'Остановка...' : 'Остановить' }}
            </button>
          </div>
          <div v-if="currentRun" class="small mono text-muted mt-2">
            {{ runStatusText(currentRun.status) }}
            <RouterLink class="ms-2" :to="`/runs/${currentRun.run_id}/watch`">Смотреть</RouterLink>
          </div>
        </article>
      </div>

      <article class="agp-card p-3">
        <div class="d-flex justify-content-between align-items-center gap-2 flex-wrap mb-2">
          <div>
            <h2 class="h6 mb-0">Код команды</h2>
            <div class="small text-muted">
              {{ selectedTeamId ? 'Код будет сохранен для выбранной команды' : 'Сначала выберите или создайте команду' }}
            </div>
          </div>
          <div class="d-flex gap-2 flex-wrap">
            <button class="btn btn-sm btn-outline-secondary" :disabled="!selectedSlotKey" @click="applyTemplateToSelectedSlot">
              Шаблон
            </button>
            <button class="btn btn-sm btn-outline-secondary" :disabled="!selectedSlotDemoCode" @click="applyDemoToSelectedSlot">
              Демо
            </button>
            <button class="btn btn-sm btn-dark" :disabled="!canSaveSelectedCode" @click="saveSelectedSlotCode">
              {{ isSavingCode ? 'Сохранение...' : 'Сохранить код' }}
            </button>
          </div>
        </div>
        <div v-if="workspaceError" class="small text-danger mb-2">{{ workspaceError }}</div>
        <div v-if="!selectedTeamId" class="small text-muted">Создайте или выберите команду, чтобы редактировать код.</div>
        <CodeEditor
          v-else
          v-model="editorCode"
          :readonly="isSavingCode || isRunActive"
          language="python"
        />
        <div class="small text-muted mt-2">Если нажать “Готов” с изменениями, код сначала сохранится.</div>
      </article>

      <article class="agp-card p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Последние игры</h2>
          <RouterLink
            v-if="lobby"
            class="btn btn-sm btn-outline-secondary"
            :to="`/replays?game_id=${lobby.game_id}&run_kind=training_match`"
          >
            Все повторы
          </RouterLink>
        </div>
        <div v-if="lobbyRuns.length === 0" class="text-muted small">Игр в этом лобби пока не было.</div>
        <div v-else class="agp-grid">
          <div
            v-for="item in lobbyRuns"
            :key="item.run_id"
            class="agp-card-soft p-3 d-flex justify-content-between gap-3 align-items-center flex-wrap"
          >
            <div>
              <div class="fw-semibold">{{ teamName(item.team_id) }}</div>
              <div class="small text-muted">
                {{ runStatusText(item.status) }}
                <RunReasonBadge v-if="item.error_message" :reason="item.error_message" />
              </div>
            </div>
            <div class="d-flex gap-2">
              <button class="btn btn-sm btn-outline-dark" @click="inspectRunReplay(item.run_id)">Данные</button>
              <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/runs/${item.run_id}/watch`">
                Смотреть
              </RouterLink>
            </div>
          </div>
        </div>
      </article>

      <article class="agp-card p-3" v-if="inspectedRunId">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Данные повтора</h2>
        </div>
        <div v-if="isInspectReplayLoading" class="text-muted small">Загрузка повтора...</div>
        <div v-else-if="inspectReplayError" class="text-danger small">{{ inspectReplayError }}</div>
        <div v-else-if="inspectedReplay">
          <div class="small text-muted mb-2">
            кадров: <span class="mono">{{ inspectedReplay.frames.length }}</span>
          </div>
          <pre class="mono small mb-0">{{ inspectedReplaySummary }}</pre>
        </div>
        <div v-else class="text-muted small">Для выбранной игры повтор пока недоступен.</div>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import CodeEditor from '../components/CodeEditor.vue';
import LobbyStatusBanner from '../components/LobbyStatusBanner.vue';
import RunReasonBadge from '../components/RunReasonBadge.vue';
import {
  cancelRun,
  createCompetition,
  createLobby,
  createRun,
  createTeam,
  getGameTemplates,
  getLobby,
  getRunReplay,
  getRun,
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
  setLobbyStatus,
  setLobbyReady,
  updateSlotCode,
  type StreamEnvelopeDto,
  type GameTemplatesDto,
  type LobbyDto,
  type ReplayDto,
  type RunDto,
  type TeamWorkspaceDto,
  type TeamDto,
} from '../lib/api';
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

const isSelectedTeamReady = computed(() => Boolean(selectedTeamLobbyState.value?.ready));
const canJoin = computed(() => Boolean(lobby.value && selectedTeamId.value) && !selectedTeamLobbyState.value && ['open', 'draft'].includes(lobby.value!.status));
const canToggleReady = computed(() => Boolean(lobby.value && selectedTeamId.value && selectedTeamLobbyState.value) && ['open', 'draft'].includes(lobby.value!.status));
const canLeave = computed(() => Boolean(lobby.value && selectedTeamId.value && selectedTeamLobbyState.value) && lobby.value!.status !== 'closed');
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
const canLaunchTrainingRun = computed(() => Boolean(lobby.value && selectedTeamId.value) && !isRunActive.value);
const canCancelRun = computed(() => Boolean(currentRun.value && isRunActive.value) && !isCancellingRun.value);
const canRunMatchmakingTick = computed(
  () => Boolean(lobby.value) && ['open', 'running'].includes(lobby.value!.status) && !isTickingMatchmaking.value
);
const canCreateCompetitionFromLobby = computed(
  () => Boolean(lobby.value) && canManageLobbyLifecycle.value && lobby.value!.teams.length >= 2
);
const isRunActive = computed(() => ['created', 'queued', 'running'].includes(currentRun.value?.status ?? ''));
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
const canSaveSelectedCode = computed(
  () => Boolean(selectedTeamId.value && selectedSlotKey.value && editorCode.value.trim()) && !isSavingCode.value
);

function teamName(teamId: string): string {
  const found = teamsByGame.value.find((item) => item.team_id === teamId);
  return found?.name ?? teamId;
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

function readTeamByGameMap(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem('agp_team_by_game') ?? '{}') as Record<string, string>;
  } catch {
    return {};
  }
}

function writeTeamByGameMap(map: Record<string, string>): void {
  localStorage.setItem('agp_team_by_game', JSON.stringify(map));
}

function persistSelectedTeamForGame(gameId: string, teamId: string): void {
  const map = readTeamByGameMap();
  map[gameId] = teamId;
  writeTeamByGameMap(map);
}

function syncSelectedTeamFromStorage(): void {
  if (!lobby.value) return;
  const mapped = readTeamByGameMap()[lobby.value.game_id] ?? '';
  if (mapped && teamsByGame.value.some((team) => team.team_id === mapped)) {
    selectedTeamId.value = mapped;
    return;
  }
  if (teamsByGame.value[0]) {
    selectedTeamId.value = teamsByGame.value[0].team_id;
    return;
  }
  selectedTeamId.value = '';
}

function syncEditorFromWorkspace(payload: TeamWorkspaceDto): void {
  selectedSlotKey.value = payload.slot_states[0]?.slot_key ?? '';
  const selectedSlot = payload.slot_states.find((slot) => slot.slot_key === selectedSlotKey.value);
  const initialCode = selectedSlot?.code ?? selectedSlotTemplateCode.value ?? selectedSlotDemoCode.value ?? '';
  editorCode.value = initialCode;
  savedCode.value = selectedSlot?.code ?? '';
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
    `/api/v1/lobbies/${encodeURIComponent(lobbyId)}/stream?poll_interval_ms=1000`,
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
  isCreatingTeam.value = true;
  errorMessage.value = '';
  try {
    const created = await createTeam({
      game_id: lobby.value.game_id,
      name: `${sessionStore.nickname} / ${new Date().toISOString().slice(11, 19)}`,
      captain_user_id: sessionStore.nickname,
    });
    await refreshLobbyAndTeams();
    selectedTeamId.value = created.team_id;
    persistSelectedTeamForGame(lobby.value.game_id, created.team_id);
    await loadSelectedTeamWorkspace();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось создать команду';
  } finally {
    isCreatingTeam.value = false;
  }
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
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось изменить ready-состояние';
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
    await refreshLobbyAndTeams();
    startRunPolling();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось запустить тренировочный run';
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
  if (!currentRun.value || !isRunActive.value) return;
  isCancellingRun.value = true;
  errorMessage.value = '';
  try {
    currentRun.value = await cancelRun(currentRun.value.run_id);
    if (lobby.value) {
      await refreshLobbyRuns();
    }
    stopRunPolling();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось остановить run';
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
      if (!['created', 'queued', 'running'].includes(fresh.status)) {
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
  await loadSelectedTeamWorkspace();
});
</script>
