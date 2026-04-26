<template>
  <section class="agp-grid attempts-page">
    <header class="agp-card p-4 attempts-hero">
      <div>
        <p class="attempts-kicker mb-1">Разбор попыток</p>
        <h1 class="h3 mb-1">История попыток задачи</h1>
        <p class="text-muted mb-0">
          {{ game?.title || (canManage ? 'Разбор попыток учеников и ошибок выполнения.' : 'Ваши прошлые запуски и повторы.') }}
        </p>
      </div>
      <div class="attempts-hero-actions">
        <RouterLink v-if="game" :to="`/tasks/${game.game_id}/run`" class="btn btn-dark">К запуску задачи</RouterLink>
        <button class="btn btn-outline-secondary" :disabled="isLoading" @click="loadAttempts">
          {{ isLoading ? 'Обновление...' : 'Обновить' }}
        </button>
      </div>
    </header>

    <article v-if="isGameLoading" class="agp-card p-4">
      <div class="agp-loading-state agp-loading-state--compact">Загрузка игры...</div>
    </article>
    <article v-else-if="gameError" class="agp-card p-3 text-danger">{{ gameError }}</article>

    <article v-if="game" class="agp-card p-3 attempts-filter-panel">
      <div class="attempts-filter-copy">
        <div class="small text-muted text-uppercase fw-semibold">Фильтр</div>
        <div class="fw-semibold">Найдите нужный запуск по статусу и странице</div>
      </div>
      <div class="attempts-filter-grid">
        <div v-if="canManage">
          <label class="form-label small">Пользователь</label>
          <input v-model.trim="requestedBy" class="form-control mono" placeholder="Имя пользователя" />
        </div>
        <div>
          <label class="form-label small">Статус</label>
          <select v-model="statusFilter" class="form-select">
            <option value="">Любой</option>
            <option value="created">Создан</option>
            <option value="queued">В очереди</option>
            <option value="running">Выполняется</option>
            <option value="finished">Завершен</option>
            <option value="failed">Ошибка</option>
            <option value="timeout">Таймаут</option>
            <option value="canceled">Остановлен</option>
          </select>
        </div>
        <div>
          <label class="form-label small">Лимит</label>
          <input v-model.number="limit" class="form-control mono" type="number" min="5" max="100" />
        </div>
        <div class="attempts-filter-actions">
          <button class="btn btn-outline-secondary" @click="applyFilters">Применить</button>
          <button class="btn btn-outline-secondary" @click="resetFilters">Сбросить</button>
        </div>
      </div>
    </article>

    <article v-if="game" class="attempts-metrics" aria-label="Сводка попыток">
      <div class="agp-card-soft p-3 attempts-metric-card">
        <span>На странице</span>
        <strong class="mono">{{ attempts.length }}</strong>
      </div>
      <div class="agp-card-soft p-3 attempts-metric-card attempts-metric-card--solved">
        <span>Решено</span>
        <strong class="mono">{{ solvedCount }}</strong>
      </div>
      <div class="agp-card-soft p-3 attempts-metric-card attempts-metric-card--active">
        <span>В работе</span>
        <strong class="mono">{{ activeCount }}</strong>
      </div>
      <div class="agp-card-soft p-3 attempts-metric-card attempts-metric-card--score">
        <span>Лучший счет</span>
        <strong class="mono">{{ bestScore ?? '—' }}</strong>
      </div>
    </article>

    <article v-if="attemptsError" class="agp-card p-3 text-danger">{{ attemptsError }}</article>

    <article v-if="game" class="agp-card p-3">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h2 class="h6 mb-0">Попытки</h2>
        <div class="attempts-pager">
          <span class="small text-muted">страница {{ currentPage }}</span>
          <button class="btn btn-sm btn-outline-secondary" :disabled="isLoading || offset === 0" @click="prevPage">Назад</button>
          <button class="btn btn-sm btn-outline-secondary" :disabled="isLoading || attempts.length < normalizedLimit" @click="nextPage">Вперед</button>
        </div>
      </div>

      <div v-if="isLoading && attempts.length === 0" class="agp-loading-state agp-loading-state--compact">Загрузка попыток...</div>
      <div v-else-if="attempts.length === 0" class="agp-empty-state agp-empty-state--compact">Попытки не найдены.</div>
      <div v-else class="table-responsive">
        <table class="table table-sm align-middle mb-0 attempts-table">
          <thead>
            <tr>
              <th v-if="canManage">Пользователь</th>
              <th>Статус</th>
              <th v-if="canManage">Причина</th>
              <th>Счет</th>
              <th>Решено</th>
              <th>Время</th>
              <th v-if="canManage">Детали</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="attempt in attempts" :key="attempt.run_id">
              <td v-if="canManage" class="mono small">{{ attempt.requested_by }}</td>
              <td>
                <span class="attempt-status" :class="statusClass(attempt.status)">
                  {{ statusLabel(attempt.status) }}
                </span>
              </td>
              <td v-if="canManage"><RunReasonBadge :reason="attempt.error_message" /></td>
              <td class="mono small">{{ attemptScore(attempt) }}</td>
              <td>
                <span class="attempt-solved" :class="attemptSolvedClass(attempt)">
                  {{ attemptSolved(attempt) }}
                </span>
              </td>
              <td class="small">{{ formatIso(attempt.finished_at || attempt.created_at) }}</td>
              <td v-if="canManage">
                <details class="small">
                  <summary class="text-muted">Технический ID</summary>
                  <span class="mono small">{{ attempt.run_id }}</span>
                </details>
              </td>
              <td class="text-end d-flex gap-1 justify-content-end">
                <RouterLink :to="`/runs/${attempt.run_id}/watch`" class="btn btn-sm btn-outline-secondary">Повтор</RouterLink>
                <button
                  v-if="canManage"
                  class="btn btn-sm btn-outline-dark"
                  :disabled="logsLoadingRunId === attempt.run_id"
                  @click="showLogs(attempt.run_id)"
                >
                  {{ logsLoadingRunId === attempt.run_id ? '...' : 'Логи' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <section v-if="selectedLogs" class="attempts-log-panel mt-3">
        <div class="attempts-log-head mb-2">
          <div>
            <div class="fw-semibold">Логи попытки</div>
            <div v-if="selectedLogsRunId" class="small text-muted mono">{{ selectedLogsRunId }}</div>
          </div>
          <button class="btn btn-sm btn-outline-secondary" type="button" @click="closeLogs">Закрыть</button>
        </div>
        <pre class="mono small mb-0">{{ selectedLogs }}</pre>
      </section>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import RunReasonBadge from '../components/RunReasonBadge.vue';
import {
  getGame,
  getSingleTaskAttemptLogs,
  listSingleTaskAttempts,
  type GameDto,
  type RunDto,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const sessionStore = useSessionStore();

const game = ref<GameDto | null>(null);
const isGameLoading = ref(false);
const gameError = ref('');

const attempts = ref<RunDto[]>([]);
const attemptsError = ref('');
const isLoading = ref(false);

const requestedBy = ref('');
const statusFilter = ref<'' | 'created' | 'queued' | 'running' | 'finished' | 'failed' | 'timeout' | 'canceled'>('');
const limit = ref(20);
const offset = ref(0);

const selectedLogs = ref('');
const selectedLogsRunId = ref('');
const logsLoadingRunId = ref('');

const normalizedLimit = computed(() => Math.max(5, Math.min(100, Number(limit.value) || 20)));
const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const currentPage = computed(() => Math.floor(offset.value / normalizedLimit.value) + 1);

const solvedCount = computed(() => attempts.value.filter((attempt) => attemptSolved(attempt) === 'да').length);
const activeCount = computed(
  () => attempts.value.filter((attempt) => attempt.status === 'running' || attempt.status === 'queued').length
);
const bestScore = computed(() => {
  let best: number | null = null;
  for (const attempt of attempts.value) {
    const score = attemptScoreValue(attempt);
    if (score === null) continue;
    if (best === null || score > best) best = score;
  }
  return best;
});

function gameIdFromRoute(): string {
  return String(route.params.gameId || '').trim();
}

async function loadGame(): Promise<void> {
  const gameId = gameIdFromRoute();
  if (!gameId) {
    gameError.value = 'Не найдена задача для просмотра попыток';
    return;
  }
  isGameLoading.value = true;
  gameError.value = '';
  try {
    game.value = await getGame(gameId);
  } catch (error) {
    gameError.value = error instanceof Error ? error.message : 'Не удалось загрузить игру';
  } finally {
    isGameLoading.value = false;
  }
}

async function loadAttempts(): Promise<void> {
  const gameId = gameIdFromRoute();
  if (!gameId) return;
  isLoading.value = true;
  attemptsError.value = '';
  selectedLogs.value = '';
  selectedLogsRunId.value = '';
  try {
    attempts.value = await listSingleTaskAttempts({
      game_id: gameId,
      requested_by: requestedBy.value || undefined,
      status: statusFilter.value || undefined,
      limit: normalizedLimit.value,
      offset: offset.value,
    });
  } catch (error) {
    attemptsError.value = error instanceof Error ? error.message : 'Не удалось загрузить попытки';
  } finally {
    isLoading.value = false;
  }
}

async function applyFilters(): Promise<void> {
  offset.value = 0;
  await loadAttempts();
}

async function resetFilters(): Promise<void> {
  requestedBy.value = '';
  statusFilter.value = '';
  limit.value = 20;
  offset.value = 0;
  await loadAttempts();
}

async function nextPage(): Promise<void> {
  offset.value += normalizedLimit.value;
  await loadAttempts();
}

async function prevPage(): Promise<void> {
  offset.value = Math.max(0, offset.value - normalizedLimit.value);
  await loadAttempts();
}

async function showLogs(runId: string): Promise<void> {
  logsLoadingRunId.value = runId;
  selectedLogs.value = '';
  selectedLogsRunId.value = runId;
  try {
    const logs = await getSingleTaskAttemptLogs(runId);
    selectedLogs.value = logs.lines.length > 0 ? logs.lines.join('\n') : 'Логи отсутствуют';
  } catch (error) {
    selectedLogs.value = error instanceof Error ? error.message : 'Не удалось получить логи';
  } finally {
    logsLoadingRunId.value = '';
  }
}

function closeLogs(): void {
  selectedLogs.value = '';
  selectedLogsRunId.value = '';
}

function attemptScoreValue(run: RunDto): number | null {
  const payload = run.result_payload;
  if (!payload || typeof payload !== 'object') return null;
  const metrics = payload.metrics;
  if (!metrics || typeof metrics !== 'object') return null;
  const source = metrics as Record<string, unknown>;
  return typeof source.score === 'number' ? source.score : null;
}

function attemptScore(run: RunDto): string {
  const value = attemptScoreValue(run);
  return value === null ? '—' : String(value);
}

function attemptSolved(run: RunDto): string {
  const payload = run.result_payload;
  if (!payload || typeof payload !== 'object') return '—';
  const metrics = payload.metrics;
  if (!metrics || typeof metrics !== 'object') return '—';
  const source = metrics as Record<string, unknown>;
  if (typeof source.solved === 'boolean') return source.solved ? 'да' : 'нет';
  if (typeof source.reached_goal === 'boolean') return source.reached_goal ? 'да' : 'нет';
  if (typeof source.reached_exit === 'boolean') return source.reached_exit ? 'да' : 'нет';
  return '—';
}

function statusLabel(status: RunDto['status']): string {
  const labels: Record<RunDto['status'], string> = {
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

function statusClass(status: RunDto['status']): string {
  if (status === 'finished') return 'attempt-status--finished';
  if (status === 'running' || status === 'queued' || status === 'created') return 'attempt-status--active';
  if (status === 'failed' || status === 'timeout') return 'attempt-status--danger';
  return 'attempt-status--muted';
}

function attemptSolvedClass(run: RunDto): string {
  const solved = attemptSolved(run);
  if (solved === 'да') return 'attempt-solved--yes';
  if (solved === 'нет') return 'attempt-solved--no';
  return 'attempt-solved--unknown';
}

function formatIso(value: string): string {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleString('ru-RU');
}

onMounted(async () => {
  await loadGame();
  await loadAttempts();
});
</script>

<style scoped>
.attempts-page {
  gap: 0.9rem;
}

.attempts-hero {
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  background:
    radial-gradient(circle at 14% 18%, rgba(20, 184, 166, 0.18), transparent 15rem),
    radial-gradient(circle at 88% 12%, rgba(245, 158, 11, 0.14), transparent 13rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.9)),
    url("data:image/svg+xml,%3Csvg width='168' height='104' viewBox='0 0 168 104' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.13' stroke-width='2'%3E%3Cpath d='M20 24h28v28H20zM74 14h28v28H74zM124 34h26v26h-26zM48 70h28v20H48zM104 66h28v28h-28z'/%3E%3Cpath d='M48 38h26M102 28h22M76 80h28M88 42v24'/%3E%3C/g%3E%3C/svg%3E");
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.attempts-hero::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.25rem;
  background: linear-gradient(90deg, #14b8a6, #f59e0b, #2563eb);
}

.attempts-hero > * {
  position: relative;
}

.attempts-kicker {
  color: #0f766e;
  font-size: 0.76rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.attempts-hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
}

.attempts-filter-panel {
  display: grid;
  grid-template-columns: minmax(14rem, 0.8fr) minmax(0, 1.8fr);
  gap: 1rem;
  align-items: end;
}

.attempts-filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  gap: 0.75rem;
  align-items: end;
}

.attempts-filter-actions {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.attempts-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
}

.attempts-metric-card {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 0.1rem;
  border-color: rgba(148, 163, 184, 0.34);
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}

.attempts-metric-card::after {
  content: '';
  position: absolute;
  right: -1.25rem;
  bottom: -1.4rem;
  width: 4.6rem;
  height: 4.6rem;
  border-radius: 1.1rem;
  background: rgba(37, 99, 235, 0.08);
  transform: rotate(18deg);
}

.attempts-metric-card span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
  font-weight: 750;
}

.attempts-metric-card strong {
  color: var(--agp-text);
  font-size: 1.45rem;
}

.attempts-metric-card--solved::after {
  background: rgba(34, 197, 94, 0.12);
}

.attempts-metric-card--active::after {
  background: rgba(20, 184, 166, 0.12);
}

.attempts-metric-card--score::after {
  background: rgba(245, 158, 11, 0.16);
}

.attempts-pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.attempts-table {
  --bs-table-bg: transparent;
  --bs-table-striped-bg: rgba(248, 250, 252, 0.78);
  border-color: rgba(148, 163, 184, 0.24);
}

.attempts-table thead th {
  color: var(--agp-text-muted);
  font-size: 0.76rem;
  font-weight: 850;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.attempt-status,
.attempt-solved {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 0.16rem 0.55rem;
  font-size: 0.74rem;
  font-weight: 850;
  white-space: nowrap;
}

.attempt-status--finished,
.attempt-solved--yes {
  border-color: #86efac;
  background: #dcfce7;
  color: #166534;
}

.attempt-status--active {
  border-color: #99f6e4;
  background: #ccfbf1;
  color: #0f766e;
}

.attempt-status--danger,
.attempt-solved--no {
  border-color: #fecaca;
  background: #fef2f2;
  color: #991b1b;
}

.attempt-status--muted,
.attempt-solved--unknown {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #475569;
}

.attempts-log-panel {
  border: 1px solid var(--agp-border);
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.12), transparent 10rem),
    var(--agp-surface-soft);
  border-radius: 8px;
  padding: 0.85rem;
}

.attempts-log-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
}

.attempts-log-panel pre {
  max-height: 18rem;
  overflow: auto;
  white-space: pre-wrap;
}

@media (max-width: 1100px) {
  .attempts-filter-panel {
    grid-template-columns: 1fr;
  }

  .attempts-filter-grid,
  .attempts-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .attempts-hero {
    flex-direction: column;
  }

  .attempts-hero-actions {
    justify-content: flex-start;
    width: 100%;
  }

  .attempts-hero-actions .btn {
    flex: 1 1 12rem;
  }

  .attempts-filter-grid,
  .attempts-metrics {
    grid-template-columns: 1fr;
  }

  .attempts-filter-actions .btn {
    flex: 1 1 8rem;
  }
}
</style>
