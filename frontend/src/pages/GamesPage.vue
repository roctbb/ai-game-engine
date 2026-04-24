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

    <section v-else class="games-list">
      <article v-for="game in sortedGames" :key="game.game_id" class="agp-card p-3 game-row">
        <div class="game-row-main">
          <div class="d-flex gap-2 flex-wrap mb-2">
            <span class="agp-pill agp-pill--neutral">{{ modeLabel(game.mode) }}</span>
            <span v-if="game.difficulty" class="agp-pill agp-pill--neutral">{{ difficultyLabel(game.difficulty) }}</span>
          </div>
          <h2 class="h5 mb-1">{{ game.title }}</h2>
          <p class="small text-muted mb-2">{{ game.description || 'Описание пока не заполнено.' }}</p>
          <div class="d-flex gap-1 flex-wrap">
            <span v-for="topic in game.topics" :key="`${game.game_id}-${topic}`" class="agp-topic-chip">
              {{ topic }}
            </span>
          </div>
        </div>
        <div class="game-actions">
          <RouterLink
            class="btn btn-sm btn-outline-secondary"
            :to="{ name: 'game-docs', params: { gameId: game.game_id }, query: { from: 'games' } }"
            target="_blank"
            rel="noopener noreferrer"
          >
            Документация
          </RouterLink>
        </div>
      </article>
      <article v-if="!sortedGames.length" class="agp-card p-4 text-muted">
        Игры для лобби пока не подключены.
      </article>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import { listGames, type GameDto, type GameMode } from '../lib/api';
import { useSessionStore } from '../stores/session';

const sessionStore = useSessionStore();
const games = ref<GameDto[]>([]);
const isLoading = ref(false);
const errorMessage = ref('');

const canManageGameSources = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const sortedGames = computed(() =>
  games.value
    .filter((game) => isLobbyCatalogGame(game))
    .sort((a, b) => a.title.localeCompare(b.title)),
);

function isLobbyCatalogGame(game: GameDto): boolean {
  return game.mode !== 'single_task' && game.catalog_metadata_status === 'ready';
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

.games-head,
.game-row {
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

.games-list {
  display: grid;
  gap: 0.75rem;
}

.game-row {
  flex-wrap: wrap;
}

.game-row-main {
  min-width: min(100%, 28rem);
  flex: 1;
}

.game-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 760px) {
  .games-head,
  .game-row {
    display: grid;
  }

  .game-actions {
    justify-content: flex-start;
  }

  .games-head-actions {
    justify-content: flex-start;
  }
}
</style>
