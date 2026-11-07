<template>
  <section class="agp-grid lobbies-page-simple">
    <header class="agp-page-heading lobbies-simple-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between align-items-start gap-3">
        <div>
          <p class="lobbies-kicker mb-1">Матчи и соревнования</p>
          <h1 class="h3 mb-1">{{ canManage ? 'Занятия и лобби' : 'Лобби' }}</h1>
          <p class="text-muted mb-0">
            {{ canManage ? 'Создайте лобби, пригласите участников и запустите тренировку или соревнование.' : 'Войдите в лобби, подготовьте код и нажмите «Готов играть».' }}
          </p>
        </div>
        <div class="lobbies-controls">
          <div class="lobbies-filter-wrap">
            <label class="form-label small mb-1" for="lobby-game-filter">Игра</label>
            <select id="lobby-game-filter" v-model="selectedGameId" class="form-select">
              <option value="">Все игры</option>
              <option v-for="game in lobbyGames" :key="game.game_id" :value="game.game_id">
                {{ game.title }}
              </option>
            </select>
          </div>
          <RouterLink
            v-if="canManage"
            class="btn btn-primary lobbies-create-btn"
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
      <LoadingSkeleton v-if="isLoading && lobbies.length === 0" class="lobbies-empty-card" :count="4" label="Загрузка лобби…" />
      <article v-else-if="filteredLobbies.length === 0" class="agp-card p-4">
        <div class="agp-empty-state">
          <div>
            <h2 class="h6 mb-1">{{ selectedGameId ? 'Лобби по выбранной игре не найдены' : 'Лобби пока нет' }}</h2>
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
              class="btn btn-primary"
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
import { statusPillClass } from '../lib/statusTone';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

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
const route = useRoute();
const sessionStore = useSessionStore();

const isLoading = ref(false);
const busyLobbyId = ref('');
const errorMessage = ref('');
const games = ref<GameDto[]>([]);
const lobbies = ref<LobbyDto[]>([]);
const selectedGameId = ref(typeof route.query.game_id === 'string' ? route.query.game_id : '');
watch(selectedGameId, (gameId) => { void router.replace({ query: { ...route.query, game_id: gameId || undefined } }); });
watch(() => route.query.game_id, (gameId) => { selectedGameId.value = typeof gameId === 'string' ? gameId : ''; });
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
  return statusPillClass(status);
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
  if (canManage.value && !lobby.my_team_id) return 'Управлять';
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
