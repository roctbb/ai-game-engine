<template>
  <section class="agp-grid">
    <header class="agp-card replay-catalog-head">
      <div>
        <p class="replay-catalog-kicker mb-1">Архив матчей</p>
        <h1 class="h3 mb-1">Каталог повторов</h1>
        <p class="mb-0">
          Повторы завершенных запусков для преподавателя и администратора.
        </p>
      </div>
      <button v-if="canManage" class="btn btn-outline-dark" :disabled="isLoading" @click="refreshReplays">
        {{ isLoading ? 'Обновление...' : 'Обновить' }}
      </button>
    </header>

    <article v-if="!canManage" class="agp-card p-4">
      <div class="agp-empty-state">
      Каталог повторов доступен только преподавателю или администратору.
      </div>
    </article>

    <article v-if="canManage" class="agp-card p-3 replay-filter-card">
      <div class="row g-2">
        <div class="col-md-3">
          <label class="form-label small">Игра</label>
          <select v-model="gameIdFilter" class="form-select">
            <option value="">Все игры</option>
            <option v-for="game in games" :key="game.game_id" :value="game.game_id">
              {{ game.title }}
            </option>
          </select>
        </div>
        <div class="col-md-3">
          <label class="form-label small">Тип</label>
          <select v-model="runKindFilter" class="form-select">
            <option value="">Любой</option>
            <option value="single_task">Задача</option>
            <option value="training_match">Лобби</option>
            <option value="competition_match">Соревнование</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small">Лимит</label>
          <input v-model.number="limitFilter" min="1" max="200" class="form-control mono" type="number" />
        </div>
        <div class="col-md-4">
          <label class="form-label small">Поиск по повтору</label>
          <input v-model.trim="runIdQuery" class="form-control" placeholder="Игра, статус или часть ссылки" />
        </div>
      </div>
    </article>

    <div v-if="canManage && hasActiveFilters" class="replay-active-filter-line">
      <span>Фильтр:</span>
      <strong>{{ activeFilterSummary }}</strong>
      <button class="btn btn-sm btn-link p-0" type="button" @click="resetFilters">Сбросить</button>
    </div>

    <article v-if="canManage && errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <article v-if="canManage" class="agp-card p-3 replay-results-card">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h2 class="h6 mb-0">Результаты</h2>
        <div class="replay-results-meta">
          <label class="small text-muted d-flex align-items-center gap-1 mb-0">
            <input v-model="isAutoRefreshEnabled" class="form-check-input m-0" type="checkbox" />
            автообновление
          </label>
          <span class="small text-muted">Показано: <span class="mono">{{ filteredReplays.length }}</span></span>
          <span v-if="lastUpdatedAt" class="small text-muted">обновлено: {{ formatIso(lastUpdatedAt) }}</span>
        </div>
      </div>
      <div v-if="isLoading" class="agp-loading-state agp-loading-state--compact">Загрузка повторов...</div>
      <div v-else class="table-responsive">
        <table class="table align-middle mb-0 replay-table">
          <thead>
            <tr>
              <th>Игра</th>
              <th>Тип и статус</th>
              <th>Данные повтора</th>
              <th>Обновлено</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredReplays" :key="item.replay_id">
              <td>
                <div class="replay-row-title">
                  <strong>{{ gameTitle(item.game_id) }}</strong>
                  <span class="mono">{{ item.run_id }}</span>
                </div>
                <details class="small mt-1">
                  <summary class="text-muted">Технические детали</summary>
                  <div class="mono small mt-1">игра: {{ item.game_id }}</div>
                  <div class="mono small">запуск: {{ item.run_id }}</div>
                  <div class="mono small">повтор: {{ item.replay_id }}</div>
                </details>
              </td>
              <td>
                <div class="replay-kind-line">
                  <span class="replay-kind-pill">{{ runKindLabel(item.run_kind) }}</span>
                  <span class="agp-pill" :class="statusToneClass(item.status)">{{ statusLabel(item.status) }}</span>
                </div>
              </td>
              <td class="small">
                <div class="replay-metrics">
                  <span class="replay-metric-pill"><strong>{{ item.frames.length }}</strong> кадров</span>
                  <span class="replay-metric-pill"><strong>{{ item.events.length }}</strong> событий</span>
                </div>
              </td>
              <td class="mono small">{{ formatIso(item.updated_at) }}</td>
              <td class="text-end">
                <RouterLink :to="`/runs/${item.run_id}/watch`" class="btn btn-sm btn-outline-secondary">Открыть</RouterLink>
              </td>
            </tr>
            <tr v-if="filteredReplays.length === 0">
              <td colspan="5">
                <div class="agp-empty-state agp-empty-state--compact">{{ emptyStateText }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import { listGames, listReplays, type GameDto, type ReplayDto } from '../lib/api';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const sessionStore = useSessionStore();

const games = ref<GameDto[]>([]);
const replays = ref<ReplayDto[]>([]);
const isLoading = ref(false);
const lastUpdatedAt = ref('');
const isAutoRefreshEnabled = ref(true);
const errorMessage = ref('');

const gameIdFilter = ref('');
const runKindFilter = ref<'single_task' | 'training_match' | 'competition_match' | ''>('');
const limitFilter = ref(50);
const runIdQuery = ref('');
const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const normalizedLimit = computed(() => Math.max(1, Math.min(200, Number(limitFilter.value) || 50)));
let autoRefreshHandle: ReturnType<typeof setInterval> | null = null;

const filteredReplays = computed(() => {
  const query = runIdQuery.value.toLowerCase();
  if (!query) return replays.value;
  return replays.value.filter((item) =>
    [
      item.run_id,
      item.replay_id,
      item.game_id,
      gameTitle(item.game_id),
      runKindLabel(item.run_kind),
      statusLabel(item.status),
    ]
      .join(' ')
      .toLowerCase()
      .includes(query)
  );
});
const hasActiveFilters = computed(() => Boolean(gameIdFilter.value || runKindFilter.value || runIdQuery.value || normalizedLimit.value !== 50));
const activeFilterSummary = computed(() => {
  const parts: string[] = [];
  if (gameIdFilter.value) parts.push(`игра: ${gameTitle(gameIdFilter.value)}`);
  if (runKindFilter.value) parts.push(`тип: ${runKindLabel(runKindFilter.value)}`);
  if (runIdQuery.value) parts.push(`поиск: ${runIdQuery.value}`);
  if (normalizedLimit.value !== 50) parts.push(`лимит: ${normalizedLimit.value}`);
  return parts.join(' · ');
});
const emptyStateText = computed(() =>
  replays.value.length === 0
    ? 'Повторов пока нет.'
    : 'Повторы по текущим фильтрам не найдены.'
);

function applyFiltersFromQuery(): void {
  const gameQuery = route.query.game_id;
  if (typeof gameQuery === 'string' && gameQuery.trim()) {
    gameIdFilter.value = gameQuery.trim();
  }

  const runKindQuery = route.query.run_kind;
  if (
    runKindQuery === 'single_task' ||
    runKindQuery === 'training_match' ||
    runKindQuery === 'competition_match'
  ) {
    runKindFilter.value = runKindQuery;
  }

  const limitQuery = route.query.limit;
  if (typeof limitQuery === 'string') {
    const parsed = Number(limitQuery);
    if (Number.isFinite(parsed)) {
      limitFilter.value = Math.max(1, Math.min(200, parsed));
    }
  }

  const runIdQueryRaw = route.query.run_id;
  if (typeof runIdQueryRaw === 'string' && runIdQueryRaw.trim()) {
    runIdQuery.value = runIdQueryRaw.trim();
  }
}

function gameTitle(gameId: string): string {
  const item = games.value.find((game) => game.game_id === gameId);
  return item?.title ?? gameId;
}

function runKindLabel(kind: ReplayDto['run_kind']): string {
  const labels: Record<ReplayDto['run_kind'], string> = {
    single_task: 'Задача',
    training_match: 'Лобби',
    competition_match: 'Соревнование',
  };
  return labels[kind] ?? kind;
}

function statusLabel(status: ReplayDto['status']): string {
  const labels: Record<ReplayDto['status'], string> = {
    created: 'Создан',
    queued: 'В очереди',
    running: 'Выполняется',
    finished: 'Завершен',
    failed: 'Ошибка',
    timeout: 'Таймаут',
    canceled: 'Остановлен',
  };
  return labels[status] ?? status;
}

function statusToneClass(status: ReplayDto['status']): string {
  if (status === 'finished') return 'agp-pill--success';
  if (status === 'queued' || status === 'running') return 'agp-pill--warning';
  if (status === 'failed' || status === 'timeout' || status === 'canceled') return 'agp-pill--danger';
  return 'agp-pill--neutral';
}

function formatIso(value: string): string {
  const time = Date.parse(value);
  if (Number.isNaN(time)) return value;
  return new Date(time).toLocaleString('ru-RU');
}

function resetFilters(): void {
  gameIdFilter.value = '';
  runKindFilter.value = '';
  limitFilter.value = 50;
  runIdQuery.value = '';
}

async function loadReplays(options: { silent?: boolean } = {}): Promise<void> {
  if (!canManage.value) return;
  if (!options.silent) {
    isLoading.value = true;
    errorMessage.value = '';
  }
  try {
    replays.value = await listReplays({
      game_id: gameIdFilter.value || undefined,
      run_kind: runKindFilter.value || undefined,
      limit: normalizedLimit.value,
    });
    lastUpdatedAt.value = new Date().toISOString();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить каталог повторов';
  } finally {
    if (!options.silent) {
      isLoading.value = false;
    }
  }
}

async function refreshReplays(): Promise<void> {
  await loadReplays();
}

function startAutoRefresh(): void {
  stopAutoRefresh();
  if (!canManage.value || !isAutoRefreshEnabled.value) return;
  autoRefreshHandle = setInterval(() => {
    void loadReplays({ silent: true });
  }, 15000);
}

function stopAutoRefresh(): void {
  if (autoRefreshHandle) {
    clearInterval(autoRefreshHandle);
    autoRefreshHandle = null;
  }
}

watch([gameIdFilter, runKindFilter, limitFilter], () => {
  void loadReplays();
});

watch(isAutoRefreshEnabled, () => {
  startAutoRefresh();
});

onMounted(async () => {
  if (!canManage.value) return;
  applyFiltersFromQuery();
  try {
    games.value = await listGames();
  } catch {
    // Каталог игр не блокирует отображение таблицы повторов.
  }
  await loadReplays();
  startAutoRefresh();
});

onUnmounted(() => {
  stopAutoRefresh();
});
</script>

<style scoped>
.replay-catalog-head {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
  background:
    url("data:image/svg+xml,%3Csvg width='160' height='96' viewBox='0 0 160 96' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23ffffff' stroke-opacity='.32' stroke-width='2'%3E%3Cpath d='M18 18h26v26H18zM116 18h26v26h-26zM67 52h26v26H67z'/%3E%3Cpath d='M44 31h23M93 65h23M80 0v26M80 70v26'/%3E%3C/g%3E%3C/svg%3E") right 1rem center / 13rem auto no-repeat,
    linear-gradient(135deg, #0f766e 0%, #2563eb 58%, #f59e0b 100%);
  color: #f8fbff;
}

.replay-catalog-head h1,
.replay-catalog-head p {
  position: relative;
  z-index: 1;
}

.replay-catalog-head p {
  color: rgba(248, 251, 255, 0.78);
}

.replay-catalog-kicker {
  color: rgba(204, 251, 241, 0.9) !important;
  font-size: 0.76rem;
  font-weight: 900;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.replay-catalog-head .btn {
  position: relative;
  z-index: 1;
  border-color: rgba(255, 255, 255, 0.52);
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
  backdrop-filter: blur(8px);
}

.replay-filter-card,
.replay-results-card {
  position: relative;
  overflow: hidden;
}

.replay-filter-card::before,
.replay-results-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.18rem;
  background: linear-gradient(90deg, #14b8a6, #2563eb, #f59e0b);
  opacity: 0.72;
}

.replay-active-filter-line {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  flex-wrap: wrap;
  color: var(--agp-text-muted);
  font-size: 0.86rem;
}

.replay-active-filter-line strong {
  color: var(--agp-text);
  font-weight: 600;
}

.replay-results-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.replay-table {
  --bs-table-bg: transparent;
  --bs-table-hover-bg: rgba(20, 184, 166, 0.06);
}

.replay-table thead th {
  color: var(--agp-text-muted);
  font-size: 0.76rem;
  font-weight: 900;
  text-transform: uppercase;
}

.replay-table tbody tr {
  border-color: rgba(148, 163, 184, 0.24);
}

.replay-row-title {
  display: grid;
  gap: 0.18rem;
}

.replay-row-title strong {
  font-size: 0.96rem;
}

.replay-row-title .mono {
  color: var(--agp-text-muted);
  font-size: 0.76rem;
}

.replay-kind-line,
.replay-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 0.38rem;
  align-items: center;
}

.replay-kind-pill,
.replay-metric-pill {
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--agp-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
  line-height: 1.2;
  padding: 0.28rem 0.58rem;
}

.replay-metric-pill strong {
  color: var(--agp-primary);
}

@media (max-width: 720px) {
  .replay-catalog-head {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
