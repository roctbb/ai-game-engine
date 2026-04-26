<template>
  <section class="agp-grid games-page">
    <header class="agp-card p-4 games-head">
      <div>
        <p class="games-kicker mb-1">База арен</p>
        <h1 class="h3 mb-1">Игры</h1>
        <p class="text-muted mb-0">Документация и режимы доступных игр.</p>
      </div>
      <div v-if="canManageGameSources" class="games-head-actions">
        <RouterLink class="btn btn-dark" to="/admin/game-sources">+ Добавить игру</RouterLink>
        <RouterLink class="btn btn-outline-secondary" to="/admin/game-sources">Источники игр</RouterLink>
      </div>
      <div class="games-head-stats">
        <div>
          <span>Показано</span>
          <strong class="mono">{{ sortedGames.length }}</strong>
        </div>
        <div>
          <span>Опубликовано</span>
          <strong class="mono">{{ readyGameCount }}</strong>
        </div>
        <div>
          <span>Черновики</span>
          <strong class="mono">{{ draftGameCount }}</strong>
        </div>
        <div>
          <span>Темы</span>
          <strong class="mono">{{ topicCount }}</strong>
        </div>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <article v-if="isLoading" class="agp-card p-4">
      <div class="agp-loading-state agp-loading-state--compact">Загрузка игр...</div>
    </article>

    <article v-if="canManageGameSources && !isLoading" class="agp-card p-3 games-filter-panel">
      <div>
        <div class="small text-muted text-uppercase fw-semibold">Каталог игр</div>
        <div class="fw-semibold">Показывайте только нужные игры для лобби</div>
      </div>
      <label class="games-filter-field">
        <span class="form-label small mb-1">Статус</span>
        <select v-model="statusFilter" class="form-select form-select-sm">
          <option value="">Все</option>
          <option value="ready">Опубликованные</option>
          <option value="draft">Черновики</option>
          <option value="archived">Архив</option>
        </select>
      </label>
      <div class="games-filter-summary small text-muted">
        показано: <span class="mono">{{ sortedGames.length }}</span>
        из <span class="mono">{{ lobbyGameCount }}</span>
      </div>
    </article>

    <section v-if="!isLoading" class="games-card-grid">
      <article v-for="game in sortedGames" :key="game.game_id" class="agp-card p-3 game-card">
        <div class="game-row-main">
          <div class="d-flex gap-2 flex-wrap mb-2">
            <span class="agp-pill agp-pill--neutral">{{ modeLabel(game.mode) }}</span>
            <span v-if="canManageGameSources" class="agp-pill" :class="catalogStatusPillClass(game.catalog_metadata_status)">
              {{ catalogStatusLabel(game.catalog_metadata_status) }}
            </span>
            <span v-if="game.difficulty" class="agp-pill agp-pill--neutral">{{ difficultyLabel(game.difficulty) }}</span>
            <span v-if="game.learning_section" class="agp-pill agp-pill--primary">{{ game.learning_section }}</span>
          </div>
          <h2 class="h6 mb-0">{{ game.title }}</h2>
          <p class="small text-muted mb-0 game-description">{{ game.description || 'Описание пока не заполнено.' }}</p>
          <div class="game-meta-strip">
            <div>
              <span>Роли</span>
              <strong class="mono">{{ gameRoleCount(game) }}</strong>
            </div>
            <div>
              <span>Матч</span>
              <strong class="mono">{{ matchBoundsLabel(game) }}</strong>
            </div>
            <div>
              <span>Версий</span>
              <strong class="mono">{{ game.versions.length }}</strong>
            </div>
          </div>
          <div class="d-flex gap-1 flex-wrap">
            <span v-for="topic in game.topics" :key="`${game.game_id}-${topic}`" class="agp-topic-chip">
              {{ topic }}
            </span>
          </div>
        </div>
        <div class="game-actions">
          <RouterLink
            class="btn btn-sm btn-dark w-100"
            :to="{ name: 'game-docs', params: { gameId: game.game_id }, query: { from: 'games' } }"
            target="_blank"
            rel="noopener noreferrer"
          >
            Документация
          </RouterLink>
        </div>
      </article>
      <article v-if="!sortedGames.length" class="agp-card p-4 text-muted">
        <div class="agp-empty-state">{{ emptyGamesText }}</div>
      </article>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import { listGames, type CatalogMetadataStatus, type GameDto, type GameMode } from '../lib/api';
import { useSessionStore } from '../stores/session';

const sessionStore = useSessionStore();
const games = ref<GameDto[]>([]);
const isLoading = ref(false);
const errorMessage = ref('');
const statusFilter = ref<CatalogMetadataStatus | ''>('');

const canManageGameSources = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const lobbyGameCount = computed(() => games.value.filter((game) => game.mode !== 'single_task').length);
const readyGameCount = computed(() => games.value.filter((game) => game.mode !== 'single_task' && game.catalog_metadata_status === 'ready').length);
const draftGameCount = computed(() => games.value.filter((game) => game.mode !== 'single_task' && game.catalog_metadata_status === 'draft').length);
const topicCount = computed(() => new Set(games.value.filter((game) => game.mode !== 'single_task').flatMap((game) => game.topics)).size);
const sortedGames = computed(() =>
  games.value
    .filter((game) => isLobbyCatalogGame(game))
    .sort((a, b) => a.title.localeCompare(b.title)),
);
const emptyGamesText = computed(() =>
  canManageGameSources.value
    ? 'Игры для лобби пока не подключены.'
    : 'Опубликованные игры для лобби пока не подключены.'
);

function isLobbyCatalogGame(game: GameDto): boolean {
  if (game.mode === 'single_task') return false;
  if (canManageGameSources.value && statusFilter.value && game.catalog_metadata_status !== statusFilter.value) {
    return false;
  }
  return canManageGameSources.value || game.catalog_metadata_status === 'ready';
}

function modeLabel(mode: GameMode): string {
  if (mode === 'multiplayer' || mode === 'small_match' || mode === 'massive_lobby') return 'мультиплеер';
  return 'лобби';
}

function matchBoundsLabel(game: GameDto): string {
  const min = game.min_players_per_match ?? 2;
  const max = game.max_players_per_match ?? min;
  return min === max ? String(min) : `${min}-${max}`;
}

function gameRoleCount(game: GameDto): number {
  return game.versions.find((version) => version.version_id === game.active_version_id)?.required_slot_keys.length
    ?? game.versions[0]?.required_slot_keys.length
    ?? 0;
}

function difficultyLabel(difficulty: GameDto['difficulty']): string {
  if (difficulty === 'easy') return 'легкая';
  if (difficulty === 'medium') return 'средняя';
  if (difficulty === 'hard') return 'сложная';
  return difficulty ?? '';
}

function catalogStatusLabel(status: CatalogMetadataStatus): string {
  if (status === 'ready') return 'опубликовано';
  if (status === 'draft') return 'черновик';
  return 'архив';
}

function catalogStatusPillClass(status: CatalogMetadataStatus): string {
  if (status === 'ready') return 'agp-pill--primary';
  if (status === 'draft') return 'agp-pill--warning';
  return 'agp-pill--neutral';
}

onMounted(async () => {
  isLoading.value = true;
  try {
    games.value = await listGames();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить игры';
  } finally {
    isLoading.value = false;
  }
});
</script>

<style scoped>
.games-page {
  gap: 0.9rem;
}

.games-head {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: flex-start;
  background:
    url("data:image/svg+xml,%3Csvg width='176' height='104' viewBox='0 0 176 104' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%232563eb' stroke-opacity='.13' stroke-width='2'%3E%3Cpath d='M18 18h28v28H18zM130 18h28v28h-28zM74 58h28v28H74z'/%3E%3Cpath d='M46 32h28M102 72h28M88 0v24M88 80v24'/%3E%3C/g%3E%3C/svg%3E") right 1rem top 0.8rem / 14rem auto no-repeat,
    radial-gradient(circle at 12% 18%, rgba(37, 99, 235, 0.16), transparent 16rem),
    radial-gradient(circle at 88% 8%, rgba(20, 184, 166, 0.18), transparent 15rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(240, 253, 250, 0.95));
}

.games-head::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.22rem;
  background: linear-gradient(90deg, #2563eb, #14b8a6, #f59e0b);
}

.games-kicker {
  color: #2563eb;
  font-size: 0.76rem;
  font-weight: 900;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.games-head-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.games-head-stats {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
}

.games-head-stats > div {
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

.games-head-stats span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.games-head-stats strong {
  color: var(--agp-text);
  font-size: 0.96rem;
}

.games-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 18rem), 18rem));
  gap: 0.75rem;
  justify-content: start;
}

.games-filter-panel {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.games-filter-field {
  min-width: min(100%, 14rem);
}

.games-filter-summary {
  margin-left: auto;
}

.game-card {
  position: relative;
  overflow: hidden;
  min-height: 13.25rem;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 0.65rem;
  align-items: start;
  transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
}

.game-card:hover {
  transform: translateY(-2px);
  border-color: rgba(37, 99, 235, 0.34);
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.11);
}

.game-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.28rem;
  background: linear-gradient(90deg, #2563eb, #14b8a6, #f59e0b);
}

.game-card::after {
  content: '';
  position: absolute;
  right: -1.4rem;
  bottom: -1.55rem;
  width: 5.5rem;
  height: 5.5rem;
  border-radius: 1.35rem;
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.12), rgba(245, 158, 11, 0.12)),
    url("data:image/svg+xml,%3Csvg width='88' height='88' viewBox='0 0 88 88' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%232563eb' stroke-opacity='.25'%3E%3Cpath d='M14 44h60M44 14v60M28 28h32v32H28z'/%3E%3C/g%3E%3C/svg%3E");
  pointer-events: none;
}

.game-row-main {
  position: relative;
  z-index: 1;
  min-width: 0;
  display: grid;
  gap: 0.45rem;
}

.game-meta-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.45rem;
}

.game-meta-strip > div {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 0.55rem;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6rem;
  background: rgba(248, 250, 252, 0.84);
  padding: 0.42rem 0.55rem;
}

.game-meta-strip span {
  color: var(--agp-text-muted);
  font-size: 0.76rem;
  font-weight: 700;
}

.game-actions {
  position: relative;
  z-index: 1;
  display: flex;
  align-self: end;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.game-description {
  min-height: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 760px) {
  .games-head {
    display: grid;
  }

  .game-actions {
    justify-content: flex-start;
  }

  .games-head-actions {
    justify-content: flex-start;
  }

  .games-filter-summary {
    margin-left: 0;
  }

  .games-head-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .games-head-stats {
    grid-template-columns: 1fr;
  }
}
</style>
