<template>
  <section class="agp-grid lc-page">
    <header class="lc-head"><div><RouterLink to="/lobbies" class="lc-back-link">← К лобби</RouterLink><h1>Создать лобби</h1></div><button class="btn btn-outline-secondary" :disabled="isLoading" @click="loadData">Обновить игры</button></header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <div v-if="!canManage" class="agp-card p-3">
      <div class="agp-empty-state agp-empty-state--compact">Создание лобби доступно только преподавателю или администратору.</div>
    </div>
    <div v-else-if="!isLoading && lobbyGames.length === 0" class="agp-card p-3">
      <div class="agp-empty-state agp-empty-state--compact">Игры для лобби пока не подключены.</div>
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
        <div class="lc-fields">
          <div class="lc-field">
            <label class="form-label small">Игра</label>
            <select v-model="form.game_id" class="form-select" :disabled="!canManage || isCreating">
              <option value="">Выберите игру</option>
              <option v-for="game in lobbyGames" :key="game.game_id" :value="game.game_id">{{ game.title }}</option>
            </select>
          </div>

          <div class="lc-field">
            <label class="form-label small">Название лобби</label>
            <input
              v-model.trim="form.title"
              class="form-control"
              placeholder="Название лобби"
              :disabled="!canManage || isCreating"
              @input="titleTouched = true"
            />
          </div>

          <div class="lc-field-row">
            <div class="lc-field">
              <label class="form-label small">Доступ</label>
              <div class="lc-access-toggle">
                <button
                  type="button"
                  :class="{ active: form.access === 'public' }"
                  :disabled="!canManage || isCreating"
                  @click="setAccess('public')"
                >
                  <strong>Открытое</strong>

                </button>
                <button
                  type="button"
                  :class="{ active: form.access === 'code' }"
                  :disabled="!canManage || isCreating"
                  @click="setAccess('code')"
                >
                  <strong>По коду</strong>

                </button>
              </div>
            </div>

            <div class="lc-field">
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

          </div>

          <div v-if="form.access === 'code'" class="lc-field">
            <label class="form-label small">Код входа</label>
            <div class="input-group">
              <input
                v-model.trim="form.access_code"
                class="form-control mono"
                placeholder="Например, ARENA-2026"
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
const playerLimitHint = computed(() => {
  if (!selectedGame.value) return 'Сколько учеников сможет участвовать в этом лобби.';
  return `Матчи стартуют от ${selectedGame.value.min_players_per_match ?? 2} игроков, максимум ${selectedGame.value.max_players_per_match ?? 2}.`;
});

function isLobbyCatalogGame(game: GameDto): boolean {
  return game.mode !== 'single_task';
}

const canCreate = computed(() => {
  if (!canManage.value || isCreating.value) return false;
  if (!form.game_id || !form.title.trim()) return false;
  if (!Number.isFinite(form.max_teams) || form.max_teams < 2 || form.max_teams > 512) return false;
  if (form.access === 'code' && !form.access_code.trim()) return false;
  return true;
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
.lc-page { max-width: 1120px; margin-inline: auto; gap: 16px; }
.lc-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-bottom: 8px; }
.lc-head h1 { margin: 8px 0 0; }
.lc-back-link { color: var(--agp-text-muted); text-decoration: none; font-size: 13px; }
.lc-back-link:hover { color: var(--agp-primary); }
.lc-body { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(260px, 1fr); gap: 16px; align-items: start; }
.lc-body--single { grid-template-columns: 1fr; }
.lc-fields, .lc-field { display: grid; gap: 20px; min-width: 0; }
.lc-field { gap: 8px; align-content: start; }
.lc-field .form-label, .lc-field .form-text { margin: 0; }
.lc-field .form-text { color: var(--agp-text-muted); font-size: 12px; }
.lc-field-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.lc-access-toggle { display: flex; gap: 8px; }
.lc-access-toggle button { flex: 1; min-height: 36px; padding: 7px 12px; border: 1px solid var(--agp-border); border-radius: 6px; background: var(--agp-surface); color: var(--agp-text-muted); font: inherit; }
.lc-access-toggle strong { font-weight: 500; }
.lc-access-toggle button.active { border-color: var(--agp-primary); color: var(--agp-primary); background: var(--agp-primary-soft); }
.lc-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-top: 20px; margin-top: 20px; border-top: 1px solid var(--agp-border); }
.lc-preview { display: grid; gap: 12px; }
.lc-preview p, .lc-preview h2 { margin: 0 !important; }
.lc-kicker { color: var(--agp-text-muted); font-size: 12px; }
.lc-preview-pills { display: flex; flex-wrap: wrap; gap: 8px; }
.lc-role-preview { display: grid; gap: 8px; padding-top: 12px; border-top: 1px solid var(--agp-border); font-size: 12px; color: var(--agp-text-muted); }
.lc-role-preview > div { display: flex; flex-wrap: wrap; gap: 8px; }
.lc-role-preview strong { font-family: "JetBrains Mono", monospace; color: var(--agp-text); font-weight: 500; }
@media (max-width: 767px) { .lc-head { align-items: flex-start; } .lc-body { grid-template-columns: 1fr; } .lc-access-toggle button { min-height: 44px; } }
@media (max-width: 480px) { .lc-field-row { grid-template-columns: 1fr; } }
</style>
