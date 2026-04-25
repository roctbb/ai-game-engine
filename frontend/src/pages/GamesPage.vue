<template>
  <section class="agp-grid games-page">
    <header class="agp-card p-4 games-head">
      <div>
        <h1 class="h3 mb-1">Игры</h1>
        <p class="text-muted mb-0">Документация и режимы доступных игр.</p>
      </div>
      <div v-if="canManageGameSources" class="games-head-actions">
        <RouterLink class="btn btn-dark" to="/admin/game-sources">+ Добавить игру</RouterLink>
        <RouterLink class="btn btn-outline-secondary" to="/admin/game-sources">Источники игр</RouterLink>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка игр...</article>

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
          </div>
          <h2 class="h6 mb-0">{{ game.title }}</h2>
          <p class="small text-muted mb-0 game-description">{{ game.description || 'Описание пока не заполнено.' }}</p>
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
        {{ emptyGamesText }}
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
  if (mode === 'small_match' || mode === 'massive_lobby') return 'лобби';
  return 'лобби';
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
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.games-head {
  background: #f8fafc;
}

.games-head-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
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
  min-height: 13.25rem;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 0.65rem;
  align-items: start;
  transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
}

.game-card:hover {
  transform: translateY(-1px);
  border-color: #c8d4e0;
  box-shadow: 0 16px 34px rgba(17, 24, 39, 0.08);
}

.game-row-main {
  min-width: 0;
  display: grid;
  gap: 0.45rem;
}

.game-actions {
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
}
</style>
