<template>
  <section class="agp-grid">
    <header class="d-flex justify-content-between align-items-start gap-3">
      <div>
        <h1 class="h3 mb-1">История попыток задачи</h1>
        <p class="text-muted mb-0">Фильтрация и быстрый разбор запусков `single_task`.</p>
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
        <div class="col-md-3">
          <label class="form-label small">Пользователь</label>
          <input v-model.trim="requestedBy" class="form-control mono" placeholder="nickname" />
        </div>
        <div class="col-md-3">
          <label class="form-label small">Статус</label>
          <select v-model="statusFilter" class="form-select mono">
            <option value="">Любой</option>
            <option value="created">created</option>
            <option value="queued">queued</option>
            <option value="running">running</option>
            <option value="finished">finished</option>
            <option value="failed">failed</option>
            <option value="timeout">timeout</option>
            <option value="canceled">canceled</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small">Лимит</label>
          <input v-model.number="limit" class="form-control mono" type="number" min="5" max="100" />
        </div>
        <div class="col-md-4 d-flex gap-2">
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
            <div class="small text-muted">Solved</div>
            <div class="mono">{{ solvedCount }}</div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="agp-card-soft p-2">
            <div class="small text-muted">Running/Queued</div>
            <div class="mono">{{ activeCount }}</div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="agp-card-soft p-2">
            <div class="small text-muted">Лучший score</div>
            <div class="mono">{{ bestScore ?? '—' }}</div>
          </div>
        </div>
      </div>
    </article>

    <article v-if="attemptsError" class="agp-card p-3 text-danger">{{ attemptsError }}</article>

    <article v-if="game" class="agp-card p-3">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h2 class="h6 mb-0">Попытки</h2>
        <div class="d-flex gap-2">
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
              <th>run_id</th>
              <th>Пользователь</th>
              <th>Статус</th>
              <th>Reason</th>
              <th>Score</th>
              <th>Solved</th>
              <th>Время</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="attempt in attempts" :key="attempt.run_id">
              <td class="mono small">{{ attempt.run_id }}</td>
              <td class="mono small">{{ attempt.requested_by }}</td>
              <td class="mono small">{{ attempt.status }}</td>
              <td><RunReasonBadge :reason="attempt.error_message" /></td>
              <td class="mono small">{{ attemptScore(attempt) }}</td>
              <td class="mono small">{{ attemptSolved(attempt) }}</td>
              <td class="small">{{ formatIso(attempt.finished_at || attempt.created_at) }}</td>
              <td class="text-end d-flex gap-1 justify-content-end">
                <RouterLink :to="`/runs/${attempt.run_id}/watch`" class="btn btn-sm btn-outline-secondary">Watch</RouterLink>
                <button
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

      <pre v-if="selectedLogs" class="mono small mt-3 mb-0">{{ selectedLogs }}</pre>
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

const route = useRoute();

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
const logsLoadingRunId = ref('');

const normalizedLimit = computed(() => Math.max(5, Math.min(100, Number(limit.value) || 20)));

const solvedCount = computed(() => attempts.value.filter((attempt) => attemptSolved(attempt) === 'yes').length);
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
    gameError.value = 'Не передан gameId';
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
  try {
    const logs = await getSingleTaskAttemptLogs(runId);
    selectedLogs.value = logs.lines.length > 0 ? logs.lines.join('\n') : 'Логи отсутствуют';
  } catch (error) {
    selectedLogs.value = error instanceof Error ? error.message : 'Не удалось получить логи';
  } finally {
    logsLoadingRunId.value = '';
  }
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
  if (typeof source.solved === 'boolean') return source.solved ? 'yes' : 'no';
  if (typeof source.reached_goal === 'boolean') return source.reached_goal ? 'yes' : 'no';
  if (typeof source.reached_exit === 'boolean') return source.reached_exit ? 'yes' : 'no';
  return '—';
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
