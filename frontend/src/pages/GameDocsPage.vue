<template>
  <section class="agp-grid game-docs-page">
    <header class="agp-card p-4 game-docs-head">
      <div>
        <RouterLink class="agp-back-link" :to="backTarget">←</RouterLink>
        <h1 class="h3 mb-1">{{ game?.title || 'Документация' }}</h1>
        <p class="text-muted mb-0">{{ docs?.player_instruction || 'Документация игры' }}</p>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка документации...</article>

    <template v-else-if="docs">
      <article v-if="!docs.links.length" class="agp-card p-4 text-muted">
        Документация для этой игры пока не подключена.
      </article>

      <article v-for="link in docs.links" :key="link.path" class="agp-card p-4 game-doc-section">
        <header>
          <h2 class="h5 mb-1">{{ link.title }}</h2>
          <span class="mono small text-muted">{{ link.path }}</span>
        </header>
        <MarkdownContent v-if="link.content" :source="link.content" />
        <div v-else class="small text-muted mt-3">Файл документации пуст или недоступен.</div>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import MarkdownContent from '../components/MarkdownContent.vue';
import { getGame, getGameDocs, type GameDocumentationDto, type GameDto } from '../lib/api';

const route = useRoute();

const game = ref<GameDto | null>(null);
const docs = ref<GameDocumentationDto | null>(null);
const isLoading = ref(false);
const errorMessage = ref('');
const backTarget = computed(() => {
  const id = gameId();
  if (route.query.from === 'task' && id) {
    return { name: 'task-run', params: { gameId: id } };
  }
  if (route.query.from === 'lobby' && typeof route.query.lobby_id === 'string') {
    return { name: 'lobby', params: { lobbyId: route.query.lobby_id } };
  }
  return { name: 'games' };
});

function gameId(): string {
  return String(route.params.gameId || '').trim();
}

onMounted(async () => {
  const id = gameId();
  if (!id) {
    errorMessage.value = 'Не передан gameId';
    return;
  }
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const [freshGame, freshDocs] = await Promise.all([getGame(id), getGameDocs(id)]);
    game.value = freshGame;
    docs.value = freshDocs;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить документацию';
  } finally {
    isLoading.value = false;
  }
});
</script>

<style scoped>
.game-docs-page {
  gap: 0.9rem;
}

.game-docs-head {
  background: #f8fafc;
}

.game-doc-section header {
  border-bottom: 1px solid var(--agp-border);
  margin-bottom: 0.9rem;
  padding-bottom: 0.65rem;
}
</style>
