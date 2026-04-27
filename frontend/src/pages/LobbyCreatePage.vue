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
      <div class="lc-head-stats">
        <div>
          <span>Игр</span>
          <strong class="mono">{{ lobbyGames.length }}</strong>
        </div>
        <div>
          <span>Доступ</span>
          <strong>{{ accessLabel }}</strong>
        </div>
        <div>
          <span>Лимит</span>
          <strong class="mono">{{ form.max_teams }}</strong>
        </div>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <div v-if="!canManage" class="agp-card p-3">
      <div class="agp-empty-state agp-empty-state--compact">Создание лобби доступно только преподавателю или администратору.</div>
    </div>
    <div v-else-if="!isLoading && lobbyGames.length === 0" class="agp-card p-3">
      <div class="agp-empty-state agp-empty-state--compact">Нет опубликованных игр для лобби. Сначала подключите игру и опубликуйте ее в каталоге.</div>
    </div>
    <div v-else-if="isLoading" class="agp-card p-3">
      <div class="agp-loading-state agp-loading-state--compact">Загрузка игр...</div>
    </div>

    <div
      v-if="canManage && !isLoading && lobbyGames.length > 0"
      class="lc-body"
      :class="{ 'lc-body--single': !selectedGame }"
    >
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
              <div class="lc-access-toggle">
                <button
                  type="button"
                  :class="{ active: form.access === 'public' }"
                  :disabled="!canManage || isCreating"
                  @click="setAccess('public')"
                >
                  <strong>Открытое</strong>
                  <span>видно всем</span>
                </button>
                <button
                  type="button"
                  :class="{ active: form.access === 'code' }"
                  :disabled="!canManage || isCreating"
                  @click="setAccess('code')"
                >
                  <strong>По коду</strong>
                  <span>для класса</span>
                </button>
              </div>
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
          <button class="btn btn-primary" :disabled="!canCreate" @click="createNewLobby">
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
          <span class="agp-pill agp-pill--neutral">{{ matchFlowLabel(selectedGame) }}</span>
          <span class="agp-pill agp-pill--neutral">ролей: {{ selectedRequiredSlots.length || 'нет данных' }}</span>
          <span v-if="selectedGame.difficulty" class="agp-pill agp-pill--neutral">{{ difficultyLabel(selectedGame.difficulty) }}</span>
          <span v-if="selectedGame.learning_section" class="agp-pill agp-pill--primary">{{ selectedGame.learning_section }}</span>
        </div>
        <div v-if="selectedRequiredSlots.length" class="lc-role-preview">
          <span>Роли для кода</span>
          <div>
            <strong v-for="slot in selectedRequiredSlots" :key="slot">{{ slot }}</strong>
          </div>
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
const accessLabel = computed(() => (form.access === 'code' ? 'по коду' : 'открыто'));
const playerLimitHint = computed(() => {
  if (!selectedGame.value) return 'Сколько учеников сможет участвовать в этом лобби.';
  return `Матчи стартуют от ${selectedGame.value.min_players_per_match ?? 2} игроков, максимум ${selectedGame.value.max_players_per_match ?? 2}.`;
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
  if (mode === 'multiplayer' || mode === 'small_match' || mode === 'massive_lobby') return 'мультиплеер';
  return 'лобби';
}

function matchFlowLabel(game: GameDto): string {
  return `матч ${game.min_players_per_match ?? 2}-${game.max_players_per_match ?? 2}`;
}

function difficultyLabel(difficulty: GameDto['difficulty']): string {
  if (difficulty === 'easy') return 'легкая';
  if (difficulty === 'medium') return 'средняя';
  if (difficulty === 'hard') return 'сложная';
  return difficulty ?? '';
}

function setAccess(access: LobbyAccess): void {
  form.access = access;
  if (access === 'code' && !form.access_code.trim()) {
    generateAccessCode();
  }
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
  position: relative;
  overflow: hidden;
  background:
    url("data:image/svg+xml,%3Csvg width='176' height='104' viewBox='0 0 176 104' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.12' stroke-width='2'%3E%3Cpath d='M18 18h28v28H18zM130 18h28v28h-28zM74 58h28v28H74z'/%3E%3Cpath d='M46 32h28M102 72h28M88 0v24M88 80v24'/%3E%3C/g%3E%3C/svg%3E") right 1rem top 0.8rem / 14rem auto no-repeat,
    linear-gradient(135deg, rgba(255, 255, 255, 0.97), rgba(240, 253, 250, 0.94)),
    url("data:image/svg+xml,%3Csvg width='96' height='48' viewBox='0 0 96 48' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.07'%3E%3Cpath d='M0 24h96M24 0v48M72 0v48'/%3E%3C/g%3E%3C/svg%3E");
}

.lc-head::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.22rem;
  background: linear-gradient(90deg, #14b8a6, #2563eb, #f59e0b);
}

.lc-head-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
  margin-top: 1rem;
}

.lc-head-stats > div {
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

.lc-head-stats span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lc-head-stats strong {
  color: var(--agp-text);
  font-size: 0.92rem;
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

.lc-body--single {
  grid-template-columns: minmax(0, 1fr);
}

.lc-form-card {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 1.25rem;
}

.lc-form-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.18rem;
  background: linear-gradient(90deg, #14b8a6, #2563eb, #f59e0b);
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

.lc-field .form-label {
  color: var(--agp-text);
}

.lc-access-toggle {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.45rem;
}

.lc-access-toggle button {
  border: 1px solid rgba(148, 163, 184, 0.38);
  border-radius: 0.58rem;
  display: grid;
  gap: 0.08rem;
  min-height: 4.35rem;
  align-content: center;
  padding: 0.55rem 0.65rem;
  background: rgba(255, 255, 255, 0.78);
  color: var(--agp-text);
  text-align: left;
}

.lc-access-toggle button:disabled {
  opacity: 0.55;
}

.lc-access-toggle strong {
  font-size: 0.92rem;
}

.lc-access-toggle span {
  color: var(--agp-text-muted);
  font-size: 0.75rem;
}

.lc-access-toggle button.active {
  border-color: rgba(20, 184, 166, 0.62);
  background:
    url("data:image/svg+xml,%3Csvg width='58' height='40' viewBox='0 0 58 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2314b8a6' stroke-opacity='.2'%3E%3Cpath d='M8 8h12v12H8zM38 8h12v12H38zM23 20h12v12H23z'/%3E%3C/g%3E%3C/svg%3E") right 0.35rem center / 3.6rem auto no-repeat,
    linear-gradient(135deg, #dff7f4, #dbeafe);
  box-shadow: 0 10px 24px rgba(20, 184, 166, 0.12);
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
  overflow: hidden;
  border-left: 0;
  background:
    url("data:image/svg+xml,%3Csvg width='120' height='90' viewBox='0 0 120 90' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%232563eb' stroke-opacity='.12'%3E%3Cpath d='M16 16h24v24H16zM80 16h24v24H80zM48 50h24v24H48z'/%3E%3C/g%3E%3C/svg%3E") right 0.7rem bottom 0.7rem / 8rem auto no-repeat,
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.94));
}

.lc-preview::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.22rem;
  background: linear-gradient(90deg, #2563eb, #14b8a6);
}

.lc-preview-pills {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.lc-role-preview {
  display: grid;
  gap: 0.45rem;
  margin-top: 1rem;
}

.lc-role-preview > span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
}

.lc-role-preview > div {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.lc-role-preview strong {
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: 999px;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  padding: 0.25rem 0.58rem;
  font-size: 0.78rem;
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

  .lc-head-stats,
  .lc-access-toggle {
    grid-template-columns: 1fr;
  }

  .lc-hint {
    margin-left: 0;
    width: 100%;
  }
}
</style>
