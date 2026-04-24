<template>
  <section class="agp-grid">
    <header class="d-flex justify-content-between align-items-start gap-3 flex-wrap">
      <div>
        <RouterLink to="/lobbies" class="small text-decoration-none">← К списку лобби</RouterLink>
        <h1 class="h3 mb-1 mt-2">Создать лобби</h1>
        <p class="text-muted mb-0">Выберите игру и настройте параметры лобби перед запуском.</p>
      </div>
      <button class="btn btn-sm btn-outline-secondary" :disabled="isLoading" @click="loadData">
        {{ isLoading ? 'Обновление...' : 'Обновить игры' }}
      </button>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <article class="agp-card p-3">
      <h2 class="h6 mb-2">Параметры лобби</h2>
      <div v-if="!canManage" class="small text-warning-emphasis mb-3">
        Создание лобби доступно только пользователям с ролью teacher/admin.
      </div>

      <div class="row g-2 align-items-end">
        <div class="col-md-5">
          <label class="form-label small">Игра</label>
          <select v-model="form.game_id" class="form-select" :disabled="!canManage || isCreating">
            <option value="">Выберите игру</option>
            <option v-for="game in lobbyGames" :key="game.game_id" :value="game.game_id">{{ game.title }}</option>
          </select>
        </div>

        <div class="col-md-7">
          <label class="form-label small">Название лобби</label>
          <input
            v-model.trim="form.title"
            class="form-control"
            placeholder="Например: Тренировка 8А / Графы"
            :disabled="!canManage || isCreating"
          />
        </div>

        <div class="col-md-3">
          <label class="form-label small">Доступ</label>
          <select v-model="form.access" class="form-select" :disabled="!canManage || isCreating">
            <option value="public">Открытое</option>
            <option value="code">По коду</option>
          </select>
        </div>

        <div class="col-md-3">
          <label class="form-label small">Игроков до</label>
          <input
            v-model.number="form.max_teams"
            type="number"
            min="2"
            max="512"
            class="form-control mono"
            :disabled="!canManage || isCreating"
          />
        </div>

        <div v-if="form.access === 'code'" class="col-md-4">
          <label class="form-label small">Код входа</label>
          <input
            v-model.trim="form.access_code"
            class="form-control mono"
            placeholder="например CLASS-2026"
            :disabled="!canManage || isCreating"
          />
        </div>
      </div>

      <div class="mt-3 d-flex gap-2 flex-wrap">
        <button class="btn btn-dark" :disabled="!canCreate" @click="createNewLobby">
          {{ isCreating ? 'Создание...' : 'Создать лобби' }}
        </button>
        <RouterLink class="btn btn-outline-secondary" to="/lobbies">Отмена</RouterLink>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import {
  createLobby,
  listGames,
  type GameDto,
  type LobbyAccess,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();

const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const isLoading = ref(false);
const isCreating = ref(false);
const errorMessage = ref('');
const games = ref<GameDto[]>([]);

const form = reactive({
  game_id: '',
  title: '',
  access: 'public' as LobbyAccess,
  access_code: '',
  max_teams: 16,
});

const lobbyGames = computed(() =>
  games.value
    .filter((game) => isLobbyCatalogGame(game))
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title))
);

function isLobbyCatalogGame(game: GameDto): boolean {
  return game.mode !== 'single_task' && game.catalog_metadata_status === 'ready';
}

const canCreate = computed(() => {
  if (!canManage.value || isCreating.value) return false;
  if (!form.game_id || !form.title.trim()) return false;
  if (!Number.isFinite(form.max_teams) || form.max_teams < 2 || form.max_teams > 512) return false;
  if (form.access === 'code' && !form.access_code.trim()) return false;
  return true;
});

function gameTitle(gameId: string): string {
  return games.value.find((game) => game.game_id === gameId)?.title ?? '';
}

function applyDefaultGameSelection(): void {
  const requestedGameId = typeof route.query.game_id === 'string' ? route.query.game_id : '';
  if (requestedGameId && lobbyGames.value.some((game) => game.game_id === requestedGameId)) {
    form.game_id = requestedGameId;
    return;
  }
  if (!form.game_id && lobbyGames.value[0]) {
    form.game_id = lobbyGames.value[0].game_id;
  }
}

watch(
  () => form.game_id,
  (gameId) => {
    if (!form.title.trim() && gameId) {
      form.title = `Лобби / ${gameTitle(gameId)}`;
    }
  },
);

async function loadData(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    games.value = await listGames();
    applyDefaultGameSelection();
    if (!form.title.trim() && form.game_id) {
      form.title = `Лобби / ${gameTitle(form.game_id)}`;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить список игр';
  } finally {
    isLoading.value = false;
  }
}

async function createNewLobby(): Promise<void> {
  if (!canCreate.value) return;
  isCreating.value = true;
  errorMessage.value = '';
  try {
    const created = await createLobby({
      game_id: form.game_id,
      title: form.title.trim(),
      kind: 'training',
      access: form.access,
      access_code: form.access === 'code' ? form.access_code.trim() : null,
      max_teams: form.max_teams,
    });
    await router.push(`/lobbies/${created.lobby_id}`);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось создать лобби';
  } finally {
    isCreating.value = false;
  }
}

onMounted(async () => {
  await loadData();
});
</script>
