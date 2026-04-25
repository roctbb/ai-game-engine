<template>
  <section class="agp-grid tasks-catalog-page">
    <header class="agp-card p-4 tasks-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between gap-3">
        <div>
          <h1 class="h3 mb-2">Задачи</h1>
          <p class="text-muted mb-0">
            Сначала выберите учебный раздел, затем откройте список задач внутри него.
          </p>
        </div>
        <div class="d-flex gap-2 flex-wrap align-items-start">
          <span class="agp-pill agp-pill--primary">разделов: {{ sectionCards.length }}</span>
          <span class="agp-pill agp-pill--neutral">задач: {{ tasks.length }}</span>
          <span class="agp-pill agp-pill--neutral">решено вами: {{ solvedByCurrentUserCount }}</span>
        </div>
      </div>
    </header>

    <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка разделов...</article>
    <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>
    <article v-else-if="tasks.length === 0" class="agp-card p-4 text-muted">Задачи пока не опубликованы.</article>

    <section v-else class="section-card-grid" aria-label="Разделы задач">
      <RouterLink
        v-for="section in sectionCards"
        :key="section.name"
        class="agp-card p-3 section-card"
        :class="{ 'section-card--done': section.isDone }"
        :to="{ name: 'tasks-section', params: { section: section.name } }"
      >
        <div class="section-card-top">
          <span class="section-index mono">{{ section.index }}</span>
          <span class="agp-pill" :class="section.isDone ? 'agp-pill--primary' : 'agp-pill--neutral'">
            {{ section.solved }}/{{ section.total }}
          </span>
        </div>
        <div>
          <h2>{{ section.name }}</h2>
          <p>{{ sectionDescription(section.name) }}</p>
        </div>
        <div class="section-progress" role="progressbar" :aria-valuenow="section.percent" aria-valuemin="0" aria-valuemax="100">
          <div :style="{ width: `${section.percent}%` }"></div>
        </div>
        <div class="section-card-foot">
          <span>{{ section.percent }}%</span>
          <span>{{ section.isDone ? 'раздел решен' : 'открыть задачи' }}</span>
        </div>
      </RouterLink>
    </section>

    <aside v-if="!isLoading && !errorMessage" class="agp-card p-3 tasks-summary">
      <h2 class="h6 mb-2">Ваш прогресс</h2>
      <div class="tasks-summary-grid">
        <span>Всего задач</span>
        <strong class="mono">{{ tasks.length }}</strong>
        <span>Решено</span>
        <strong class="mono">{{ solvedByCurrentUserCount }}</strong>
        <span>Полностью закрыто разделов</span>
        <strong class="mono">{{ completedSectionCount }}</strong>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import {
  getSingleTaskSolvedSummary,
  listSingleTaskCatalog,
  type SingleTaskCatalogItemDto,
  type SingleTaskSolvedSummaryDto,
} from '../lib/api';
import { sectionDescription, sectionOrder } from '../lib/taskCatalog';
import { useSessionStore } from '../stores/session';

const SOLVED_SUMMARY_LIMIT = 500;

const sessionStore = useSessionStore();
const tasks = ref<SingleTaskCatalogItemDto[]>([]);
const solvedSummary = ref<SingleTaskSolvedSummaryDto | null>(null);
const isLoading = ref(false);
const errorMessage = ref('');

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

const sectionCards = computed(() => {
  const groups = new Map<string, SingleTaskCatalogItemDto[]>();
  for (const task of tasks.value) {
    const section = task.learning_section || 'Другое';
    const items = groups.get(section) ?? [];
    items.push(task);
    groups.set(section, items);
  }

  return Array.from(groups.entries())
    .map(([name, items]) => {
      const solved = items.filter((task) => currentUserSolvedGameIds.value.has(task.game_id)).length;
      const total = items.length;
      const percent = total > 0 ? Math.round((solved / total) * 100) : 0;
      return {
        name,
        total,
        solved,
        percent,
        isDone: total > 0 && solved === total,
        index: sectionOrder(name) + 1,
      };
    })
    .sort((left, right) => sectionOrder(left.name) - sectionOrder(right.name) || left.name.localeCompare(right.name, 'ru'));
});

const completedSectionCount = computed(() => sectionCards.value.filter((section) => section.isDone).length);

onMounted(async () => {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const [catalog, summary] = await Promise.all([
      listSingleTaskCatalog(),
      getSingleTaskSolvedSummary(SOLVED_SUMMARY_LIMIT),
    ]);
    tasks.value = catalog;
    solvedSummary.value = summary;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить разделы задач';
  } finally {
    isLoading.value = false;
  }
});
</script>

<style scoped>
.tasks-catalog-page {
  gap: 0.9rem;
}

.tasks-head {
  overflow: hidden;
  background:
    radial-gradient(circle at 12% 20%, rgba(245, 158, 11, 0.18), transparent 16rem),
    radial-gradient(circle at 88% 10%, rgba(37, 99, 235, 0.14), transparent 16rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(255, 251, 235, 0.88));
}

.section-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 18rem), 1fr));
  gap: 0.85rem;
}

.section-card {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 0.85rem;
  min-height: 12.5rem;
  color: inherit;
  text-decoration: none;
  border-color: #dbe3ee;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.section-card:hover {
  border-color: rgba(245, 158, 11, 0.45);
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.11);
  transform: translateY(-2px);
}

.section-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.28rem;
  background: linear-gradient(90deg, #f59e0b, #14b8a6, #2563eb);
}

.section-card::after {
  content: '';
  position: absolute;
  right: -1.25rem;
  bottom: -1.5rem;
  width: 5.25rem;
  height: 5.25rem;
  border-radius: 1.2rem;
  background:
    linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(20, 184, 166, 0.11)),
    url("data:image/svg+xml,%3Csvg width='84' height='84' viewBox='0 0 84 84' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23d97706' stroke-opacity='.24'%3E%3Cpath d='M14 42h56M42 14v56M28 28h28v28H28z'/%3E%3C/g%3E%3C/svg%3E");
  pointer-events: none;
}

.section-card--done {
  border-color: #86efac;
  background:
    radial-gradient(circle at 85% 15%, rgba(34, 197, 94, 0.14), transparent 12rem),
    linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
}

.section-card-top,
.section-card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.section-index {
  display: inline-grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  border-radius: 999px;
  background: #e2e8f0;
  color: #334155;
  font-weight: 800;
}

.section-card--done .section-index {
  background: #bbf7d0;
  color: #166534;
}

.section-card h2 {
  margin: 0 0 0.35rem;
  font-size: 1.05rem;
  font-weight: 850;
}

.section-card p {
  margin: 0;
  color: var(--agp-text-muted);
  font-size: 0.86rem;
  line-height: 1.4;
}

.section-progress {
  height: 0.55rem;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.section-progress div {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #14b8a6);
  transition: width 0.2s ease;
}

.section-card--done .section-progress div {
  background: #16a34a;
}

.section-card-foot {
  color: var(--agp-text-muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.tasks-summary {
  max-width: 36rem;
}

.tasks-summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.45rem 1rem;
  color: var(--agp-text-muted);
  font-size: 0.9rem;
}

.tasks-summary-grid strong {
  color: var(--agp-text);
}
</style>
