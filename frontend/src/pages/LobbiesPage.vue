<template>
  <section class="agp-grid lobbies-page-simple">
    <header class="agp-card p-4 lobbies-simple-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between align-items-start gap-3">
        <div>
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

      <div class="mt-3 small text-muted">
        Показано: <span class="mono">{{ filteredLobbies.length }}</span>
        из <span class="mono">{{ sortedLobbies.length }}</span>
      </div>
      <div v-if="selectedGameId" class="lobbies-active-filter mt-2">
        <span>Фильтр:</span>
        <strong>{{ selectedGameTitle }}</strong>
        <button class="btn btn-sm btn-link p-0" type="button" @click="selectedGameId = ''">сбросить</button>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <section class="lobbies-card-grid">
      <article v-if="isLoading && lobbies.length === 0" class="agp-card p-4 text-muted">Загрузка лобби...</article>
      <article v-else-if="filteredLobbies.length === 0" class="agp-card p-4">
        <h2 class="h6 mb-1">{{ selectedGameId ? 'Лобби по выбранной игре не найдены' : 'Открытых лобби пока нет' }}</h2>
        <p class="small text-muted mb-0">
          {{ selectedGameId ? 'Смените игру в фильтре или выберите "Все игры".' : 'Когда преподаватель создаст лобби, оно появится здесь.' }}
        </p>
      </article>

      <article
        v-for="lobby in filteredLobbies"
        :key="lobby.lobby_id"
        class="agp-card agp-lobby-card p-3 lobby-card-simple"
      >
        <div class="lobby-card-content">
          <div class="lobby-main">
            <div class="d-flex gap-2 flex-wrap mb-2">
              <span class="agp-pill" :class="statusClass(lobby.status)">{{ statusLabel(lobby.status) }}</span>
              <span v-if="lobby.access === 'code'" class="agp-pill agp-pill--neutral">по коду</span>
            </div>
            <h2 class="h5 mb-1">{{ lobby.title }}</h2>
            <p class="small text-muted mb-0">{{ gameTitle(lobby.game_id) }}</p>
            <div class="small text-muted mt-2">
              Игроки: <span class="mono">{{ lobbyPlayersLabel(lobby) }}</span>
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
    updating: 4,
    closed: 5,
  };
  return [...lobbies.value].sort((a, b) => weight[a.status] - weight[b.status] || a.title.localeCompare(b.title));
});
const filteredLobbies = computed(() => {
  if (!selectedGameId.value) return sortedLobbies.value;
  return sortedLobbies.value.filter((lobby) => lobby.game_id === selectedGameId.value);
});
const selectedGameTitle = computed(() => selectedGameId.value ? gameTitle(selectedGameId.value) : '');

function statusLabel(status: LobbyStatus): string {
  const labels: Record<LobbyStatus, string> = {
    draft: 'готовится',
    open: 'открыто',
    running: 'игра идет',
    paused: 'пауза',
    updating: 'обновляется',
    closed: 'закрыто',
  };
  return labels[status];
}

function statusClass(status: LobbyStatus): string {
  if (status === 'open' || status === 'draft') return 'agp-pill--primary';
  if (status === 'running') return 'agp-pill--warning';
  if (status === 'closed') return 'agp-pill--danger';
  return 'agp-pill--neutral';
}

function gameTitle(gameId: string): string {
  return games.value.find((game) => game.game_id === gameId)?.title ?? gameId;
}

function isLobbyCatalogGame(game: GameDto): boolean {
  return game.mode !== 'single_task' && game.catalog_metadata_status === 'ready';
}

function canEnterLobby(lobby: LobbyDto): boolean {
  if (lobby.status === 'closed' || lobby.status === 'updating') return false;
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

  const source = new EventSource(
    `/api/v1/lobbies/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`
  );
  lobbiesEventSource = source;

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

  source.onerror = () => {
    stopLobbiesLiveUpdates();
    startLobbiesPolling();
  };
}

function startLobbiesPolling(): void {
  stopLobbiesPolling();
  lobbiesPollingHandle = setInterval(async () => {
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
  lobbiesEventSource.close();
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
  background: #f8fafc;
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

.lobbies-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 18rem), 18rem));
  gap: 0.75rem;
  justify-content: start;
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
  gap: 0.45rem;
  align-content: start;
  min-height: 13.25rem;
}

.lobby-card-simple h2 {
  font-size: 1rem;
}

.lobby-card-content {
  display: grid;
  gap: 0.75rem;
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
}
</style>
