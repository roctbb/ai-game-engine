<template>
  <section class="agp-grid">
    <header class="d-flex justify-content-between align-items-start gap-3">
      <div>
        <h1 class="h3 mb-1">История попыток задачи</h1>
        <p class="text-muted mb-0">
          {{ canManage ? 'Разбор попыток учеников и ошибок выполнения.' : 'Ваши прошлые запуски и повторы.' }}
        </p>
      </div>
      <div class="d-flex gap-2">
        <RouterLink v-if="game" :to="`/tasks/${game.game_id}/run`" class="btn btn-outline-dark">К запуску задачи</RouterLink>
        <button class="btn btn-outline-secondary" :disabled="isLoading" @click="loadAttempts">{{ isLoading ? 'Обновление...' : 'Обновить' }}</button>
      </div>
    </header>

    <article v-if="isGameLoading" class="agp-card p-3 text-muted">Загрузка игры...</article>
    <article v-else-if="gameError" class="agp-card p-3 text-danger">{{ gameError }}</article>

    <article v-if="game" class="agp-card p-3">
      <div class="row g-2 align-items-end">
        <div v-if="canManage" class="col-md-3">
          <label class="form-label small">Пользователь</label>
          <input v-model.trim="requestedBy" class="form-control mono" placeholder="Имя пользователя" />
        </div>
        <div :class="canManage ? 'col-md-3' : 'col-md-4'">
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
        <div :class="canManage ? 'col-md-2' : 'col-md-3'">
          <label class="form-label small">Лимит</label>
          <input v-model.number="limit" class="form-control mono" type="number" min="5" max="100" />
        </div>
        <div :class="canManage ? 'col-md-4' : 'col-md-5'" class="d-flex gap-2">
          <button class="btn btn-outline-secondary" @click="applyFilters">Применить</button>
          <button class="btn btn-outline-secondary" @click="resetFilters">Сбросить</button>
        </div>
      </div>
    </article>

    <article v-if="game" class="agp-card p-3">
      <div class="row g-2">
        <div class="col-md-3">
          <div class="agp-card-soft p-2">
            <div class="small text-muted">Всего на странице</div>
            <div class="mono">{{ attempts.length }}</div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="agp-card-soft p-2">
            <div class="small text-muted">Решено</div>
            <div class="mono">{{ solvedCount }}</div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="agp-card-soft p-2">
            <div class="small text-muted">В работе</div>
            <div class="mono">{{ activeCount }}</div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="agp-card-soft p-2">
            <div class="small text-muted">Лучший счет</div>
            <div class="mono">{{ bestScore ?? '—' }}</div>
          </div>
        </div>
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

      <div v-if="isLoading && attempts.length === 0" class="small text-muted">Загрузка попыток...</div>
      <div v-else-if="attempts.length === 0" class="small text-muted">Попытки не найдены.</div>
      <div v-else class="table-responsive">
        <table class="table table-sm align-middle mb-0">
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
              <td>{{ statusLabel(attempt.status) }}</td>
              <td v-if="canManage"><RunReasonBadge :reason="attempt.error_message" /></td>
              <td class="mono small">{{ attemptScore(attempt) }}</td>
              <td>{{ attemptSolved(attempt) }}</td>
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
.attempts-pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.attempts-log-panel {
  border: 1px solid var(--agp-border);
  background: var(--agp-surface-soft);
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
</style>
