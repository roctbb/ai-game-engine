<template>
  <section class="agp-grid game-docs-page">
    <header class="game-docs-head">
      <RouterLink class="btn btn-outline-secondary" :to="backTarget">← Назад</RouterLink>
      <h1>{{ game?.title || 'Условие и API' }}</h1>
    </header>
    <p v-if="errorMessage" role="alert" class="text-danger">{{ errorMessage }}</p>
    <LoadingSkeleton v-if="isLoading" :count="2" layout="list" label="Загрузка документации" />
    <template v-else-if="docs">
      <article v-if="docs.player_instruction" class="agp-card game-doc-section"><MarkdownContent :source="docs.player_instruction" /></article>
      <p v-if="!docs.links.length && !docs.player_instruction" class="text-muted">Документация пока не добавлена.</p>
      <article v-for="link in docs.links" :key="link.path" class="agp-card game-doc-section">
        <h2>{{ link.title }}</h2>
        <MarkdownContent v-if="link.content" :source="link.content.replace(/^# [^\n]+\n+/, '')" />
        <p v-else class="text-muted">Документ недоступен.</p>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
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
  return game.value?.mode === 'single_task' && id ? { name: 'task', params: { gameId: id } } : { name: 'lobbies' };
});

function gameId(): string {
  return String(route.params.gameId || '').trim();
}

onMounted(async () => {
  const id = gameId();
  if (!id) {
    errorMessage.value = 'Не найдена игра для документации';
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
.game-docs-page { max-width: 1040px; margin-inline: auto; gap: 16px; }
.game-docs-head { display: flex; align-items: center; gap: 16px; padding-bottom: 8px; }
.game-docs-head h1 { margin: 0; min-width: 0; }
.game-docs-head .btn { flex: none; }
.game-doc-section { padding: 24px; }
.game-doc-section h2 { margin: 0 0 16px; }
@media (max-width: 767px) { .game-doc-section { padding: 16px; } .game-docs-head { align-items: flex-start; } }
</style>
