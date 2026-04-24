<template>
  <section class="agp-grid">
    <header class="d-flex justify-content-between align-items-start gap-3 flex-wrap">
      <div>
        <h1 class="h3 mb-1">{{ pageTitle }}</h1>
        <p class="text-muted mb-0">
          {{ pageSubtitle }}
        </p>
      </div>
      <div class="d-flex gap-2 align-items-center">
        <span v-if="syncingSourcesCount > 0" class="badge text-bg-info">
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

    <article class="agp-card p-3" v-if="syncingSourcesCount > 0">
      <div class="d-flex align-items-center gap-2">
        <span class="spinner-border spinner-border-sm" aria-hidden="true"></span>
        <div class="fw-semibold">Есть активные sync-процессы</div>
      </div>
      <div class="small text-muted mt-1">
        Страница автоматически обновляет статусы каждые {{ pollingIntervalSeconds }} сек.
      </div>
    </article>

    <article class="agp-card p-3" v-if="!canManageSources">
      <div class="text-warning-emphasis fw-semibold">Требуется роль teacher или admin</div>
      <div class="small text-muted">
        Для текущего пользователя действия создания и sync источников недоступны.
      </div>
    </article>

    <article class="agp-card p-3">
      <h2 class="h6">Добавить игру из Git</h2>
      <div class="row g-2 align-items-end">
        <div class="col-12 col-lg-7">
          <label class="form-label small">Репозиторий</label>
          <input v-model.trim="repoUrl" class="form-control mono" placeholder="https://github.com/org/repo" />
        </div>
        <div class="col-6 col-lg-2">
          <label class="form-label small">branch</label>
          <input v-model.trim="defaultBranch" class="form-control mono" />
        </div>
        <div class="col-6 col-lg-3">
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
        <div v-if="isLoading" class="text-muted small">Загрузка...</div>
        <table v-else class="table align-middle mb-0">
          <thead>
            <tr>
              <th>repo</th>
              <th>branch</th>
              <th>source</th>
              <th>last sync</th>
              <th>actions</th>
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
                <span class="badge mono" :class="sourceStatusBadgeClass(source.status)">
                  {{ source.status }}
                </span>
              </td>
              <td>
                <div class="d-flex flex-column gap-1">
                  <span class="badge mono" :class="syncStatusBadgeClass(source.last_sync_status)">
                    {{ source.last_sync_status }}
                  </span>
                  <span class="small mono text-muted" v-if="source.last_synced_commit_sha">
                    {{ shortSha(source.last_synced_commit_sha) }}
                  </span>
                </div>
              </td>
              <td>
                <div class="d-flex gap-2">
                  <button class="btn btn-sm btn-outline-secondary" @click="selectSource(source.source_id)">
                    History
                  </button>
                  <button
                    class="btn btn-sm btn-outline-primary"
                    :disabled="!canManageSources || syncingSourceId === source.source_id || source.status !== 'active' || source.last_sync_status === 'syncing'"
                    @click="syncSource(source.source_id)"
                  >
                    {{ syncingSourceId === source.source_id ? 'Sync...' : 'Sync now' }}
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
                          ? 'Disable'
                          : 'Enable'
                    }}
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="sources.length === 0">
              <td colspan="5" class="text-muted small">Источники пока не добавлены.</td>
            </tr>
          </tbody>
        </table>
      </article>

      <article class="agp-card p-3">
        <h2 class="h6">История sync и диагностика</h2>
        <div v-if="!selectedSource" class="text-muted small">Выберите source, чтобы увидеть историю.</div>
        <div v-else class="d-flex flex-column gap-3">
          <div class="agp-card-soft p-3">
            <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">
              <div>
                <div class="fw-semibold">{{ selectedSource.repo_url }}</div>
                <div class="small mono text-muted">source_id={{ selectedSource.source_id }}</div>
              </div>
              <span class="badge mono" :class="sourceStatusBadgeClass(selectedSource.status)">
                {{ selectedSource.status }}
              </span>
            </div>

            <hr class="my-2" />

            <div class="small mb-1">
              Последний sync:
              <span class="badge mono" :class="syncStatusBadgeClass(selectedSource.last_sync_status)">
                {{ selectedSource.last_sync_status }}
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
                      ? 'Отключить source'
                      : 'Включить source'
                }}
              </button>
            </div>

            <div v-if="latestSync" class="small d-flex flex-column gap-1">
              <div>
                started: <span class="mono">{{ formatDate(latestSync.started_at) }}</span>
                <span v-if="latestSync.finished_at">
                  · finished: <span class="mono">{{ formatDate(latestSync.finished_at) }}</span>
                </span>
              </div>
              <div>
                requested_by: <span class="mono">{{ latestSync.requested_by }}</span>
                · build_id: <span class="mono">{{ latestSync.build_id || '—' }}</span>
              </div>
              <div>
                commit_sha: <span class="mono">{{ latestSync.commit_sha || selectedSource.last_synced_commit_sha || '—' }}</span>
              </div>
              <div>
                image_digest: <span class="mono">{{ latestSync.image_digest || '—' }}</span>
              </div>
              <div v-if="latestSync.status === 'syncing'" class="text-info-emphasis fw-semibold">
                Sync выполняется...
              </div>
              <div v-if="latestSync.error_message" class="text-danger-emphasis fw-semibold">
                Ошибка: {{ latestSync.error_message }}
              </div>
            </div>
            <div v-else class="small text-muted">Для source еще нет записей sync.</div>
          </div>

          <table class="table align-middle mb-0">
            <thead>
              <tr>
                <th>started</th>
                <th>status</th>
                <th>build</th>
                <th>digest/commit/error</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in history" :key="item.sync_id">
                <td class="small mono">{{ formatDate(item.started_at) }}</td>
                <td>
                  <span class="badge mono" :class="syncStatusBadgeClass(item.status)">
                    {{ item.status }}
                  </span>
                </td>
                <td class="small mono">{{ item.build_id || '—' }}</td>
                <td class="small mono">
                  {{ item.image_digest || item.commit_sha || item.error_message || '—' }}
                </td>
              </tr>
              <tr v-if="history.length === 0">
                <td colspan="4" class="text-muted small">Для источника пока нет sync-записей.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </div>

    <article v-if="canManageWorkers" class="agp-card p-3">
      <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap mb-2">
        <div>
          <h2 class="h6 mb-1">Worker Control</h2>
          <div class="small text-muted">Управление удаленными worker-нодами execution plane.</div>
        </div>
        <button
          class="btn btn-sm btn-outline-secondary"
          :disabled="workersLoading || !canManageWorkers"
          @click="loadWorkers()"
        >
          Обновить workers
        </button>
      </div>

      <div v-if="workerErrorMessage" class="text-danger small mb-2">{{ workerErrorMessage }}</div>
      <div v-if="workersLoading" class="text-muted small">Загрузка worker-нод...</div>
      <table v-else class="table align-middle mb-0">
        <thead>
          <tr>
            <th>worker</th>
            <th>status</th>
            <th>capacity</th>
            <th>labels</th>
            <th>actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="worker in workers" :key="worker.worker_id">
            <td>
              <div class="mono small fw-semibold">{{ worker.worker_id }}</div>
              <div class="small text-muted">{{ worker.hostname }}</div>
            </td>
            <td>
              <span class="badge mono" :class="workerStatusBadgeClass(worker.status)">
                {{ worker.status }}
              </span>
            </td>
            <td class="mono small">{{ worker.capacity_available }}/{{ worker.capacity_total }}</td>
            <td class="mono small">{{ workerLabelSummary(worker.labels) }}</td>
            <td>
              <div class="d-flex gap-1 flex-wrap">
                <button
                  v-for="targetStatus in workerStatusOptions"
                  :key="`${worker.worker_id}-${targetStatus}`"
                  class="btn btn-sm btn-outline-secondary"
                  :disabled="!canManageWorkers || workerStatusChangingId === worker.worker_id || worker.status === targetStatus"
                  @click="updateWorkerStatus(worker.worker_id, targetStatus)"
                >
                  {{ targetStatus }}
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="workers.length === 0">
            <td colspan="5" class="text-muted small">Worker-ноды пока не зарегистрированы.</td>
          </tr>
        </tbody>
      </table>
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
    ? 'Источники игр, ручной sync и диагностика worker-нод.'
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
  if (status === 'finished') return 'text-bg-success';
  if (status === 'failed') return 'text-bg-danger';
  if (status === 'syncing') return 'text-bg-info';
  return 'text-bg-secondary';
}

function sourceStatusBadgeClass(status: GameSourceStatus): string {
  return status === 'active' ? 'text-bg-success' : 'text-bg-secondary';
}

function workerStatusBadgeClass(status: WorkerStatus): string {
  if (status === 'online') return 'text-bg-success';
  if (status === 'draining') return 'text-bg-warning';
  if (status === 'offline') return 'text-bg-secondary';
  return 'text-bg-danger';
}

function workerLabelSummary(labels: Record<string, string>): string {
  const entries = Object.entries(labels);
  if (entries.length === 0) return '—';
  return entries.map(([key, value]) => `${key}:${value}`).join(', ');
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
      errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить game sources';
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
    workerErrorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить worker-ноды';
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
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось создать source';
  } finally {
    isCreating.value = false;
  }
}

async function refreshHistory(sourceId: string, options: { silent?: boolean } = {}): Promise<void> {
  try {
    history.value = await listGameSourceSyncHistory(sourceId);
  } catch (error) {
    if (!options.silent) {
      errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить историю sync';
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
    errorMessage.value = error instanceof Error ? error.message : 'Sync завершился с ошибкой';
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
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось изменить статус source';
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
      error instanceof Error ? error.message : 'Не удалось изменить статус worker';
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
