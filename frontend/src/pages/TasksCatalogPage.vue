<template>
  <section class="agp-grid tasks-catalog-page">
    <header class="agp-card p-4 tasks-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between gap-3">
        <div>
          <h1 class="h3 mb-2">Задачи</h1>
          <p class="text-muted mb-0">Список доступных задач. Выберите нужную и переходите к решению.</p>
        </div>
        <div class="d-flex gap-2 flex-wrap align-items-start">
          <span class="agp-pill agp-pill--primary">задач: {{ tasks.length }}</span>
          <span class="agp-pill agp-pill--neutral">решено вами: {{ solvedByCurrentUserCount }}</span>
        </div>
      </div>
    </header>

    <div class="tasks-layout">
      <section class="agp-grid">
        <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка задач...</article>
        <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>
        <article v-else-if="tasks.length === 0" class="agp-card p-4 text-muted">Задачи пока не опубликованы.</article>

        <div v-else class="tasks-list">
          <article v-for="task in tasks" :key="task.game_id" class="agp-card p-3 task-row">
            <div class="task-row-main">
              <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">
                <div class="d-flex flex-column gap-2">
                  <span
                    class="task-state"
                    :class="isSolvedTask(task.game_id) ? 'task-state--solved' : 'task-state--pending'"
                  >
                    {{ isSolvedTask(task.game_id) ? 'Решено' : 'Не решено' }}
                  </span>
                  <h2 class="h6 mb-0">{{ task.title }}</h2>
                </div>
                <span v-if="task.difficulty" class="agp-pill agp-pill--neutral">{{ task.difficulty }}</span>
              </div>
              <p class="small text-muted mb-0 task-description">
                {{ task.description || 'Описание задачи пока не заполнено.' }}
              </p>
              <div class="d-flex gap-1 flex-wrap">
                <span v-for="topic in task.topics" :key="`${task.game_id}-${topic}`" class="agp-topic-chip">
                  {{ topic }}
                </span>
              </div>
              <div class="task-meta-row small text-muted">
                <span>
                  Попыток: <span class="mono">{{ task.attempts_finished }}</span>
                </span>
                <span>
                  Решили: <span class="mono">{{ task.solved_users }}</span>
                </span>
              </div>
            </div>
            <div class="task-row-action">
              <RouterLink :to="`/tasks/${task.game_id}/run`" class="btn btn-dark w-100">Решать</RouterLink>
            </div>
          </article>
        </div>
      </section>

      <aside class="agp-grid tasks-sidebar">
        <article class="agp-card p-3 leaderboard-card">
          <h2 class="h6 mb-1">Лидерборд</h2>
          <p class="small text-muted mb-2">Кто сколько задач решил.</p>
          <div v-if="summaryError" class="small text-danger">{{ summaryError }}</div>
          <div v-else-if="!solvedSummary" class="small text-muted">Загрузка...</div>
          <div v-else-if="solvedSummary.entries.length === 0" class="small text-muted">
            Решённых задач пока нет.
          </div>
          <div v-else class="d-flex flex-column gap-2">
            <div v-if="currentUserEntry" class="agp-card-soft p-2 current-user-summary">
              <div class="small text-muted">Ваш результат</div>
              <div class="d-flex justify-content-between align-items-baseline gap-2">
                <span class="mono small">#{{ currentUserEntry.place }}</span>
                <strong class="mono">{{ currentUserEntry.solved_tasks_count }}</strong>
              </div>
            </div>
            <div
              v-for="entry in leaderboardEntries"
              :key="entry.user_id"
              class="agp-card-soft p-2 d-flex justify-content-between align-items-center gap-2 leaderboard-row"
              :class="{ 'leaderboard-row--mine': isCurrentUser(entry.user_id) }"
            >
              <span class="mono small">#{{ entry.place }} {{ leaderboardUserLabel(entry.user_id) }}</span>
              <strong class="mono small">{{ entry.solved_tasks_count }}</strong>
            </div>
          </div>
        </article>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import { useSessionStore } from '../stores/session';
import {
  getSingleTaskSolvedSummary,
  listSingleTaskCatalog,
  type SingleTaskCatalogItemDto,
  type SingleTaskSolvedSummaryEntryDto,
  type SingleTaskSolvedSummaryDto,
} from '../lib/api';

const SOLVED_SUMMARY_LIMIT = 500;

const sessionStore = useSessionStore();
const tasks = ref<SingleTaskCatalogItemDto[]>([]);
const solvedSummary = ref<SingleTaskSolvedSummaryDto | null>(null);
const isLoading = ref(false);
const errorMessage = ref('');
const summaryError = ref('');

const currentUserKeys = computed(() => {
  const keys = [sessionStore.externalUserId, sessionStore.nickname]
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
  return new Set(keys);
});

const currentUserSolvedGameIds = computed(() => {
  const ids = new Set<string>();
  const entries = solvedSummary.value?.entries ?? [];
  for (const entry of entries) {
    if (!currentUserKeys.value.has(entry.user_id)) continue;
    for (const gameId of entry.solved_game_ids) ids.add(gameId);
  }
  return ids;
});

const solvedByCurrentUserCount = computed(() => currentUserSolvedGameIds.value.size);

const currentUserEntry = computed<SingleTaskSolvedSummaryEntryDto | null>(() => {
  const entries = solvedSummary.value?.entries ?? [];
  return entries.find((entry) => currentUserKeys.value.has(entry.user_id)) ?? null;
});

const leaderboardEntries = computed(() => {
  const entries = solvedSummary.value?.entries ?? [];
  const current = currentUserEntry.value;
  const withoutCurrent = current ? entries.filter((entry) => entry.user_id !== current.user_id) : entries;
  return withoutCurrent.slice(0, 7);
});

function isSolvedTask(gameId: string): boolean {
  return currentUserSolvedGameIds.value.has(gameId);
}

function isCurrentUser(userId: string): boolean {
  return currentUserKeys.value.has(userId);
}

function leaderboardUserLabel(userId: string): string {
  return isCurrentUser(userId) ? 'Вы' : userId;
}

onMounted(async () => {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    tasks.value = await listSingleTaskCatalog();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить каталог задач';
  } finally {
    isLoading.value = false;
  }

  try {
    solvedSummary.value = await getSingleTaskSolvedSummary(SOLVED_SUMMARY_LIMIT);
  } catch (error) {
    summaryError.value = error instanceof Error ? error.message : 'Не удалось загрузить лидерборд';
  }
});
</script>

<style scoped>
.tasks-catalog-page {
  gap: 0.9rem;
}

.tasks-head {
  background:
    linear-gradient(130deg, rgba(223, 247, 244, 0.62) 0%, rgba(255, 255, 255, 0.92) 44%, rgba(255, 241, 219, 0.48) 100%);
}

.tasks-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(16rem, 18rem);
  gap: 0.9rem;
  align-items: start;
}

.tasks-list {
  display: grid;
  gap: 0.75rem;
}

.task-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.8rem;
  align-items: start;
  transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
}

.task-row:hover {
  transform: translateY(-1px);
  border-color: #c8d4e0;
  box-shadow: 0 16px 34px rgba(17, 24, 39, 0.08);
}

.task-row-main {
  min-width: 0;
  display: grid;
  gap: 0.45rem;
}

.task-row-action {
  align-self: start;
  display: flex;
  align-items: flex-start;
}

.task-description {
  min-height: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-meta-row {
  display: flex;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.task-state {
  width: fit-content;
  border-radius: 999px;
  border: 1px solid var(--agp-border);
  padding: 0.14rem 0.52rem;
  font-size: 0.72rem;
  letter-spacing: 0.015em;
  font-weight: 800;
  text-transform: uppercase;
}

.task-state--solved {
  border-color: #83c9bf;
  background: #eaf9f6;
  color: var(--agp-primary);
}

.task-state--pending {
  border-color: #e1c69b;
  background: #fff6e9;
  color: #8a4b0c;
}

.tasks-sidebar {
  gap: 0.65rem;
}

.leaderboard-card {
  position: sticky;
  top: 0.85rem;
}

.current-user-summary {
  background: #edf8f6;
  border-color: #9fd7cf;
}

.leaderboard-row--mine {
  border-color: rgba(15, 118, 110, 0.45);
  background: #ecf9f7;
}

@media (max-width: 1100px) {
  .tasks-layout {
    grid-template-columns: 1fr;
  }

  .leaderboard-card {
    position: static;
  }
}

@media (max-width: 800px) {
  .task-row {
    grid-template-columns: 1fr;
  }
}
</style>
