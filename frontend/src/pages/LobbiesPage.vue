<template>
  <section class="agp-grid lobbies-page-simple">
    <header class="agp-card p-4 lobbies-simple-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between align-items-start gap-3">
        <div>
          <h1 class="h3 mb-1">Лобби</h1>
          <p class="text-muted mb-0">Только список доступных лобби с фильтрацией по играм.</p>
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
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <section class="agp-grid">
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
        <div class="d-flex justify-content-between gap-3 align-items-start">
          <div class="lobby-main">
            <div class="d-flex gap-2 flex-wrap mb-2">
              <span class="agp-pill" :class="statusClass(lobby.status)">{{ statusLabel(lobby.status) }}</span>
            </div>
            <h2 class="h5 mb-1">{{ lobby.title }}</h2>
            <p class="small text-muted mb-0">{{ gameTitle(lobby.game_id) }}</p>
            <div class="small text-muted mt-2">
              Команд: <span class="mono">{{ lobby.teams.length }}</span> / <span class="mono">{{ lobby.max_teams }}</span>
            </div>
          </div>
          <div class="agp-lobby-actions lobby-actions-simple">
            <button
              class="btn btn-dark"
              :disabled="!canEnterLobby(lobby) || busyLobbyId === lobby.lobby_id"
              @click="enterLobby(lobby)"
            >
              {{ enterButtonText(lobby) }}
            </button>
            <RouterLink class="btn btn-outline-secondary" :to="`/lobbies/${lobby.lobby_id}`">
              Открыть
            </RouterLink>
            <RouterLink
              v-if="lobby.last_scheduled_run_ids.length > 0"
              class="btn btn-outline-secondary"
              :to="`/runs/${lobby.last_scheduled_run_ids[0]}/watch`"
            >
              Смотреть
            </RouterLink>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import {
  createTeam,
  joinLobby,
  listGames,
  listLobbies,
  listTeamsByGame,
  type GameDto,
  type LobbyDto,
  type LobbyStatus,
  type StreamEnvelopeDto,
} from '../lib/api';
import { loadTeamMapping, saveTeamMapping } from '../lib/teamMapping';
import { useSessionStore } from '../stores/session';

const router = useRouter();
const sessionStore = useSessionStore();

const isLoading = ref(false);
const busyLobbyId = ref('');
const errorMessage = ref('');
const games = ref<GameDto[]>([]);
const lobbies = ref<LobbyDto[]>([]);
const selectedGameId = ref('');
let lobbiesEventSource: EventSource | null = null;
let lobbiesPollingHandle: ReturnType<typeof setInterval> | null = null;

const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const lobbyGames = computed(() =>
  games.value
    .filter((game) => game.mode !== 'single_task')
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

function rememberTeam(gameId: string, teamId: string): void {
  saveTeamMapping(gameId, sessionStore.nickname, teamId);
}

function knownTeamForLobby(lobby: LobbyDto): string {
  return loadTeamMapping(lobby.game_id, sessionStore.nickname);
}

function canEnterLobby(lobby: LobbyDto): boolean {
  if (lobby.status === 'closed' || lobby.status === 'updating') return false;
  if (lobby.status === 'running') return lobby.last_scheduled_run_ids.length > 0;
  return lobby.teams.length < lobby.max_teams || Boolean(knownTeamForLobby(lobby));
}

function enterButtonText(lobby: LobbyDto): string {
  if (busyLobbyId.value === lobby.lobby_id) return 'Входим...';
  if (lobby.status === 'running') return 'Смотреть игру';
  if (knownTeamForLobby(lobby)) return 'Вернуться';
  return 'Войти';
}

async function ensureTeamForLobby(lobby: LobbyDto): Promise<string> {
  const mapped = knownTeamForLobby(lobby);
  const teams = await listTeamsByGame(lobby.game_id);
  if (mapped && teams.some((team) => team.team_id === mapped && team.captain_user_id === sessionStore.nickname)) {
    return mapped;
  }

  const existing = teams.find((team) => team.captain_user_id === sessionStore.nickname);
  if (existing) {
    rememberTeam(lobby.game_id, existing.team_id);
    return existing.team_id;
  }

  const created = await createTeam({
    game_id: lobby.game_id,
    name: `${sessionStore.nickname} / ${gameTitle(lobby.game_id)}`,
    captain_user_id: sessionStore.nickname,
  });
  rememberTeam(lobby.game_id, created.team_id);
  return created.team_id;
}

async function enterLobby(lobby: LobbyDto): Promise<void> {
  if (!canEnterLobby(lobby)) return;
  busyLobbyId.value = lobby.lobby_id;
  errorMessage.value = '';
  try {
    if (lobby.status === 'running' && lobby.last_scheduled_run_ids[0]) {
      await router.push(`/runs/${lobby.last_scheduled_run_ids[0]}/watch`);
      return;
    }

    const teamId = await ensureTeamForLobby(lobby);
    if (!lobby.teams.some((team) => team.team_id === teamId)) {
      await joinLobby({
        lobby_id: lobby.lobby_id,
        team_id: teamId,
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

  const source = new EventSource('/api/v1/lobbies/stream?poll_interval_ms=1000');
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

.lobby-card-simple {
  gap: 0.6rem;
}

.lobby-main {
  min-width: 0;
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
