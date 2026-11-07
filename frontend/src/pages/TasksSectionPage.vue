<template>
  <section class="agp-grid tasks-catalog-page">
    <header class="agp-page-heading tasks-head">
      <div class="d-flex flex-column flex-lg-row justify-content-between gap-3">
        <div>
          <div class="mb-2">
            <RouterLink class="btn btn-sm btn-outline-secondary" to="/tasks">Все разделы</RouterLink>
          </div>
          <p class="tasks-kicker mb-1">Раздел задач</p>
          <h1 class="h3 mb-2">{{ routeSection }}</h1>
          <p class="text-muted mb-0">
            {{ sectionDescription(routeSection) }}
          </p>
        </div>
        <div class="tasks-head-stats" aria-label="Сводка раздела">
          <div>
            <span>Показано</span>
            <strong class="mono">{{ filteredTasks.length }}/{{ sectionTasks.length }}</strong>
          </div>
          <div>
            <span>Решено</span>
            <strong class="mono">{{ sectionSolvedCount }}</strong>
          </div>
          <div>
            <span>Тем</span>
            <strong class="mono">{{ topicOptions.length }}</strong>
          </div>
          <div>
            <span>Прогресс</span>
            <strong class="mono">{{ sectionProgressPercent }}%</strong>
          </div>
        </div>
      </div>
    </header>

    <section class="agp-card p-3 tasks-filter-panel" aria-label="Фильтры задач">
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
        <LoadingSkeleton v-if="isLoading" :count="4" layout="list" label="Загрузка задач…" />
        <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>
        <article v-else-if="tasks.length === 0" class="agp-card p-4">
          <div class="agp-empty-state">Задачи пока не опубликованы.</div>
        </article>
        <article v-else-if="sectionTasks.length === 0" class="agp-card p-4">
          <div class="agp-empty-state">В этом разделе задач нет.</div>
        </article>
        <article v-else-if="filteredTasks.length === 0" class="agp-card p-4">
          <div class="agp-empty-state">По выбранным фильтрам задач нет. Сбросьте фильтры или выберите другой тег.</div>
        </article>

        <div v-else class="tasks-list">
          <section v-for="group in groupedFilteredTasks" :key="group.key" class="tasks-group">
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
                  <RouterLink :to="{ name: 'task-run', params: { gameId: task.game_id }, query: { from: route.fullPath } }" class="btn btn-primary btn-sm w-100">
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
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

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
const router = useRouter();
const tasks = ref<SingleTaskCatalogItemDto[]>([]);
const solvedSummary = ref<SingleTaskSolvedSummaryDto | null>(null);
const isLoading = ref(false);
const errorMessage = ref('');
const summaryError = ref('');
const selectedTopic = ref(typeof route.query.topic === 'string' ? route.query.topic : '');
const selectedDifficulty = ref(typeof route.query.difficulty === 'string' ? route.query.difficulty : '');
const selectedProgress = ref<'all' | 'solved' | 'unsolved'>(route.query.progress === 'solved' || route.query.progress === 'unsolved' ? route.query.progress : 'all');
watch([selectedTopic, selectedDifficulty, selectedProgress], ([topic, difficulty, progress]) => {
  void router.replace({ query: { ...route.query, topic: topic || undefined, difficulty: difficulty || undefined, progress: progress === 'all' ? undefined : progress } });
});
watch(() => route.query, (query) => {
  selectedTopic.value = typeof query.topic === 'string' ? query.topic : '';
  selectedDifficulty.value = typeof query.difficulty === 'string' ? query.difficulty : '';
  selectedProgress.value = query.progress === 'solved' || query.progress === 'unsolved' ? query.progress : 'all';
});

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
  const [catalog, summary] = await Promise.allSettled([
    listSingleTaskCatalog(), getSingleTaskSolvedSummary(SOLVED_SUMMARY_LIMIT),
  ]);
  if (catalog.status === 'fulfilled') tasks.value = catalog.value;
  else errorMessage.value = catalog.reason instanceof Error ? catalog.reason.message : 'Не удалось загрузить каталог задач';
  if (summary.status === 'fulfilled') solvedSummary.value = summary.value;
  else summaryError.value = 'Прогресс пока недоступен. Попробуйте обновить страницу.';
  isLoading.value = false;
});
</script>
