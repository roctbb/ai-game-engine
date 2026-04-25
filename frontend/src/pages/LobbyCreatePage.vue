<template>
  <section class="agp-grid lc-page">
    <header class="agp-card p-4 lc-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between align-items-start gap-3">
        <div>
          <RouterLink to="/lobbies" class="lc-back-link">← К списку лобби</RouterLink>
          <p class="lc-kicker">Новое лобби</p>
          <h1 class="h3 mb-1">Создать лобби</h1>
          <p class="text-muted mb-0">Выберите игру и настройте параметры перед запуском.</p>
        </div>
        <button class="btn btn-sm btn-outline-secondary" :disabled="isLoading" @click="loadData">
          {{ isLoading ? 'Обновление...' : 'Обновить игры' }}
        </button>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <div v-if="!canManage" class="agp-card p-3">
      <div class="small text-warning-emphasis">Создание лобби доступно только преподавателю или администратору.</div>
    </div>
    <div v-else-if="!isLoading && lobbyGames.length === 0" class="agp-card p-3">
      <div class="small text-warning-emphasis">Нет опубликованных игр для лобби. Сначала подключите игру и опубликуйте ее в каталоге.</div>
    </div>

    <div v-if="canManage" class="lc-body">
      <article class="agp-card p-4 lc-form-card">
        <div class="lc-steps">
          <div class="agp-task-step" :class="{ 'agp-task-step--active': !form.game_id, 'agp-task-step--done': !!form.game_id }">
            <strong>1</strong><span>Игра</span>
          </div>
          <div class="agp-task-step" :class="{ 'agp-task-step--active': !!form.game_id && !form.title.trim(), 'agp-task-step--done': !!form.game_id && !!form.title.trim() }">
            <strong>2</strong><span>Настройки</span>
          </div>
          <div class="agp-task-step" :class="{ 'agp-task-step--active': canCreate }">
            <strong>3</strong><span>Запуск</span>
          </div>
        </div>

        <div class="lc-fields">
          <div class="lc-field">
            <label class="form-label small fw-bold">Игра</label>
            <select v-model="form.game_id" class="form-select" :disabled="!canManage || isCreating">
              <option value="">Выберите игру</option>
              <option v-for="game in lobbyGames" :key="game.game_id" :value="game.game_id">{{ game.title }}</option>
            </select>
          </div>

          <div class="lc-field">
            <label class="form-label small fw-bold">Название лобби</label>
            <input
              v-model.trim="form.title"
              class="form-control"
              placeholder="Например: Тренировка 8А / Графы"
              :disabled="!canManage || isCreating"
              @input="titleTouched = true"
            />
          </div>

          <div class="lc-field-row">
            <div class="lc-field">
              <label class="form-label small fw-bold">Доступ</label>
              <select v-model="form.access" class="form-select" :disabled="!canManage || isCreating">
                <option value="public">Открытое</option>
                <option value="code">По коду</option>
              </select>
            </div>

            <div class="lc-field">
              <label class="form-label small fw-bold">Лимит игроков</label>
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
          </div>

          <div v-if="form.access === 'code'" class="lc-field">
            <label class="form-label small fw-bold">Код входа</label>
            <div class="input-group">
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

        <div class="lc-actions">
          <button class="btn btn-dark" :disabled="!canCreate" @click="createNewLobby">
            {{ isCreating ? 'Создание...' : 'Создать лобби' }}
          </button>
          <RouterLink class="btn btn-outline-secondary" to="/lobbies">Отмена</RouterLink>
          <span class="small text-muted lc-hint">{{ createHint }}</span>
        </div>
      </article>

      <aside v-if="selectedGame" class="agp-card p-4 lc-preview">
        <p class="lc-kicker mb-2">Выбранная игра</p>
        <h2 class="h5 mb-1">{{ selectedGame.title }}</h2>
        <p class="small text-muted mb-3">{{ selectedGame.description || 'Описание игры пока не заполнено.' }}</p>
        <div class="lc-preview-pills">
          <span class="agp-pill agp-pill--neutral">{{ modeLabel(selectedGame.mode) }}</span>
          <span class="agp-pill agp-pill--neutral">{{ matchFlowLabel(selectedGame.mode) }}</span>
          <span class="agp-pill agp-pill--neutral">ролей: {{ selectedRequiredSlots.length || 'нет данных' }}</span>
          <span v-if="selectedGame.difficulty" class="agp-pill agp-pill--neutral">{{ difficultyLabel(selectedGame.difficulty) }}</span>
          <span v-if="selectedGame.learning_section" class="agp-pill agp-pill--primary">{{ selectedGame.learning_section }}</span>
        </div>
      </aside>
    </div>
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
.lc-page {
  max-width: 64rem;
}

.lc-head {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.97), rgba(240, 253, 250, 0.94)),
    url("data:image/svg+xml,%3Csvg width='96' height='48' viewBox='0 0 96 48' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.07'%3E%3Cpath d='M0 24h96M24 0v48M72 0v48'/%3E%3C/g%3E%3C/svg%3E");
}

.lc-kicker {
  margin: 0 0 0.25rem;
  color: var(--agp-primary);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.lc-back-link {
  display: inline-block;
  margin-bottom: 0.55rem;
  color: var(--agp-text-muted);
  font-size: 0.82rem;
  font-weight: 700;
  text-decoration: none;
}

.lc-back-link:hover {
  color: var(--agp-primary);
}

.lc-body {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(16rem, 0.6fr);
  gap: 1rem;
  align-items: start;
}

.lc-form-card {
  display: grid;
  gap: 1.25rem;
}

.lc-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.6rem;
}

.lc-fields {
  display: grid;
  gap: 0.85rem;
}

.lc-field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
}

.lc-field {
  min-width: 0;
}

.lc-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
  padding-top: 0.5rem;
  border-top: 1px solid var(--agp-border);
}

.lc-hint {
  margin-left: auto;
}

.lc-preview {
  position: sticky;
  top: 4.5rem;
  border-left: 3px solid var(--agp-primary);
}

.lc-preview-pills {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

@media (max-width: 860px) {
  .lc-body {
    grid-template-columns: 1fr;
  }

  .lc-preview {
    position: static;
  }

  .lc-field-row {
    grid-template-columns: 1fr;
  }

  .lc-steps {
    grid-template-columns: 1fr;
  }

  .lc-hint {
    margin-left: 0;
    width: 100%;
  }
}
</style>
