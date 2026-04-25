<template>
  <section class="agp-grid tasks-catalog-page">
    <header class="agp-card p-4 tasks-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between gap-3">
        <div>
          <div class="mb-2">
            <RouterLink class="btn btn-sm btn-outline-secondary" to="/tasks">Все разделы</RouterLink>
          </div>
          <h1 class="h3 mb-2">{{ routeSection }}</h1>
          <p class="text-muted mb-0">
            {{ sectionDescription(routeSection) }}
          </p>
        </div>
        <div class="d-flex gap-2 flex-wrap align-items-start">
          <span class="agp-pill agp-pill--primary">показано: {{ filteredTasks.length }}/{{ sectionTasks.length }}</span>
          <span class="agp-pill agp-pill--neutral">решено в разделе: {{ sectionSolvedCount }}</span>
          <span class="agp-pill agp-pill--neutral">тегов: {{ topicOptions.length }}</span>
        </div>
      </div>
    </header>

    <section class="agp-card p-3 section-progress-panel" aria-label="Прогресс раздела">
      <div>
        <div class="small text-muted text-uppercase fw-semibold">Прогресс раздела</div>
        <strong>{{ sectionSolvedCount }} из {{ sectionTasks.length }}</strong>
      </div>
      <div class="section-progress" role="progressbar" :aria-valuenow="sectionProgressPercent" aria-valuemin="0" aria-valuemax="100">
        <div :style="{ width: `${sectionProgressPercent}%` }"></div>
      </div>
      <span class="mono">{{ sectionProgressPercent }}%</span>
    </section>

    <section class="agp-card p-3 tasks-filter-panel" aria-label="Фильтры задач">
      <div>
        <div class="small text-muted text-uppercase fw-semibold">Фильтры обучения</div>
        <div class="fw-semibold">Найдите следующую задачу по тегу, сложности и прогрессу</div>
      </div>
      <label class="tasks-filter-field">
        <span class="form-label small mb-1">Тег</span>
        <select v-model="selectedTopic" class="form-select form-select-sm">
          <option value="">Все теги</option>
          <option v-for="topic in topicOptions" :key="topic" :value="topic">{{ topic }}</option>
        </select>
      </label>
      <label class="tasks-filter-field">
        <span class="form-label small mb-1">Сложность</span>
        <select v-model="selectedDifficulty" class="form-select form-select-sm">
          <option value="">Любая</option>
          <option v-for="difficulty in difficultyOptions" :key="difficulty" :value="difficulty">
            {{ difficultyLabel(difficulty) }}
          </option>
        </select>
      </label>
      <label class="tasks-filter-field">
        <span class="form-label small mb-1">Прогресс</span>
        <select v-model="selectedProgress" class="form-select form-select-sm">
          <option value="all">Все</option>
          <option value="unsolved">Не решено</option>
          <option value="solved">Решено</option>
        </select>
      </label>
      <button class="btn btn-sm btn-outline-secondary tasks-filter-reset" :disabled="!hasActiveFilters" @click="resetFilters">
        Сбросить
      </button>
    </section>

    <div v-if="hasActiveFilters" class="tasks-active-filter-line">
      <span>Фильтр:</span>
      <strong>{{ activeFilterSummary }}</strong>
    </div>

    <div class="tasks-layout">
      <section class="agp-grid">
        <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка задач...</article>
        <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>
        <article v-else-if="tasks.length === 0" class="agp-card p-4 text-muted">Задачи пока не опубликованы.</article>
        <article v-else-if="sectionTasks.length === 0" class="agp-card p-4 text-muted">В этом разделе задач нет.</article>
        <article v-else-if="filteredTasks.length === 0" class="agp-card p-4 text-muted">
          По выбранным фильтрам задач нет. Сбросьте фильтры или выберите другой тег.
        </article>

        <div v-else class="tasks-list">
          <section v-for="group in groupedFilteredTasks" :key="group.key" class="tasks-group">
            <header class="tasks-group-head">
              <div>
                <h2>{{ group.learningSection }}</h2>
                <p>{{ sectionDescription(group.learningSection) }}</p>
              </div>
              <span>{{ group.items.length }}</span>
            </header>
            <div class="tasks-group-items">
              <article v-for="task in group.items" :key="task.game_id" class="agp-card p-3 task-row">
                <div class="task-row-main">
                  <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">
                    <div class="d-flex flex-column gap-2">
                      <span
                        class="task-state"
                        :class="isSolvedTask(task.game_id) ? 'task-state--solved' : 'task-state--pending'"
                      >
                        {{ isSolvedTask(task.game_id) ? 'Решено' : 'Не решено' }}
                      </span>
                      <h3 class="h6 mb-0">{{ task.title }}</h3>
                    </div>
                    <div class="d-flex gap-1 flex-wrap justify-content-end">
                      <span v-if="task.difficulty" class="agp-pill agp-pill--neutral">{{ difficultyLabel(task.difficulty) }}</span>
                      <span v-if="task.learning_section" class="agp-pill agp-pill--primary">{{ task.learning_section }}</span>
                    </div>
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
                    <span>Попыток: <span class="mono">{{ task.attempts_finished }}</span></span>
                    <span>Решили: <span class="mono">{{ task.solved_users }}</span></span>
                    <span>Успех: <span class="mono">{{ successRateLabel(task) }}</span></span>
                  </div>
                </div>
                <div class="task-row-action">
                  <RouterLink :to="`/tasks/${task.game_id}/run`" class="btn btn-dark btn-sm w-100">
                    {{ isSolvedTask(task.game_id) ? 'Повторить' : 'Решать' }}
                  </RouterLink>
                </div>
              </article>
            </div>
          </section>
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
import { RouterLink, useRoute } from 'vue-router';

import { useSessionStore } from '../stores/session';
import {
  getSingleTaskSolvedSummary,
  listSingleTaskCatalog,
  type SingleTaskCatalogItemDto,
  type SingleTaskSolvedSummaryEntryDto,
  type SingleTaskSolvedSummaryDto,
} from '../lib/api';
import { difficultyLabel, difficultyOrder, sectionDescription, sectionOrder } from '../lib/taskCatalog';

const SOLVED_SUMMARY_LIMIT = 500;

const sessionStore = useSessionStore();
const route = useRoute();
const tasks = ref<SingleTaskCatalogItemDto[]>([]);
const solvedSummary = ref<SingleTaskSolvedSummaryDto | null>(null);
const isLoading = ref(false);
const errorMessage = ref('');
const summaryError = ref('');
const selectedTopic = ref('');
const selectedDifficulty = ref('');
const selectedProgress = ref<'all' | 'solved' | 'unsolved'>('all');

const routeSection = computed(() => String(route.params.section ?? ''));

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

const sectionTasks = computed(() =>
  tasks.value.filter((task) => (task.learning_section || 'Другое') === routeSection.value)
);
const sectionSolvedCount = computed(() =>
  sectionTasks.value.filter((task) => currentUserSolvedGameIds.value.has(task.game_id)).length
);
const sectionProgressPercent = computed(() =>
  sectionTasks.value.length > 0 ? Math.round((sectionSolvedCount.value / sectionTasks.value.length) * 100) : 0
);
const topicOptions = computed(() =>
  Array.from(new Set(sectionTasks.value.flatMap((task) => task.topics))).sort((a, b) => a.localeCompare(b))
);
const difficultyOptions = computed(() =>
  Array.from(new Set(sectionTasks.value.map((task) => task.difficulty).filter((item): item is string => Boolean(item)))).sort(
    (a, b) => difficultyOrder(a) - difficultyOrder(b) || a.localeCompare(b)
  )
);
const hasActiveFilters = computed(() =>
  Boolean(selectedTopic.value || selectedDifficulty.value || selectedProgress.value !== 'all')
);
const activeFilterSummary = computed(() => {
  const parts: string[] = [];
  if (selectedTopic.value) parts.push(`тег: ${selectedTopic.value}`);
  if (selectedDifficulty.value) parts.push(`сложность: ${difficultyLabel(selectedDifficulty.value)}`);
  if (selectedProgress.value === 'solved') parts.push('только решенные');
  if (selectedProgress.value === 'unsolved') parts.push('только нерешенные');
  return parts.join(' · ');
});
const filteredTasks = computed(() =>
  sectionTasks.value.filter((task) => {
    if (selectedTopic.value && !task.topics.includes(selectedTopic.value)) return false;
    if (selectedDifficulty.value && task.difficulty !== selectedDifficulty.value) return false;
    if (selectedProgress.value === 'solved' && !isSolvedTask(task.game_id)) return false;
    if (selectedProgress.value === 'unsolved' && isSolvedTask(task.game_id)) return false;
    return true;
  })
);

const groupedFilteredTasks = computed(() => {
  const groups = new Map<string, { key: string; learningSection: string; items: SingleTaskCatalogItemDto[] }>();
  for (const task of filteredTasks.value) {
    const learningSection = task.learning_section || 'Другое';
    const key = learningSection;
    const group = groups.get(key) ?? { key, learningSection, items: [] };
    group.items.push(task);
    groups.set(key, group);
  }
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      items: group.items.sort(
        (left, right) =>
          difficultyOrder(left.difficulty || '') - difficultyOrder(right.difficulty || '') ||
          left.title.localeCompare(right.title, 'ru')
      ),
    }))
    .sort((left, right) => sectionOrder(left.learningSection) - sectionOrder(right.learningSection));
});

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

function successRateLabel(task: SingleTaskCatalogItemDto): string {
  if (task.attempts_finished <= 0) return 'нет данных';
  return `${Math.round((task.solved_users / task.attempts_finished) * 100)}%`;
}

function resetFilters(): void {
  selectedTopic.value = '';
  selectedDifficulty.value = '';
  selectedProgress.value = 'all';
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
  background: #f8fafc;
}

.section-progress-panel {
  display: grid;
  grid-template-columns: minmax(10rem, auto) minmax(12rem, 1fr) auto;
  gap: 0.85rem;
  align-items: center;
}

.section-progress {
  height: 0.65rem;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.section-progress div {
  height: 100%;
  border-radius: inherit;
  background: #2563eb;
  transition: width 0.2s ease;
}

.tasks-filter-panel {
  display: grid;
  grid-template-columns: minmax(14rem, 1fr) repeat(3, minmax(9rem, 0.62fr)) auto;
  gap: 0.75rem;
  align-items: end;
}

.tasks-filter-field {
  min-width: 0;
}

.tasks-filter-reset {
  white-space: nowrap;
}

.tasks-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(16rem, 18rem);
  gap: 0.9rem;
  align-items: start;
}

.tasks-active-filter-line {
  display: flex;
  gap: 0.4rem;
  align-items: baseline;
  color: var(--agp-text-muted);
  font-size: 0.86rem;
}

.tasks-active-filter-line strong {
  color: var(--agp-text);
}

.tasks-list {
  display: grid;
  gap: 0.75rem;
}

.tasks-group {
  display: grid;
  gap: 0.55rem;
}

.tasks-group-items {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 18rem), 18rem));
  gap: 0.75rem;
  justify-content: start;
}

.tasks-group-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.75rem;
  padding: 0.1rem 0.1rem 0;
}

.tasks-group-head h2 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 850;
}

.tasks-group-head p {
  margin: 0.15rem 0 0;
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.tasks-group-head span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.task-row {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 0.65rem;
  align-items: start;
  min-height: 13.25rem;
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
  align-self: end;
  display: flex;
  align-items: flex-end;
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
  gap: 0.55rem;
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
  .section-progress-panel,
  .tasks-filter-panel {
    grid-template-columns: 1fr 1fr;
  }

  .tasks-layout {
    grid-template-columns: 1fr;
  }

  .leaderboard-card {
    position: static;
  }
}

@media (max-width: 800px) {
  .section-progress-panel,
  .tasks-filter-panel {
    grid-template-columns: 1fr;
  }

  .task-row {
    grid-template-columns: 1fr;
  }

  .tasks-filter-reset {
    width: 100%;
  }
}
</style>
