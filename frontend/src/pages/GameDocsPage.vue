<template>
  <section class="agp-grid game-docs-page">
    <header class="agp-card p-4 game-docs-head">
      <div class="game-docs-head-main">
        <div class="game-docs-title-line">
          <RouterLink class="agp-back-link" :to="backTarget">←</RouterLink>
          <div>
            <p class="game-docs-kicker mb-1">Документация</p>
            <h1 class="h3 mb-0">{{ game?.title || 'Документация' }}</h1>
          </div>
        </div>
        <div class="game-docs-head-stats" aria-label="Сводка документации">
          <div>
            <span>Файлов</span>
            <strong class="mono">{{ docs?.links.length ?? 0 }}</strong>
          </div>
          <div>
            <span>Заполнено</span>
            <strong class="mono">{{ filledDocsCount }}</strong>
          </div>
          <div>
            <span>Режим</span>
            <strong>{{ game?.mode === 'single_task' ? 'задача' : 'игра' }}</strong>
          </div>
        </div>
      </div>
      <div class="game-docs-head-copy">
        <p class="text-muted mb-0">{{ docs?.player_instruction || 'Документация игры' }}</p>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <LoadingSkeleton v-if="isLoading" :count="2" layout="list" label="Загрузка документации…" />

    <template v-else-if="docs">
      <article v-if="!docs.links.length" class="agp-card p-4">
        <div class="agp-empty-state">Документация для этой игры пока не подключена.</div>
      </article>

      <article v-for="link in docs.links" :key="link.path" class="agp-card p-4 game-doc-section">
        <header>
          <div>
            <p class="game-docs-kicker mb-1">Файл руководства</p>
            <h2 class="h5 mb-1">{{ link.title }}</h2>
          </div>
          <span class="game-doc-path mono small">{{ link.path }}</span>
        </header>
        <MarkdownContent v-if="link.content" :source="link.content" />
        <div v-else class="agp-empty-state agp-empty-state--compact mt-3">Файл документации пуст или недоступен.</div>
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
const filledDocsCount = computed(() =>
  docs.value?.links.filter((link) => (link.content ?? '').trim().length > 0).length ?? 0
);
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
.game-docs-page {
  gap: 0.9rem;
}

.game-docs-head {
  position: relative;
  overflow: hidden;
  background: var(--agp-surface);
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.game-docs-head::before {
  content: none;
}

.game-docs-head > * {
  position: relative;
}

.game-docs-head-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.game-docs-title-line {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-width: 0;
}

.game-docs-title-line h1 {
  min-width: 0;
  overflow-wrap: anywhere;
}

.game-docs-head-copy {
  margin-left: 2.6rem;
  margin-top: 0.65rem;
  max-width: 56rem;
}

.game-docs-kicker {
  color: #0f766e;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.game-docs-head-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(5.5rem, 1fr));
  gap: 0.55rem;
  min-width: min(100%, 22rem);
}

.game-docs-head-stats div {
  display: grid;
  gap: 0.05rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 0.85rem;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.game-docs-head-stats span {
  color: var(--agp-text-muted);
  font-size: 0.72rem;
  font-weight: 700;
}

.game-docs-head-stats strong {
  color: var(--agp-text);
  font-size: 1.02rem;
}

.game-doc-section header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  border-bottom: 1px solid var(--agp-border);
  margin-bottom: 0.9rem;
  padding-bottom: 0.65rem;
}

.game-doc-section {
  position: relative;
  overflow: hidden;
}

.game-doc-section::before {
  content: none;
}

.game-doc-section > * {
  position: relative;
}

.game-doc-path {
  border: 1px solid rgba(148, 163, 184, 0.38);
  border-radius: 999px;
  background: #f8fafc;
  color: var(--agp-text-muted);
  padding: 0.18rem 0.55rem;
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .game-docs-head-main,
  .game-doc-section header {
    flex-direction: column;
  }

  .game-docs-head-copy {
    margin-left: 0;
  }

  .game-docs-head-stats {
    grid-template-columns: 1fr;
    min-width: 0;
    width: 100%;
  }
}
</style>
