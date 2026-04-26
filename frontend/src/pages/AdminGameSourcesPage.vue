<template>
  <section class="agp-grid admin-sources-page">
    <header class="agp-card p-4 admin-sources-hero">
      <div>
        <p class="admin-sources-kicker mb-1">{{ canManageWorkers ? 'Системный контур' : 'Библиотека игр' }}</p>
        <h1 class="h3 mb-1">{{ pageTitle }}</h1>
        <p class="text-muted mb-0">
          {{ pageSubtitle }}
        </p>
      </div>
      <div class="d-flex gap-2 align-items-center">
        <span v-if="syncingSourcesCount > 0" class="admin-source-status admin-source-status--syncing">
          Синхронизация: {{ syncingSourcesCount }}
        </span>
        <button
          class="btn btn-sm btn-outline-secondary"
          :disabled="isLoading || !canManageSources"
          @click="loadSources()"
        >
          Обновить
        </button>
      </div>
    </header>

    <article class="agp-card p-3 agp-status-card" v-if="syncingSourcesCount > 0">
      <div class="d-flex align-items-center gap-2">
        <span class="spinner-border spinner-border-sm" aria-hidden="true"></span>
        <div class="fw-semibold">Есть активные синхронизации</div>
      </div>
      <div class="small text-muted mt-1">
        Страница автоматически обновляет статусы каждые {{ pollingIntervalSeconds }} сек.
      </div>
    </article>

    <article class="agp-card p-3" v-if="!canManageSources">
      <div class="agp-empty-state agp-empty-state--compact">
        Требуется роль преподавателя или администратора. Для текущего пользователя действия создания и синхронизации источников недоступны.
      </div>
    </article>

    <article v-if="canManageSources" class="agp-card p-3 admin-source-create-card">
      <h2 class="h6">Добавить игру из Git</h2>
      <p class="small text-muted mb-3">
        После добавления источник можно синхронизировать вручную. Новые игры появятся в разделе «Игры» после успешной сборки.
      </p>
      <div class="admin-source-create-grid">
        <div>
          <label class="form-label small">Репозиторий</label>
          <input v-model.trim="repoUrl" class="form-control mono" placeholder="https://github.com/org/repo" />
        </div>
        <div>
          <label class="form-label small">Ветка</label>
          <input v-model.trim="defaultBranch" class="form-control mono" />
        </div>
        <div>
          <button
            class="btn btn-dark w-100"
            :disabled="!canManageSources || isCreating || !repoUrl || !defaultBranch"
            @click="createSource"
          >
            {{ isCreating ? 'Создание...' : 'Добавить' }}
          </button>
        </div>
      </div>
    </article>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">
      {{ errorMessage }}
    </article>

    <div class="agp-grid agp-grid--2">
      <article class="agp-card p-3">
        <h2 class="h6">Источники игр</h2>
        <div v-if="isLoading" class="agp-loading-state agp-loading-state--compact">Загрузка источников...</div>
        <div v-else class="table-responsive">
          <table class="table align-middle mb-0 admin-source-table">
            <thead>
              <tr>
                <th>Репозиторий</th>
                <th>Ветка</th>
                <th>Состояние</th>
                <th>Синхронизация</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="source in sources"
                :key="source.source_id"
                :class="{ 'table-active': selectedSourceId === source.source_id }"
              >
                <td class="small mono">{{ source.repo_url }}</td>
                <td class="small mono">{{ source.default_branch }}</td>
                <td>
                  <span class="admin-source-status mono" :class="sourceStatusBadgeClass(source.status)">
                    {{ sourceStatusLabel(source.status) }}
                  </span>
                </td>
                <td>
                  <div class="d-flex flex-column gap-1">
                    <span class="admin-source-status mono" :class="syncStatusBadgeClass(source.last_sync_status)">
                      {{ syncStatusLabel(source.last_sync_status) }}
                    </span>
                    <span class="small text-muted" v-if="source.last_synced_commit_sha">
                      {{ shortSha(source.last_synced_commit_sha) }}
                    </span>
                  </div>
                </td>
                <td>
                  <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-outline-secondary" @click="selectSource(source.source_id)">
                      История
                    </button>
                    <button
                      class="btn btn-sm btn-outline-primary"
                      :disabled="!canManageSources || syncingSourceId === source.source_id || source.status !== 'active' || source.last_sync_status === 'syncing'"
                      @click="syncSource(source.source_id)"
                    >
                      {{ syncingSourceId === source.source_id ? 'Синхронизация...' : 'Синхронизировать' }}
                    </button>
                    <button
                      class="btn btn-sm btn-outline-warning"
                      :disabled="!canManageSources || statusChangingSourceId === source.source_id || source.last_sync_status === 'syncing'"
                      @click="toggleSourceStatus(source)"
                    >
                      {{
                        statusChangingSourceId === source.source_id
                          ? '...'
                          : source.status === 'active'
                            ? 'Отключить'
                            : 'Включить'
                      }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="sources.length === 0">
                <td colspan="5">
                  <div class="agp-empty-state agp-empty-state--compact">Источники пока не добавлены.</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="agp-card p-3">
        <h2 class="h6">История синхронизации и диагностика</h2>
        <div v-if="!selectedSource" class="text-muted small">Выберите источник, чтобы увидеть историю.</div>
        <div v-else class="d-flex flex-column gap-3">
          <div class="agp-card-soft p-3">
            <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">
              <div>
                <div class="fw-semibold">{{ selectedSource.repo_url }}</div>
                <div class="small text-muted">{{ selectedSource.default_branch }}</div>
              </div>
              <span class="admin-source-status mono" :class="sourceStatusBadgeClass(selectedSource.status)">
                {{ sourceStatusLabel(selectedSource.status) }}
              </span>
            </div>

            <hr class="my-2" />

            <div class="small mb-1">
              Последняя синхронизация:
              <span class="admin-source-status mono" :class="syncStatusBadgeClass(selectedSource.last_sync_status)">
                {{ syncStatusLabel(selectedSource.last_sync_status) }}
              </span>
            </div>
            <div class="mb-2" v-if="canManageSources">
              <button
                class="btn btn-sm btn-outline-warning"
                :disabled="statusChangingSourceId === selectedSource.source_id || selectedSource.last_sync_status === 'syncing'"
                @click="toggleSourceStatus(selectedSource)"
              >
                {{
                  statusChangingSourceId === selectedSource.source_id
                    ? 'Смена статуса...'
                    : selectedSource.status === 'active'
                      ? 'Отключить источник'
                      : 'Включить источник'
                }}
              </button>
            </div>

            <div v-if="latestSync" class="source-sync-summary">
              <div class="source-sync-row">
                <span>Старт</span>
                <strong>{{ formatDate(latestSync.started_at) }}</strong>
              </div>
              <div class="source-sync-row" v-if="latestSync.finished_at">
                <span>Финиш</span>
                <strong>{{ formatDate(latestSync.finished_at) }}</strong>
              </div>
              <div class="source-sync-row">
                <span>Инициатор</span>
                <strong>{{ latestSync.requested_by }}</strong>
              </div>
              <div v-if="latestSync.status === 'syncing'" class="text-info-emphasis fw-semibold">
                Синхронизация выполняется...
              </div>
              <div v-if="latestSync.error_message" class="text-danger-emphasis fw-semibold">
                Ошибка: {{ latestSync.error_message }}
              </div>
              <details class="source-tech-details">
                <summary class="small text-muted">Технические детали</summary>
                <div class="mono small mt-2">source_id: {{ selectedSource.source_id }}</div>
                <div class="mono small">build_id: {{ latestSync.build_id || '—' }}</div>
                <div class="mono small">commit_sha: {{ latestSync.commit_sha || selectedSource.last_synced_commit_sha || '—' }}</div>
                <div class="mono small">image_digest: {{ latestSync.image_digest || '—' }}</div>
              </details>
            </div>
            <div v-else class="small text-muted">Для источника еще нет записей синхронизации.</div>
          </div>

          <div class="table-responsive">
            <table class="table align-middle mb-0 admin-source-table">
              <thead>
                <tr>
                  <th>Начало</th>
                  <th>Статус</th>
                  <th>Результат</th>
                  <th>Детали</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in history" :key="item.sync_id">
                  <td class="small mono">{{ formatDate(item.started_at) }}</td>
                  <td>
                    <span class="admin-source-status mono" :class="syncStatusBadgeClass(item.status)">
                      {{ syncStatusLabel(item.status) }}
                    </span>
                  </td>
                  <td class="small">
                    {{ syncResultLabel(item) }}
                  </td>
                  <td>
                    <details class="small">
                      <summary class="text-muted">Технические детали</summary>
                      <div class="mono small mt-1">sync_id: {{ item.sync_id }}</div>
                      <div class="mono small">build_id: {{ item.build_id || '—' }}</div>
                      <div class="mono small">commit_sha: {{ item.commit_sha || '—' }}</div>
                      <div class="mono small">image_digest: {{ item.image_digest || '—' }}</div>
                    </details>
                  </td>
                </tr>
                <tr v-if="history.length === 0">
                  <td colspan="4" class="text-muted small">Для источника пока нет записей синхронизации.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </article>
    </div>

    <article v-if="canManageWorkers" class="agp-card p-3">
      <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap mb-2">
        <div>
          <h2 class="h6 mb-1">Исполнители запусков</h2>
          <div class="small text-muted">Управление исполнителями запусков.</div>
        </div>
        <button
          class="btn btn-sm btn-outline-secondary"
          :disabled="workersLoading || !canManageWorkers"
          @click="loadWorkers()"
        >
          Обновить
        </button>
      </div>

      <div v-if="workerErrorMessage" class="text-danger small mb-2">{{ workerErrorMessage }}</div>
      <div v-if="workersLoading" class="agp-loading-state agp-loading-state--compact">Загрузка исполнителей...</div>
      <div v-else class="table-responsive">
        <table class="table align-middle mb-0 admin-source-table">
          <thead>
            <tr>
              <th>Исполнитель</th>
              <th>Статус</th>
              <th>Емкость</th>
              <th>Метки</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="worker in workers" :key="worker.worker_id">
              <td>
                <div class="fw-semibold">{{ worker.hostname || 'Без имени' }}</div>
                <details class="small">
                  <summary class="text-muted">Технический ID</summary>
                  <span class="mono small">{{ worker.worker_id }}</span>
                </details>
              </td>
              <td>
                <span class="admin-source-status mono" :class="workerStatusBadgeClass(worker.status)">
                  {{ workerStatusLabel(worker.status) }}
                </span>
              </td>
              <td>
                <div class="worker-capacity">
                  <div class="d-flex justify-content-between small">
                    <span>{{ worker.capacity_available }} свободно</span>
                    <span class="text-muted">из {{ worker.capacity_total }}</span>
                  </div>
                  <div class="worker-capacity-bar" aria-hidden="true">
                    <span :style="{ width: workerCapacityPercent(worker) }"></span>
                  </div>
                </div>
              </td>
              <td>
                <div v-if="workerLabelEntries(worker.labels).length" class="worker-label-list">
                  <span
                    v-for="[key, value] in workerLabelEntries(worker.labels)"
                    :key="`${worker.worker_id}-${key}`"
                    class="agp-topic-chip"
                  >
                    {{ key }}: {{ value }}
                  </span>
                </div>
                <span v-else class="text-muted small">без меток</span>
              </td>
              <td>
                <div class="d-flex gap-1 flex-wrap">
                  <button
                    v-for="targetStatus in workerStatusOptions"
                    :key="`${worker.worker_id}-${targetStatus}`"
                    class="btn btn-sm btn-outline-secondary"
                    :disabled="!canManageWorkers || workerStatusChangingId === worker.worker_id || worker.status === targetStatus"
                    @click="updateWorkerStatus(worker.worker_id, targetStatus)"
                  >
                    {{ workerStatusLabel(targetStatus) }}
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="workers.length === 0">
              <td colspan="5" class="text-muted small">Исполнители пока не зарегистрированы.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import {
  createGameSource,
  listGameSourceSyncHistory,
  listGameSources,
  listWorkers,
  setGameSourceStatus,
  setWorkerStatus,
  triggerGameSourceSync,
  type GameSourceDto,
  type GameSourceStatus,
  type GameSourceSyncDto,
  type GameSourceSyncStatus,
  type WorkerDto,
  type WorkerStatus,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

const sessionStore = useSessionStore();

const sources = ref<GameSourceDto[]>([]);
const history = ref<GameSourceSyncDto[]>([]);
const workers = ref<WorkerDto[]>([]);
const selectedSourceId = ref('');
const repoUrl = ref('');
const defaultBranch = ref('main');
const isLoading = ref(false);
const isCreating = ref(false);
const syncingSourceId = ref('');
const statusChangingSourceId = ref('');
const workerStatusChangingId = ref('');
const errorMessage = ref('');
const workerErrorMessage = ref('');
const workersLoading = ref(false);
const pollTimer = ref<number | null>(null);
const pollingIntervalSeconds = 3;
const workerStatusOptions: WorkerStatus[] = ['online', 'offline', 'draining', 'disabled'];

const canManageSources = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const canManageWorkers = computed(() => sessionStore.role === 'admin');
const pageTitle = computed(() => (canManageWorkers.value ? 'Статус системы' : 'Источники игр'));
const pageSubtitle = computed(() =>
  canManageWorkers.value
    ? 'Источники игр, ручная синхронизация и диагностика исполнителей.'
    : 'Подключение и обновление игр из Git-репозиториев.'
);
const selectedSource = computed(
  () => sources.value.find((source) => source.source_id === selectedSourceId.value) ?? null
);
const latestSync = computed(() => history.value[0] ?? null);
const syncingSourcesCount = computed(
  () => sources.value.filter((source) => source.last_sync_status === 'syncing').length
);

function formatDate(raw: string): string {
  const value = new Date(raw);
  if (Number.isNaN(value.getTime())) return raw;
  return value.toLocaleString('ru-RU');
}

function shortSha(value: string): string {
  return value.length <= 12 ? value : value.slice(0, 12);
}

function syncStatusBadgeClass(status: GameSourceSyncStatus): string {
  if (status === 'finished') return 'admin-source-status--ok';
  if (status === 'failed') return 'admin-source-status--danger';
  if (status === 'syncing') return 'admin-source-status--syncing';
  return 'admin-source-status--muted';
}

function syncStatusLabel(status: GameSourceSyncStatus): string {
  if (status === 'finished') return 'готово';
  if (status === 'failed') return 'ошибка';
  if (status === 'syncing') return 'идет';
  return status;
}

function sourceStatusBadgeClass(status: GameSourceStatus): string {
  return status === 'active' ? 'admin-source-status--ok' : 'admin-source-status--muted';
}

function sourceStatusLabel(status: GameSourceStatus): string {
  if (status === 'active') return 'активен';
  if (status === 'disabled') return 'отключен';
  return status;
}

function workerStatusBadgeClass(status: WorkerStatus): string {
  if (status === 'online') return 'admin-source-status--ok';
  if (status === 'draining') return 'admin-source-status--warning';
  if (status === 'offline') return 'admin-source-status--muted';
  return 'admin-source-status--danger';
}

function workerStatusLabel(status: WorkerStatus): string {
  if (status === 'online') return 'онлайн';
  if (status === 'offline') return 'оффлайн';
  if (status === 'draining') return 'завершает';
  if (status === 'disabled') return 'отключен';
  return status;
}

function workerLabelEntries(labels: Record<string, string>): [string, string][] {
  return Object.entries(labels);
}

function workerCapacityPercent(worker: WorkerDto): string {
  if (worker.capacity_total <= 0) return '0%';
  const busy = Math.max(0, worker.capacity_total - worker.capacity_available);
  return `${Math.min(100, Math.round((busy / worker.capacity_total) * 100))}%`;
}

function syncResultLabel(item: GameSourceSyncDto): string {
  if (item.error_message) return item.error_message;
  if (item.status === 'syncing') return 'Выполняется';
  if (item.image_digest) return 'Образ собран';
  if (item.commit_sha) return `Commit ${shortSha(item.commit_sha)}`;
  return '—';
}

function stopPolling(): void {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
}

function refreshPollingState(): void {
  if (syncingSourcesCount.value > 0) {
    if (pollTimer.value === null) {
      pollTimer.value = window.setInterval(() => {
        void loadSources({ silent: true });
      }, pollingIntervalSeconds * 1000);
    }
    return;
  }
  stopPolling();
}

async function loadSources(options: { silent?: boolean } = {}): Promise<void> {
  if (!canManageSources.value) {
    sources.value = [];
    history.value = [];
    selectedSourceId.value = '';
    return;
  }
  if (!options.silent) {
    isLoading.value = true;
  }
  if (!options.silent) {
    errorMessage.value = '';
  }
  try {
    sources.value = await listGameSources();

    const selectedStillExists = sources.value.some((source) => source.source_id === selectedSourceId.value);
    if (!selectedStillExists) {
      selectedSourceId.value = sources.value[0]?.source_id ?? '';
    }

    if (selectedSourceId.value) {
      await refreshHistory(selectedSourceId.value, options);
    } else {
      history.value = [];
    }
  } catch (error) {
    if (!options.silent) {
      errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить источники игр';
    }
  } finally {
    if (!options.silent) {
      isLoading.value = false;
    }
    refreshPollingState();
  }
}

async function loadWorkers(): Promise<void> {
  if (!canManageWorkers.value) {
    workers.value = [];
    workerErrorMessage.value = '';
    return;
  }
  workersLoading.value = true;
  workerErrorMessage.value = '';
  try {
    workers.value = await listWorkers();
  } catch (error) {
    workerErrorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить исполнителей';
  } finally {
    workersLoading.value = false;
  }
}

async function createSource(): Promise<void> {
  if (!canManageSources.value) return;
  isCreating.value = true;
  errorMessage.value = '';
  try {
    const created = await createGameSource({
      repo_url: repoUrl.value,
      default_branch: defaultBranch.value,
      created_by: sessionStore.nickname,
    });
    repoUrl.value = '';
    await loadSources();
    await selectSource(created.source_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось создать источник';
  } finally {
    isCreating.value = false;
  }
}

async function refreshHistory(sourceId: string, options: { silent?: boolean } = {}): Promise<void> {
  try {
    history.value = await listGameSourceSyncHistory(sourceId);
  } catch (error) {
    if (!options.silent) {
      errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить историю синхронизации';
    }
    throw error;
  }
}

async function selectSource(sourceId: string): Promise<void> {
  selectedSourceId.value = sourceId;
  errorMessage.value = '';
  try {
    await refreshHistory(sourceId);
  } catch {
    // refreshHistory already sets error
  }
}

async function syncSource(sourceId: string): Promise<void> {
  if (!canManageSources.value) return;
  syncingSourceId.value = sourceId;
  errorMessage.value = '';
  try {
    await triggerGameSourceSync({
      source_id: sourceId,
      requested_by: sessionStore.nickname,
    });
    await loadSources();
    await selectSource(sourceId);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Синхронизация завершилась с ошибкой';
    await loadSources();
    await selectSource(sourceId);
  } finally {
    syncingSourceId.value = '';
  }
}

async function toggleSourceStatus(source: GameSourceDto): Promise<void> {
  if (!canManageSources.value) return;
  statusChangingSourceId.value = source.source_id;
  errorMessage.value = '';
  const nextStatus: GameSourceStatus = source.status === 'active' ? 'disabled' : 'active';
  try {
    await setGameSourceStatus({
      source_id: source.source_id,
      status: nextStatus,
    });
    await loadSources();
    await selectSource(source.source_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось изменить статус источника';
  } finally {
    statusChangingSourceId.value = '';
  }
}

async function updateWorkerStatus(workerId: string, status: WorkerStatus): Promise<void> {
  if (!canManageWorkers.value) return;
  workerStatusChangingId.value = workerId;
  workerErrorMessage.value = '';
  try {
    await setWorkerStatus({
      worker_id: workerId,
      status,
    });
    await loadWorkers();
  } catch (error) {
    workerErrorMessage.value =
      error instanceof Error ? error.message : 'Не удалось изменить статус исполнителя';
  } finally {
    workerStatusChangingId.value = '';
  }
}

onMounted(async () => {
  if (canManageSources.value || canManageWorkers.value) {
    await Promise.all([
      canManageSources.value ? loadSources() : Promise.resolve(),
      canManageWorkers.value ? loadWorkers() : Promise.resolve(),
    ]);
  }
});

onUnmounted(() => {
  stopPolling();
});

watch(
  [canManageSources, canManageWorkers],
  async (nextValue) => {
    const [canUseSources, canUseWorkers] = nextValue;
    if (canUseSources || canUseWorkers) {
      await Promise.all([
        canUseSources ? loadSources() : Promise.resolve(),
        canUseWorkers ? loadWorkers() : Promise.resolve(),
      ]);
      if (!canUseWorkers) workers.value = [];
      return;
    }
    stopPolling();
    sources.value = [];
    history.value = [];
    workers.value = [];
    selectedSourceId.value = '';
  },
  { flush: 'post' }
);
</script>

<style scoped>
.admin-sources-page {
  gap: 0.9rem;
}

.admin-sources-hero {
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  background:
    radial-gradient(circle at 12% 18%, rgba(20, 184, 166, 0.18), transparent 15rem),
    radial-gradient(circle at 88% 12%, rgba(37, 99, 235, 0.14), transparent 14rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(240, 253, 250, 0.9)),
    url("data:image/svg+xml,%3Csvg width='184' height='112' viewBox='0 0 184 112' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.14' stroke-width='2'%3E%3Cpath d='M22 24h42v28H22zM80 18h34v34H80zM132 32h30v24h-30zM44 72h36v20H44zM104 70h42v22h-42z'/%3E%3Cpath d='M64 38h16M114 35h18M80 82h24M96 52v18'/%3E%3C/g%3E%3C/svg%3E");
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.admin-sources-hero::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.25rem;
  background: linear-gradient(90deg, #14b8a6, #2563eb, #f59e0b);
}

.admin-sources-hero > * {
  position: relative;
}

.admin-sources-kicker {
  color: #0f766e;
  font-size: 0.74rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.agp-status-card {
  border-color: rgba(14, 116, 144, 0.22);
  background:
    radial-gradient(circle at 100% 0%, rgba(14, 165, 233, 0.16), transparent 12rem),
    #f0f9ff;
}

.admin-source-create-card {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.1), transparent 12rem),
    #fff;
}

.admin-source-create-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.18rem;
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.72), rgba(37, 99, 235, 0.5), transparent);
}

.admin-source-create-card > * {
  position: relative;
}

.admin-source-create-grid {
  display: grid;
  grid-template-columns: minmax(18rem, 1fr) minmax(8rem, 0.28fr) minmax(9rem, 0.28fr);
  gap: 0.75rem;
  align-items: end;
}

.admin-source-table {
  --bs-table-bg: transparent;
  --bs-table-striped-bg: rgba(248, 250, 252, 0.82);
  border-color: rgba(148, 163, 184, 0.24);
}

.admin-source-table thead th {
  color: var(--agp-text-muted);
  font-size: 0.74rem;
  font-weight: 850;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.admin-source-status {
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

.admin-source-status--ok {
  border-color: #86efac;
  background: #dcfce7;
  color: #166534;
}

.admin-source-status--syncing {
  border-color: #99f6e4;
  background: #ccfbf1;
  color: #0f766e;
}

.admin-source-status--warning {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #9a3412;
}

.admin-source-status--danger {
  border-color: #fecaca;
  background: #fef2f2;
  color: #991b1b;
}

.admin-source-status--muted {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #475569;
}

.source-sync-summary {
  display: grid;
  gap: 0.45rem;
  font-size: 0.88rem;
}

.source-sync-row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.source-sync-row span {
  color: var(--agp-muted);
}

.source-sync-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: right;
}

.source-tech-details {
  border-top: 1px solid rgba(148, 163, 184, 0.18);
  padding-top: 0.35rem;
}

.worker-capacity {
  min-width: 9rem;
}

.worker-capacity-bar {
  height: 0.42rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.24);
}

.worker-capacity-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #14b8a6);
}

.worker-label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

@media (max-width: 1000px) {
  .admin-sources-hero {
    flex-direction: column;
  }

  .admin-source-create-grid {
    grid-template-columns: 1fr 1fr;
  }

  .admin-source-create-grid > :first-child {
    grid-column: 1 / -1;
  }
}

@media (max-width: 640px) {
  .admin-source-create-grid {
    grid-template-columns: 1fr;
  }
}
</style>
