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

    <article class="agp-card p-3 lobby-create-card">
      <h2 class="h6 mb-2">Параметры лобби</h2>
      <div v-if="!canManage" class="small text-warning-emphasis mb-3">
        Создание лобби доступно только преподавателю или администратору.
      </div>
      <div v-else-if="!isLoading && lobbyGames.length === 0" class="small text-warning-emphasis mb-3">
        Нет опубликованных игр для лобби. Сначала подключите игру и опубликуйте ее в каталоге.
      </div>

      <div class="lobby-create-form">
        <div class="lobby-create-field lobby-create-field--game">
          <label class="form-label small">Игра</label>
          <select v-model="form.game_id" class="form-select" :disabled="!canManage || isCreating">
            <option value="">Выберите игру</option>
            <option v-for="game in lobbyGames" :key="game.game_id" :value="game.game_id">{{ game.title }}</option>
          </select>
        </div>

        <div class="lobby-create-field lobby-create-field--title">
          <label class="form-label small">Название лобби</label>
          <input
            v-model.trim="form.title"
            class="form-control"
            placeholder="Например: Тренировка 8А / Графы"
            :disabled="!canManage || isCreating"
            @input="titleTouched = true"
          />
        </div>

        <div class="lobby-create-field">
          <label class="form-label small">Доступ</label>
          <select v-model="form.access" class="form-select" :disabled="!canManage || isCreating">
            <option value="public">Открытое</option>
            <option value="code">По коду</option>
          </select>
        </div>

        <div class="lobby-create-field">
          <label class="form-label small">Лимит игроков</label>
          <input
            v-model.number="form.max_teams"
            type="number"
            min="2"
            max="512"
            class="form-control mono"
            :disabled="!canManage || isCreating"
          />
          <div class="form-text">{{ playerLimitHint }}</div>
        </div>

        <div v-if="form.access === 'code'" class="lobby-create-field lobby-create-field--code">
          <label class="form-label small">Код входа</label>
          <div class="input-group input-group-sm">
            <input
              v-model.trim="form.access_code"
              class="form-control mono"
              placeholder="например CLASS-2026"
              :disabled="!canManage || isCreating"
            />
            <button
              class="btn btn-outline-secondary"
              type="button"
              :disabled="!canManage || isCreating"
              @click="generateAccessCode"
            >
              Сгенерировать
            </button>
          </div>
        </div>
      </div>

      <section v-if="selectedGame" class="lobby-game-summary mt-3">
        <div>
          <div class="small text-muted">Выбранная игра</div>
          <strong>{{ selectedGame.title }}</strong>
          <p class="small text-muted mb-0">{{ selectedGame.description || 'Описание игры пока не заполнено.' }}</p>
        </div>
        <div class="lobby-game-summary-meta">
          <span class="agp-pill agp-pill--neutral">{{ modeLabel(selectedGame.mode) }}</span>
          <span class="agp-pill agp-pill--neutral">{{ matchFlowLabel(selectedGame.mode) }}</span>
          <span class="agp-pill agp-pill--neutral">ролей: {{ selectedRequiredSlots.length || 'нет данных' }}</span>
          <span v-if="selectedGame.difficulty" class="agp-pill agp-pill--neutral">{{ difficultyLabel(selectedGame.difficulty) }}</span>
        </div>
      </section>

      <div class="mt-3 lobby-create-actions">
        <button class="btn btn-dark" :disabled="!canCreate" @click="createNewLobby">
          {{ isCreating ? 'Создание...' : 'Создать лобби' }}
        </button>
        <RouterLink class="btn btn-outline-secondary" to="/lobbies">Отмена</RouterLink>
        <span class="small text-muted">{{ createHint }}</span>
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
const titleTouched = ref(false);

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
const selectedGame = computed(() => lobbyGames.value.find((game) => game.game_id === form.game_id) ?? null);
const selectedRequiredSlots = computed(
  () =>
    selectedGame.value?.versions.find((version) => version.version_id === selectedGame.value?.active_version_id)
      ?.required_slot_keys ?? [],
);
const defaultLobbyTitle = computed(() => (selectedGame.value ? `Лобби / ${selectedGame.value.title}` : ''));
const playerLimitHint = computed(() => {
  if (!selectedGame.value) return 'Сколько учеников сможет участвовать в этом лобби.';
  if (selectedGame.value.mode === 'massive_lobby') {
    return 'В большой игре все готовые игроки попадают в ближайший матч.';
  }
  return 'В маленькой игре лишние готовые игроки ждут очередь.';
});

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
const createHint = computed(() => {
  if (!canManage.value) return 'Создавать лобби может только преподаватель или администратор.';
  if (isCreating.value) return 'Создаем лобби...';
  if (!lobbyGames.value.length) return 'Нет доступных игр для лобби.';
  if (!form.game_id) return 'Выберите игру для лобби.';
  if (!form.title.trim()) return 'Добавьте понятное название для учеников.';
  if (!Number.isFinite(form.max_teams) || form.max_teams < 2 || form.max_teams > 512) return 'Укажите от 2 до 512 игроков.';
  if (form.access === 'code' && !form.access_code.trim()) return 'Для закрытого лобби нужен код входа.';
  return form.access === 'code' ? 'Ученики смогут войти только по коду.' : 'Лобби будет видно всем ученикам.';
});

function applyDefaultTitle(): void {
  if (!titleTouched.value) {
    form.title = defaultLobbyTitle.value;
  }
}

function modeLabel(mode: GameDto['mode']): string {
  if (mode === 'small_match') return 'малое лобби';
  if (mode === 'massive_lobby') return 'большое лобби';
  return 'лобби';
}

function matchFlowLabel(mode: GameDto['mode']): string {
  if (mode === 'massive_lobby') return 'все готовые играют';
  return 'есть очередь';
}

function difficultyLabel(difficulty: GameDto['difficulty']): string {
  if (difficulty === 'easy') return 'легкая';
  if (difficulty === 'medium') return 'средняя';
  if (difficulty === 'hard') return 'сложная';
  return difficulty ?? '';
}

function generateAccessCode(): void {
  const titlePrefix = selectedGame.value?.slug?.slice(0, 4).toUpperCase() || 'GAME';
  const suffix = Math.random().toString(36).slice(2, 6).toUpperCase();
  form.access_code = `${titlePrefix}-${suffix}`;
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
  () => {
    applyDefaultTitle();
  },
);

watch(
  () => form.access,
  (access) => {
    if (access === 'code' && !form.access_code.trim()) {
      generateAccessCode();
    }
  },
);

async function loadData(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    games.value = await listGames();
    applyDefaultGameSelection();
    applyDefaultTitle();
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

<style scoped>
.lobby-create-card {
  display: grid;
  gap: 0.25rem;
}

.lobby-create-form {
  display: grid;
  grid-template-columns: minmax(16rem, 1.2fr) minmax(18rem, 1.8fr) minmax(9rem, 0.7fr) minmax(10rem, 0.8fr);
  gap: 0.75rem;
  align-items: start;
}

.lobby-create-field {
  min-width: 0;
}

.lobby-create-field .form-label {
  min-height: 1.1rem;
}

.lobby-create-field--game,
.lobby-create-field--title {
  grid-row: 1;
}

.lobby-create-field--code {
  grid-column: 3 / 5;
}

.lobby-game-summary {
  display: flex;
  justify-content: space-between;
  gap: 0.9rem;
  align-items: flex-start;
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: 0.55rem;
  background: #f0fdfa;
  padding: 0.75rem;
}

.lobby-game-summary-meta,
.lobby-create-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}

.lobby-game-summary-meta {
  justify-content: flex-end;
}

@media (max-width: 760px) {
  .lobby-create-form {
    grid-template-columns: 1fr;
  }

  .lobby-create-field--game,
  .lobby-create-field--title,
  .lobby-create-field--code {
    grid-column: auto;
    grid-row: auto;
  }

  .lobby-game-summary {
    display: grid;
  }

  .lobby-game-summary-meta {
    justify-content: flex-start;
  }
}
</style>
