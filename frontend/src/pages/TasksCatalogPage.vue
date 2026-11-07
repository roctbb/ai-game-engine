<template>
  <section class="agp-grid tasks-catalog-page">
    <header class="agp-page-heading tasks-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between gap-3">
        <div>
          <p class="tasks-kicker mb-1">Учебная карта</p>
          <h1 class="h3 mb-2">Задачи</h1>
          <p class="text-muted mb-0">{{ canManage ? 'Подберите задачи для занятия и проверьте примеры решений.' : 'Выберите тему, напишите стратегию и посмотрите, как работает ваш код.' }}</p>
          <div class="agp-page-actions">
            <RouterLink v-if="canManage" class="btn btn-primary" to="/admin/catalog">Управление задачами</RouterLink>
            <RouterLink v-else-if="resumeSection && !isLoading" class="btn btn-primary" :to="{ name: 'tasks-section', params: { section: resumeSection.name } }">{{ resumeSection.solved > 0 ? 'Продолжить обучение' : 'Начать обучение' }}</RouterLink>
          </div>
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
            <strong class="mono">{{ solvedSummary ? solvedByCurrentUserCount : '—' }}</strong>
          </div>
          <div>
            <span>Прогресс</span>
            <strong class="mono">{{ solvedSummary ? `${overallProgressPercent}%` : '—' }}</strong>
          </div>
        </div>
      </div>
    </header>

    <LoadingSkeleton v-if="isLoading" :count="12" label="Загрузка разделов…" />
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
          <span>{{ solvedSummary ? `${section.solved}/${section.total}` : section.total }} задач</span>
          <span>{{ section.isDone ? 'раздел решен' : section.solved > 0 ? 'продолжить' : 'начать' }}</span>
        </div>
      </RouterLink>
    </section>


  </section>
</template>

<script setup lang="ts">
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
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
const canManage = computed(() => sessionStore.role !== 'student');
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


const resumeSection = computed(() => sectionCards.value.find(section => section.solved > 0 && !section.isDone) ?? sectionCards.value.find(section => !section.isDone));

type SectionCard = {
  name: string;
  total: number;
  solved: number;
  percent: number;
  isDone: boolean;
  index: number;
};

function sectionStatusLabel(section: SectionCard): string {
  if (!solvedSummary.value) return 'нет данных';
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
    const [catalog, summary] = await Promise.allSettled([
      listSingleTaskCatalog(),
      getSingleTaskSolvedSummary(SOLVED_SUMMARY_LIMIT),
    ]);
    if (catalog.status === 'rejected') throw catalog.reason;
    tasks.value = catalog.value;
    solvedSummary.value = summary.status === 'fulfilled' ? summary.value : null;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить разделы задач';
  } finally {
    isLoading.value = false;
  }
});
</script>
