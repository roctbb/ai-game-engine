<template>
  <section class="agp-grid tasks-catalog-page">
    <header class="agp-card p-4 tasks-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between gap-3">
        <div>
          <p class="tasks-kicker mb-1">Учебная карта</p>
          <h1 class="h3 mb-2">Задачи</h1>
          <p class="text-muted mb-0">
            Сначала выберите учебный раздел, затем откройте список задач внутри него.
          </p>
        </div>
        <div class="tasks-head-stats" aria-label="Сводка каталога задач">
          <div>
            <span>Разделов</span>
            <strong class="mono">{{ sectionCards.length }}</strong>
          </div>
          <div>
            <span>Задач</span>
            <strong class="mono">{{ tasks.length }}</strong>
          </div>
          <div>
            <span>Решено</span>
            <strong class="mono">{{ solvedByCurrentUserCount }}</strong>
          </div>
          <div>
            <span>Прогресс</span>
            <strong class="mono">{{ overallProgressPercent }}%</strong>
          </div>
        </div>
      </div>
    </header>

    <article v-if="isLoading" class="agp-card p-4">
      <div class="agp-loading-state agp-loading-state--compact">Загрузка разделов...</div>
    </article>
    <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>
    <article v-else-if="tasks.length === 0" class="agp-card p-4">
      <div class="agp-empty-state">Задачи пока не опубликованы.</div>
    </article>

    <section v-else class="section-card-grid" aria-label="Разделы задач">
      <RouterLink
        v-for="section in sectionCards"
        :key="section.name"
        class="agp-card p-3 section-card"
        :class="{
          'section-card--done': section.isDone,
          'section-card--started': section.solved > 0 && !section.isDone,
        }"
        :to="{ name: 'tasks-section', params: { section: section.name } }"
      >
        <div class="section-card-top">
          <span class="section-index mono">{{ section.index }}</span>
          <span class="section-status" :class="sectionStatusClass(section)">
            {{ sectionStatusLabel(section) }}
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
          <span>{{ section.solved }}/{{ section.total }} задач</span>
          <span>{{ section.isDone ? 'раздел решен' : section.solved > 0 ? 'продолжить' : 'начать' }}</span>
        </div>
      </RouterLink>
    </section>

    <aside v-if="!isLoading && !errorMessage" class="agp-card p-3 tasks-summary">
      <div class="d-flex justify-content-between align-items-start gap-3 mb-2">
        <div>
          <p class="tasks-kicker mb-1">Путь игрока</p>
          <h2 class="h6 mb-0">Ваш прогресс</h2>
        </div>
        <strong class="tasks-summary-percent mono">{{ overallProgressPercent }}%</strong>
      </div>
      <div
        class="tasks-summary-progress"
        role="progressbar"
        :aria-valuenow="overallProgressPercent"
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <i :style="{ width: `${overallProgressPercent}%` }"></i>
      </div>
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
const overallProgressPercent = computed(() =>
  tasks.value.length > 0 ? Math.round((solvedByCurrentUserCount.value / tasks.value.length) * 100) : 0
);

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
        order: sectionOrder(name),
      };
    })
    .sort((left, right) => left.order - right.order || left.name.localeCompare(right.name, 'ru'))
    .map(({ order: _order, ...section }, index) => ({
      ...section,
      index: index + 1,
    }));
});

const completedSectionCount = computed(() => sectionCards.value.filter((section) => section.isDone).length);

type SectionCard = {
  name: string;
  total: number;
  solved: number;
  percent: number;
  isDone: boolean;
  index: number;
};

function sectionStatusLabel(section: SectionCard): string {
  if (section.isDone) return 'готово';
  if (section.solved > 0) return 'в процессе';
  return 'старт';
}

function sectionStatusClass(section: SectionCard): string {
  if (section.isDone) return 'section-status--done';
  if (section.solved > 0) return 'section-status--started';
  return 'section-status--idle';
}

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
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 12% 20%, rgba(245, 158, 11, 0.18), transparent 16rem),
    radial-gradient(circle at 88% 10%, rgba(37, 99, 235, 0.14), transparent 16rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(255, 251, 235, 0.88)),
    url("data:image/svg+xml,%3Csvg width='180' height='112' viewBox='0 0 180 112' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.13' stroke-width='2'%3E%3Cpath d='M18 28h28v28H18zM76 18h28v28H76zM132 36h28v28h-28zM48 72h28v28H48zM106 68h28v28h-28z'/%3E%3Cpath d='M46 42h30M104 32h28M76 86h30M90 46v22'/%3E%3C/g%3E%3C/svg%3E");
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.tasks-head::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.25rem;
  background: linear-gradient(90deg, #f59e0b, #14b8a6, #2563eb);
}

.tasks-head > * {
  position: relative;
}

.tasks-kicker {
  color: #0f766e;
  font-size: 0.76rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.tasks-head-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(5.5rem, 1fr));
  gap: 0.55rem;
  min-width: min(100%, 28rem);
}

.tasks-head-stats div {
  display: grid;
  gap: 0.05rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 0.85rem;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.tasks-head-stats span {
  color: var(--agp-text-muted);
  font-size: 0.72rem;
  font-weight: 750;
}

.tasks-head-stats strong {
  color: var(--agp-text);
  font-size: 1.18rem;
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

.section-card--started {
  border-color: rgba(20, 184, 166, 0.4);
  background:
    radial-gradient(circle at 86% 14%, rgba(20, 184, 166, 0.14), transparent 11rem),
    linear-gradient(180deg, #f0fdfa 0%, #ffffff 100%);
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

.section-card--started .section-index {
  background: #ccfbf1;
  color: #0f766e;
}

.section-status {
  width: fit-content;
  border-radius: 999px;
  border: 1px solid transparent;
  padding: 0.18rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 850;
  text-transform: uppercase;
}

.section-status--done {
  border-color: #86efac;
  background: #dcfce7;
  color: #166534;
}

.section-status--started {
  border-color: #99f6e4;
  background: #ccfbf1;
  color: #0f766e;
}

.section-status--idle {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #9a3412;
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
  position: relative;
  overflow: hidden;
  max-width: 36rem;
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.14), transparent 11rem),
    linear-gradient(180deg, #ffffff, #f8fafc);
}

.tasks-summary::before {
  content: '';
  position: absolute;
  right: -2.5rem;
  bottom: -2.75rem;
  width: 9rem;
  height: 9rem;
  border-radius: 2rem;
  transform: rotate(18deg);
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(20, 184, 166, 0.11)),
    url("data:image/svg+xml,%3Csvg width='96' height='96' viewBox='0 0 96 96' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2314b8a6' stroke-opacity='.35' stroke-width='2'%3E%3Cpath d='M18 48h60M48 18v60M30 30h36v36H30z'/%3E%3C/g%3E%3C/svg%3E");
  pointer-events: none;
}

.tasks-summary > * {
  position: relative;
}

.tasks-summary-percent {
  color: #0f766e;
  font-size: 1.15rem;
}

.tasks-summary-progress {
  height: 0.55rem;
  overflow: hidden;
  border-radius: 999px;
  background: #dbeafe;
  margin-bottom: 0.75rem;
}

.tasks-summary-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #14b8a6, #f59e0b);
  transition: width 0.2s ease;
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

@media (max-width: 900px) {
  .tasks-head-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    min-width: 0;
  }
}

@media (max-width: 560px) {
  .tasks-head-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 360px) {
  .tasks-head-stats {
    grid-template-columns: 1fr;
  }
}
</style>
