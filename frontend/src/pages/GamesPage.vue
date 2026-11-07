<template>
  <section class="agp-grid games-page">
    <header class="agp-page-heading games-head">
      <div>
        <p class="games-kicker mb-1">База арен</p>
        <h1 class="h3 mb-1">Игры</h1>
        <p class="text-muted mb-0">Документация и режимы доступных игр.</p>
      </div>
      <div v-if="canManageGameSources" class="games-head-actions">
        <RouterLink class="btn btn-primary" to="/admin/game-sources">+ Добавить игру</RouterLink>
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
    <LoadingSkeleton v-if="isLoading" :count="8" label="Загрузка игр…" />

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
            class="btn btn-sm btn-primary w-100"
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
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
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
