<template>
  <section class="agp-grid lobbies-page-simple">
    <header class="agp-card p-4 lobbies-simple-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between align-items-start gap-3">
        <div>
          <p class="lobbies-kicker mb-1">Матчи и соревнования</p>
          <h1 class="h3 mb-1">Лобби</h1>
          <p class="text-muted mb-0">
            Ученики входят как игроки, преподаватель открывает лобби для управления.
          </p>
        </div>
        <div class="lobbies-controls">
          <div class="lobbies-filter-wrap">
            <label class="form-label small mb-1">Игра</label>
            <select v-model="selectedGameId" class="form-select">
              <option value="">Все игры</option>
              <option v-for="game in lobbyGames" :key="game.game_id" :value="game.game_id">
                {{ game.title }}
              </option>
            </select>
          </div>
          <RouterLink
            v-if="canManage"
            class="btn btn-dark lobbies-create-btn"
            :to="createLobbyRoute"
          >
            Создать лобби
          </RouterLink>
        </div>
      </div>

      <div class="lobbies-head-stats">
        <div>
          <span>Показано</span>
          <strong class="mono">{{ filteredLobbies.length }}/{{ sortedLobbies.length }}</strong>
        </div>
        <div>
          <span>Открыто</span>
          <strong class="mono">{{ openLobbyCount }}</strong>
        </div>
        <div>
          <span>Идет игра</span>
          <strong class="mono">{{ runningLobbyCount }}</strong>
        </div>
        <div>
          <span>По коду</span>
          <strong class="mono">{{ codeLobbyCount }}</strong>
        </div>
      </div>
      <div v-if="selectedGameId" class="lobbies-active-filter mt-2">
        <span>Фильтр:</span>
        <strong>{{ selectedGameTitle }}</strong>
        <button class="btn btn-sm btn-link p-0" type="button" @click="selectedGameId = ''">сбросить</button>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <section class="lobbies-card-grid">
      <article v-if="isLoading && lobbies.length === 0" class="agp-card p-4 lobbies-empty-card">
        <div class="agp-loading-state agp-loading-state--compact">Загрузка лобби...</div>
      </article>
      <article v-else-if="filteredLobbies.length === 0" class="agp-card p-4">
        <div class="agp-empty-state">
          <div>
            <h2 class="h6 mb-1">{{ selectedGameId ? 'Лобби по выбранной игре не найдены' : 'Открытых лобби пока нет' }}</h2>
            <p class="small mb-0">
              {{ selectedGameId ? 'Смените игру в фильтре или выберите "Все игры".' : 'Когда преподаватель создаст лобби, оно появится здесь.' }}
            </p>
          </div>
        </div>
      </article>

      <article
        v-for="lobby in filteredLobbies"
        :key="lobby.lobby_id"
        class="agp-card agp-lobby-card p-3 lobby-card-simple"
        :class="`lobby-card-simple--${lobby.status}`"
      >
        <div class="lobby-card-content">
          <div class="lobby-main">
            <div class="d-flex gap-2 flex-wrap mb-2">
              <span class="agp-pill" :class="statusClass(lobby.status)">{{ statusLabel(lobby.status) }}</span>
              <span v-if="lobby.access === 'code'" class="agp-pill agp-pill--neutral">по коду</span>
            </div>
            <h2 class="h5 mb-1">{{ lobby.title }}</h2>
            <p class="small text-muted mb-0">{{ gameTitle(lobby.game_id) }}</p>
            <div class="lobby-card-meter mt-3">
              <div>
                <span>Игроки</span>
                <strong class="mono">{{ lobbyPlayersLabel(lobby) }}</strong>
              </div>
              <i :style="{ width: `${lobbyOccupancyPercent(lobby)}%` }"></i>
            </div>
            <label
              v-if="needsAccessCode(lobby)"
              class="lobby-access-code-field mt-3"
              @click.stop
            >
              <span class="form-label small mb-1">Код входа</span>
              <input
                v-model.trim="accessCodeByLobbyId[lobby.lobby_id]"
                class="form-control form-control-sm"
                autocomplete="off"
                placeholder="Введите код"
                @keyup.enter="enterLobby(lobby)"
              />
              <span class="small text-muted">Участники и матчи откроются после входа.</span>
            </label>
          </div>
          <div class="agp-lobby-actions lobby-actions-simple">
            <button
              class="btn btn-dark"
              :disabled="!canEnterLobby(lobby) || busyLobbyId === lobby.lobby_id"
              @click="enterLobby(lobby)"
            >
              {{ enterButtonText(lobby) }}
            </button>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import {
  joinLobbyAsUser,
  listGames,
  listLobbies,
  type GameDto,
  type LobbyDto,
  type LobbyStatus,
  type StreamEnvelopeDto,
} from '../lib/api';
import { createResilientSSE } from '../lib/resilientSSE';
import { useSessionStore } from '../stores/session';

const router = useRouter();
const sessionStore = useSessionStore();

const isLoading = ref(false);
const busyLobbyId = ref('');
const errorMessage = ref('');
const games = ref<GameDto[]>([]);
const lobbies = ref<LobbyDto[]>([]);
const selectedGameId = ref('');
const accessCodeByLobbyId = reactive<Record<string, string>>({});
let lobbiesEventSource: EventSource | null = null;
let lobbiesPollingHandle: ReturnType<typeof setInterval> | null = null;

const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const lobbyGames = computed(() =>
  games.value
    .filter((game) => isLobbyCatalogGame(game))
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title))
);
const createLobbyRoute = computed(() =>
  selectedGameId.value
    ? { name: 'lobby-create', query: { game_id: selectedGameId.value } }
    : { name: 'lobby-create' }
);
const sortedLobbies = computed(() => {
  const weight: Record<LobbyStatus, number> = {
    open: 0,
    draft: 1,
    running: 2,
    paused: 3,
    stopped: 4,
    updating: 5,
    closed: 6,
  };
  return [...lobbies.value].sort((a, b) => weight[a.status] - weight[b.status] || a.title.localeCompare(b.title));
});
const filteredLobbies = computed(() => {
  if (!selectedGameId.value) return sortedLobbies.value;
  return sortedLobbies.value.filter((lobby) => lobby.game_id === selectedGameId.value);
});
const selectedGameTitle = computed(() => selectedGameId.value ? gameTitle(selectedGameId.value) : '');
const openLobbyCount = computed(() => filteredLobbies.value.filter((lobby) => lobby.status === 'open' || lobby.status === 'draft').length);
const runningLobbyCount = computed(() => filteredLobbies.value.filter((lobby) => lobby.status === 'running').length);
const codeLobbyCount = computed(() => filteredLobbies.value.filter((lobby) => lobby.access === 'code').length);

function statusLabel(status: LobbyStatus): string {
  const labels: Record<LobbyStatus, string> = {
    draft: 'готовится',
    open: 'открыто',
    running: 'игра идет',
    paused: 'пауза',
    stopped: 'остановлено',
    updating: 'обновляется',
    closed: 'закрыто',
  };
  return labels[status];
}

function statusClass(status: LobbyStatus): string {
  if (status === 'open' || status === 'draft') return 'agp-pill--primary';
  if (status === 'running') return 'agp-pill--warning';
  if (status === 'closed' || status === 'stopped') return 'agp-pill--danger';
  return 'agp-pill--neutral';
}

function gameTitle(gameId: string): string {
  return games.value.find((game) => game.game_id === gameId)?.title ?? gameId;
}

function isLobbyCatalogGame(game: GameDto): boolean {
  return game.mode !== 'single_task' && game.catalog_metadata_status === 'ready';
}

function canEnterLobby(lobby: LobbyDto): boolean {
  if (lobby.status === 'closed' || lobby.status === 'updating' || lobby.status === 'stopped') return canManage.value;
  if (canManage.value) return true;
  if (lobby.status === 'paused') return Boolean(lobby.my_team_id);
  if (needsAccessCode(lobby)) return Boolean((accessCodeByLobbyId[lobby.lobby_id] ?? '').trim());
  return lobby.teams.length < lobby.max_teams || Boolean(lobby.my_team_id);
}

function enterButtonText(lobby: LobbyDto): string {
  if (busyLobbyId.value === lobby.lobby_id) return 'Входим...';
  if (canManage.value && !lobby.my_team_id) return 'Открыть';
  if (lobby.my_team_id) return 'Вернуться';
  if (needsAccessCode(lobby)) return 'Войти по коду';
  return 'Войти';
}

function needsAccessCode(lobby: LobbyDto): boolean {
  return lobby.access === 'code' && !lobby.my_team_id && !canManage.value;
}

function hasHiddenLobbyDetails(lobby: LobbyDto): boolean {
  return lobby.access === 'code' && !lobby.my_team_id && !canManage.value;
}

function lobbyPlayersLabel(lobby: LobbyDto): string {
  if (hasHiddenLobbyDetails(lobby)) return 'скрыты до входа';
  return `${lobby.teams.length} / ${lobby.max_teams}`;
}

function lobbyOccupancyPercent(lobby: LobbyDto): number {
  if (hasHiddenLobbyDetails(lobby)) return 0;
  if (!lobby.max_teams) return 0;
  return Math.max(0, Math.min(100, Math.round((lobby.teams.length / lobby.max_teams) * 100)));
}

async function enterLobby(lobby: LobbyDto): Promise<void> {
  if (!canEnterLobby(lobby)) return;
  busyLobbyId.value = lobby.lobby_id;
  errorMessage.value = '';
  try {
    if (canManage.value && !lobby.my_team_id) {
      await router.push(`/lobbies/${lobby.lobby_id}`);
      return;
    }
    if (!lobby.my_team_id) {
      await joinLobbyAsUser({
        lobby_id: lobby.lobby_id,
        access_code: lobby.access === 'code' ? accessCodeByLobbyId[lobby.lobby_id] : null,
      });
    }
    await router.push(`/lobbies/${lobby.lobby_id}`);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось войти в лобби';
  } finally {
    busyLobbyId.value = '';
  }
}

async function loadData(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const [fetchedGames, fetchedLobbies] = await Promise.all([listGames(), listLobbies()]);
    games.value = fetchedGames;
    lobbies.value = fetchedLobbies;

    if (selectedGameId.value && !lobbyGames.value.some((game) => game.game_id === selectedGameId.value)) {
      selectedGameId.value = '';
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить лобби';
  } finally {
    isLoading.value = false;
  }
}

function startLobbiesLiveUpdates(): void {
  stopLobbiesLiveUpdates();
  if (typeof EventSource === 'undefined') {
    startLobbiesPolling();
    return;
  }

  const sse = createResilientSSE({
    url: `/api/v1/lobbies/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`,
    onOpen(source) {
      source.addEventListener('agp.update', (event: MessageEvent) => {
        try {
          const envelope = JSON.parse(event.data) as StreamEnvelopeDto<{ items?: LobbyDto[] }>;
          if (envelope.channel !== 'lobbies') return;
          const items = envelope.payload?.items;
          if (!Array.isArray(items)) return;
          lobbies.value = items;
        } catch {
          // Ignore malformed stream payload; the next snapshot will repair state.
        }
      });
    },
    onFallbackToPolling() {
      startLobbiesPolling();
    },
  });
  lobbiesEventSource = sse as unknown as EventSource;
}

function startLobbiesPolling(): void {
  stopLobbiesPolling();
  lobbiesPollingHandle = setInterval(async () => {
    if (document.hidden) return;
    try {
      lobbies.value = await listLobbies();
    } catch {
      // Keep last valid snapshot; next tick may succeed.
    }
  }, 5000);
}

function stopLobbiesPolling(): void {
  if (!lobbiesPollingHandle) return;
  clearInterval(lobbiesPollingHandle);
  lobbiesPollingHandle = null;
}

function stopLobbiesEventStream(): void {
  if (!lobbiesEventSource) return;
  (lobbiesEventSource as unknown as { close: () => void }).close();
  lobbiesEventSource = null;
}

function stopLobbiesLiveUpdates(): void {
  stopLobbiesEventStream();
  stopLobbiesPolling();
}

onMounted(async () => {
  await loadData();
  startLobbiesLiveUpdates();
});

onUnmounted(() => {
  stopLobbiesLiveUpdates();
});
</script>

<style scoped>
.lobbies-page-simple {
  gap: 0.9rem;
}

.lobbies-simple-head {
  position: relative;
  overflow: hidden;
  background:
    url("data:image/svg+xml,%3Csvg width='176' height='104' viewBox='0 0 176 104' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.12' stroke-width='2'%3E%3Cpath d='M18 18h28v28H18zM130 18h28v28h-28zM74 58h28v28H74z'/%3E%3Cpath d='M46 32h28M102 72h28M88 0v24M88 80v24'/%3E%3C/g%3E%3C/svg%3E") right 1rem top 0.8rem / 14rem auto no-repeat,
    radial-gradient(circle at 10% 20%, rgba(20, 184, 166, 0.16), transparent 16rem),
    radial-gradient(circle at 92% 10%, rgba(245, 158, 11, 0.18), transparent 15rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.95));
}

.lobbies-simple-head::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.22rem;
  background: linear-gradient(90deg, #14b8a6, #2563eb, #f59e0b);
}

.lobbies-kicker {
  color: var(--agp-primary);
  font-size: 0.76rem;
  font-weight: 900;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.lobbies-filter-wrap {
  width: min(18rem, 100%);
}

.lobbies-controls {
  display: flex;
  align-items: flex-end;
  gap: 0.55rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.lobbies-create-btn {
  white-space: nowrap;
}

.lobbies-head-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
  margin-top: 1rem;
}

.lobbies-head-stats > div {
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 0.6rem;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  background: rgba(255, 255, 255, 0.72);
  padding: 0.52rem 0.68rem;
  backdrop-filter: blur(8px);
}

.lobbies-head-stats span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobbies-head-stats strong {
  color: var(--agp-text);
  font-size: 0.96rem;
}

.lobbies-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 18rem), 18rem));
  gap: 0.75rem;
  justify-content: start;
}

.lobbies-empty-card {
  grid-column: 1 / -1;
}

.lobbies-active-filter {
  display: flex;
  gap: 0.4rem;
  align-items: baseline;
  flex-wrap: wrap;
  color: var(--agp-text-muted);
}

.lobbies-active-filter strong {
  color: var(--agp-text);
}

.lobby-card-simple {
  position: relative;
  overflow: hidden;
  gap: 0.45rem;
  align-content: start;
  min-height: 13.25rem;
  transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
}

.lobby-card-simple::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.28rem;
  background: linear-gradient(90deg, #14b8a6, #2563eb, #f59e0b);
}

.lobby-card-simple--running::before {
  background: linear-gradient(90deg, #f59e0b, #14b8a6, #2563eb);
}

.lobby-card-simple--closed::before {
  background: linear-gradient(90deg, #94a3b8, #64748b);
}

.lobby-card-simple--paused::before,
.lobby-card-simple--updating::before {
  background: linear-gradient(90deg, #64748b, #22d3ee);
}

.lobby-card-simple:hover {
  transform: translateY(-2px);
  border-color: rgba(20, 184, 166, 0.42);
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.11);
}

.lobby-card-simple h2 {
  font-size: 1rem;
  font-weight: 900;
}

.lobby-card-content {
  position: relative;
  display: grid;
  gap: 0.75rem;
}

.lobby-card-content::after {
  content: '';
  position: absolute;
  right: -1.2rem;
  bottom: -1.4rem;
  width: 5rem;
  height: 5rem;
  border-radius: 1.2rem;
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.12), rgba(37, 99, 235, 0.1)),
    url("data:image/svg+xml,%3Csvg width='80' height='80' viewBox='0 0 80 80' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.28'%3E%3Cpath d='M12 40h56M40 12v56M26 26h28v28H26z'/%3E%3C/g%3E%3C/svg%3E");
  pointer-events: none;
}

.lobby-card-simple .btn {
  white-space: nowrap;
  width: 100%;
}

.lobby-main {
  min-width: 0;
}

.lobby-access-code-field {
  display: block;
  width: min(15rem, 100%);
}

.lobby-card-meter {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 0.55rem;
  background: rgba(248, 250, 252, 0.84);
  padding: 0.5rem 0.6rem 0.7rem;
}

.lobby-card-meter > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}

.lobby-card-meter span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
  font-weight: 700;
}

.lobby-card-meter::after {
  content: '';
  position: absolute;
  left: 0.6rem;
  right: 0.6rem;
  bottom: 0.42rem;
  height: 0.26rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
}

.lobby-card-meter i {
  position: absolute;
  left: 0.6rem;
  bottom: 0.42rem;
  z-index: 1;
  height: 0.26rem;
  border-radius: 999px;
  background: linear-gradient(90deg, #14b8a6, #2563eb);
}

.lobby-actions-simple {
  justify-content: flex-end;
}

@media (max-width: 920px) {
  .lobbies-controls {
    justify-content: flex-start;
  }

  .lobby-actions-simple {
    justify-content: flex-start;
  }

  .lobbies-head-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .lobbies-head-stats {
    grid-template-columns: 1fr;
  }
}
</style>
