<template>
  <section class="agp-grid attempts-page">
    <header class="attempts-hero">
      <div>
        <h1 class="h3 mb-1">История попыток</h1>
        <p v-if="game" class="text-muted mb-0">
          {{ game.title }}
        </p>
      </div>
      <div class="attempts-hero-actions">
        <RouterLink v-if="game" :to="`/tasks/${game.game_id}`" class="btn btn-outline-secondary">К задаче</RouterLink>
        <button class="btn btn-outline-secondary" :disabled="isLoading" @click="loadAttempts">
          {{ isLoading ? 'Обновление...' : 'Обновить' }}
        </button>
      </div>
    </header>

    <LoadingSkeleton v-if="isGameLoading" :count="1" layout="list" label="Загрузка задачи…" />
    <article v-else-if="gameError" class="agp-card p-3 text-danger">{{ gameError }}</article>

    <article v-if="game" class="agp-card p-3 attempts-filter-panel">
      <div class="attempts-filter-grid">
        <div v-if="canManage" class="attempts-user-filter">
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

    <div v-if="game" class="attempts-summary" aria-label="Сводка попыток">
      <span>На странице <strong>{{ attempts.length }}</strong></span><span>Решено <strong>{{ solvedCount }}</strong></span><span>В работе <strong>{{ activeCount }}</strong></span><span>Лучший результат <strong>{{ bestScore ?? '—' }}</strong></span>
    </div>

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

      <LoadingSkeleton v-if="isLoading && attempts.length === 0" :count="3" layout="list" label="Загрузка попыток…" />
      <div v-else-if="attempts.length === 0" class="agp-empty-state agp-empty-state--compact">Попытки не найдены.</div>
      <template v-else>
      <div class="table-responsive attempts-desktop-list">
        <table class="table table-sm align-middle mb-0 attempts-table">
          <thead>
            <tr>
              <th aria-label="Результат"></th>
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
              <td class="arena-attempt-state"><span class="arena-status-icon" :class="attemptPresentation(attempt).tone" :title="attemptPresentation(attempt).label">{{ attemptPresentation(attempt).icon }}</span></td>
              <td v-if="canManage" class="small">{{ attempt.requested_by }}</td>
              <td>
                <span class="attempt-status" :class="attemptPresentation(attempt).tone === 'error' ? 'attempt-status--danger' : statusClass(attempt.status)">
                  {{ attemptPresentation(attempt).label }}
                </span>
              </td>
              <td v-if="canManage"><RunReasonBadge :reason="attempt.error_message" /></td>
              <td class="mono small">{{ attemptScore(attempt) }}</td>
              <td>
                <span class="attempt-solved" :class="attemptSolvedClass(attempt)">
                  {{ attemptSolved(attempt) }}
                </span>
              </td>
              <td class="small">{{ formatTime(attempt.finished_at || attempt.created_at) }}</td>
              <td v-if="canManage">
                <details class="small">
                  <summary class="text-muted">Технический ID</summary>
                  <span class="mono small">{{ attempt.run_id }}</span>
                </details>
              </td>
              <td class="text-end d-flex gap-1 justify-content-end">
                <RouterLink :to="attemptLink(attempt)" class="btn btn-sm btn-outline-secondary">Разобрать</RouterLink>
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
      <ol class="attempts-mobile-list">
        <li v-for="attempt in attempts" :key="attempt.run_id" class="attempts-mobile-row">
          <span class="arena-status-icon" :class="attemptPresentation(attempt).tone" aria-hidden="true">{{ attemptPresentation(attempt).icon }}</span>
          <div class="attempts-mobile-main">
            <strong v-if="canManage">{{ attempt.requested_by }}</strong>
            <time :datetime="attempt.finished_at || attempt.created_at">{{ formatTime(attempt.finished_at || attempt.created_at) }}</time>
            <span :class="attemptPresentation(attempt).tone === 'error' ? 'text-danger' : 'text-muted'">{{ attemptPresentation(attempt).label }}</span>
          </div>
          <div class="attempts-mobile-actions">
            <strong class="mono">{{ attemptScore(attempt) }}</strong>
            <RouterLink :to="attemptLink(attempt)" class="btn btn-sm btn-outline-secondary">Разобрать</RouterLink>
            <ActionMenu v-if="canManage" label="Действия попытки" :items="[{ id: 'logs', label: 'Логи', disabled: logsLoadingRunId === attempt.run_id }]" @select="showLogs(attempt.run_id)" />
          </div>
        </li>
      </ol>
      </template>

      <Teleport to="body">
      <div v-if="selectedLogs" class="attempts-log-overlay" @click.self="closeLogs">
      <section class="attempts-log-panel" role="dialog" aria-label="Логи попытки" v-dialog-focus="closeLogs">
        <div class="attempts-log-head mb-2">
          <div>
            <div class="fw-semibold">Логи попытки</div>
            <div v-if="selectedLogsRunId" class="small text-muted mono">{{ selectedLogsRunId }}</div>
          </div>
          <button class="btn btn-sm btn-outline-secondary" type="button" @click="closeLogs">Закрыть</button>
        </div>
        <pre class="mono small mb-0">{{ selectedLogs }}</pre>
      </section>
      </div>
      </Teleport>
    </article>
  </section>
</template>

<script setup lang="ts">
import { attemptPresentation, formatTime } from '../lib/attemptPresentation';
import ActionMenu from '../components/ActionMenu.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

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
const router = useRouter();
function attemptLink(attempt: RunDto) {
  return { name: 'task-run', params: { gameId: attempt.game_id }, query: { inspect_run: attempt.run_id, back: route.fullPath, attempt_user: requestedBy.value || undefined, attempt_offset: offset.value || undefined } };
}
const sessionStore = useSessionStore();

const game = ref<GameDto | null>(null);
const isGameLoading = ref(false);
const gameError = ref('');

const attempts = ref<RunDto[]>([]);
const attemptsError = ref('');
const isLoading = ref(false);

const requestedBy = ref(typeof route.query.requested_by === 'string' ? route.query.requested_by : '');
const statusFilter = ref<'' | 'created' | 'queued' | 'running' | 'finished' | 'failed' | 'timeout' | 'canceled'>(typeof route.query.status === 'string' && ['created','queued','running','finished','failed','timeout','canceled'].includes(route.query.status) ? route.query.status as RunDto['status'] : '');
const limit = ref(Math.min(100, Math.max(5, Number(route.query.limit) || 20)));
const offset = ref(Math.max(0, Number(route.query.offset) || 0));

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
  await router.replace({ query: { requested_by: requestedBy.value || undefined, status: statusFilter.value || undefined, limit: limit.value, offset: offset.value || undefined } });
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
  background: var(--agp-surface);
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.attempts-hero::before {
  content: none;
}

.attempts-hero > * {
  position: relative;
}


.attempts-hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
}

.attempts-filter-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  align-items: end;
}

.attempts-filter-grid {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(140px, 0.8fr) 90px auto;
  gap: 0.75rem;
  align-items: end;
}

.attempts-filter-actions {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
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
  border-color: var(--agp-border);
}

.attempts-table thead th {
  color: var(--agp-text-muted);
  font-size: 0.76rem;
  font-weight: 700;
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
  font-weight: 700;
  white-space: nowrap;
}

.attempt-status--finished,
.attempt-solved--yes {
  border-color: var(--agp-border);
  background: var(--arena-success-soft);
  color: var(--agp-success);
}

.attempt-status--active {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.attempt-status--danger,
.attempt-solved--no {
  border-color: var(--agp-border);
  background: var(--arena-error-soft);
  color: var(--agp-danger);
}

.attempt-status--muted,
.attempt-solved--unknown {
  border-color: var(--agp-border);
  background: var(--agp-surface-soft);
  color: var(--agp-text-muted);
}

.attempts-log-panel {
  border: 1px solid var(--agp-border);
  background: var(--agp-surface);
  border-radius: 8px;
  padding: 0.85rem;
  width: min(620px, 100%);
  color: var(--agp-text);
}
.attempts-log-overlay { position: fixed; inset: 0; z-index: 300; display: grid; place-items: center; padding: 16px; background: #10182766; }

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

  .attempts-filter-grid {
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
    flex: 1 1 0;
  }

  .attempts-filter-grid {
    grid-template-columns: minmax(0, 1fr) 88px;
  }
  .attempts-user-filter, .attempts-filter-actions { grid-column: 1 / -1; }

  .attempts-filter-actions .btn {
    flex: 1 1 8rem;
  }
}
.attempts-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 24px; font-size: 13px; color: var(--agp-text-muted); }
.attempts-summary strong { margin-left: 4px; color: var(--agp-text); font-variant-numeric: tabular-nums; font-weight: 500; }
.attempts-hero { padding-block: 0 8px; align-items: flex-start; background: transparent; }
.attempts-hero h1 { margin-bottom: 4px !important; }
.attempts-mobile-list { display: none; }
@media (max-width: 767px) {
  .attempts-desktop-list { display: none; }
  .attempts-mobile-list { display: grid; list-style: none; margin: 0; padding: 0; }
  .attempts-mobile-row { display: grid; grid-template-columns: 20px minmax(0, 1fr) auto; align-items: start; gap: 8px; padding: 12px 0; border-top: 1px solid var(--agp-border); }
  .attempts-mobile-main { display: grid; gap: 4px; min-width: 0; overflow-wrap: anywhere; font-size: 13px; }
  .attempts-mobile-main strong { font-weight: 500; }
  .attempts-mobile-main time { color: var(--agp-text-muted); font-size: 12px; }
  .attempts-mobile-actions { display: grid; grid-template-columns: auto auto; align-items: center; justify-content: end; gap: 4px 8px; }
  .attempts-mobile-actions strong { grid-column: 1 / -1; text-align: right; font-size: 13px; }
}
</style>
