<template>
  <section class="agp-grid admin-sources-page">
    <header class="admin-sources-hero">
      <div>
        <h1 class="h3 mb-1">{{ pageTitle }}</h1>
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
        <SnakeLoader />
        <div class="fw-semibold">Есть активные синхронизации</div>
      </div>
    </article>

    <article class="agp-card p-3" v-if="!canManageSources">
      <div class="agp-empty-state agp-empty-state--compact">
        Требуется роль администратора. Для текущего пользователя действия создания и синхронизации источников недоступны.
      </div>
    </article>

    <article v-if="canManageSources" class="agp-card p-3 admin-source-create-card">
      <h2 class="h6">Добавить игру из Git</h2>
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
        <LoadingSkeleton v-if="isLoading" :count="2" layout="list" label="Загрузка источников…" />
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
                    <button class="btn btn-outline-primary" :disabled="!canManageSources || syncingSourceId === source.source_id || source.status !== 'active' || source.last_sync_status === 'syncing'" @click="syncSource(source.source_id)">{{ syncingSourceId === source.source_id ? 'Синхронизация…' : 'Синхронизировать' }}</button>
                    <ActionMenu compact :label="`Действия источника ${source.repo_url}`" :items="sourceMenu(source)" @select="handleSourceMenu(source, $event)" />
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

        </div>
        <div class="d-flex gap-2">
        <button class="btn btn-sm btn-primary" @click="openMachineDialog()">Добавить машину</button>
        <button
          class="btn btn-sm btn-outline-secondary"
          :disabled="workersLoading || !canManageWorkers"
          @click="loadWorkers()"
        >
          Обновить
        </button>
        </div>
      </div>

      <div v-if="workerErrorMessage" class="text-danger small mb-2">{{ workerErrorMessage }}</div>
      <div v-if="workersLoading" class="agp-loading-state agp-loading-state--compact">Загрузка исполнителей...</div>
      <div v-else class="table-responsive">
        <table class="table align-middle mb-0 admin-source-table">
          <thead>
            <tr>
              <th>Исполнитель</th>
              <th>Статус</th>
              <th>Слоты</th>
              <th>Метки</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="worker in workers" :key="worker.worker_id">
              <td>
                <div class="fw-semibold">{{ worker.hostname || 'Без имени' }}</div>
                <div v-if="worker.connection_type === 'external'" class="small text-muted">{{ workerTokenLabel(worker) }}</div>
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
                <ActionMenu compact :label="`Статус исполнителя ${worker.hostname}`" :items="workerActions(worker)" @select="handleWorkerAction(worker, $event)" />
              </td>
            </tr>
            <tr v-if="workers.length === 0">
              <td colspan="5" class="text-muted small">Исполнители пока не зарегистрированы.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
    <Teleport to="body">
      <div v-if="machineDialogOpen" class="worker-dialog-backdrop" @click.self="closeMachineDialog" @keydown.esc="closeMachineDialog">
        <section ref="machineDialog" class="worker-dialog agp-card" role="dialog" aria-modal="true" aria-labelledby="worker-dialog-title" tabindex="-1" @keydown.tab="trapMachineFocus">
          <header class="worker-dialog-head"><h2 id="worker-dialog-title">{{ machineInstallation ? 'Подключение машины' : 'Добавить машину' }}</h2><button class="btn btn-outline-secondary worker-dialog-close" aria-label="Закрыть" :disabled="machineSaving" @click="closeMachineDialog">×</button></header>
          <form v-if="!machineInstallation" class="worker-dialog-form" @submit.prevent="addMachine">
            <label>Название<input ref="machineNameInput" v-model="machineName" class="form-control" maxlength="120" required :disabled="machineSaving" /></label>
            <label>Параллельных матчей<input v-model.number="machineSlots" class="form-control" type="number" min="1" max="64" required :disabled="machineSaving" /></label>
            <label>Метки<textarea v-model="machineLabels" class="form-control" rows="2" placeholder="pool=external" :disabled="machineSaving"></textarea></label>
            <div v-if="machineError" class="small text-danger" role="alert">{{ machineError }}</div>
            <footer class="worker-dialog-actions"><button type="button" class="btn btn-outline-secondary" :disabled="machineSaving" @click="closeMachineDialog">Отмена</button><button class="btn btn-primary" :disabled="machineSaving">{{ machineSaving ? 'Создание…' : 'Получить команду' }}</button></footer>
          </form>
          <div v-else class="worker-dialog-form">
            <p class="mb-0 small">Выполните на машине с Docker. Ключ действует до {{ formatDate(machineInstallation.expires_at) }} и подключает одну машину.</p>
            <textarea :value="machineInstallation.command" readonly class="form-control worker-install-command" aria-label="Команда запуска Docker" spellcheck="false" @focus="($event.target as HTMLTextAreaElement).select()"></textarea>
            <p class="mb-0 small text-muted">Контейнер управляет Docker на этой машине. Код учеников запускается в отдельных контейнерах.</p>
            <div v-if="machineError" class="small text-danger" role="alert">{{ machineError }}</div>
            <footer class="worker-dialog-actions"><button class="btn btn-outline-secondary" @click="closeMachineDialog">Закрыть</button><button class="btn btn-primary" @click="copyMachineCommand">{{ machineCommandCopied ? 'Скопировано' : 'Копировать команду' }}</button></footer>
          </div>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import ActionMenu, { type ActionMenuItem } from "../components/ActionMenu.vue";
import SnakeLoader from '../components/SnakeLoader.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import {
  createGameSource,
  listGameSourceSyncHistory,
  listGameSources,
  listWorkers,
  addExternalWorker,
  reconnectExternalWorker,
  revokeExternalWorker,
  type WorkerInstallationDto,
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

const machineDialogOpen = ref(false);
const machineDialog = ref<HTMLElement | null>(null);
const machineNameInput = ref<HTMLInputElement | null>(null);
const machineName = ref('');
const machineSlots = ref(1);
const machineLabels = ref('');
const machineSaving = ref(false);
const machineError = ref('');
const machineInstallation = ref<WorkerInstallationDto | null>(null);
const machineCommandCopied = ref(false);
let machinePreviousFocus: HTMLElement | null = null;
function openMachineDialog(): void {
  machinePreviousFocus = document.activeElement as HTMLElement;
  machineName.value = ''; machineSlots.value = 1; machineLabels.value = '';
  machineError.value = ''; machineInstallation.value = null; machineCommandCopied.value = false;
  machineDialogOpen.value = true;
  void nextTick(() => machineNameInput.value?.focus());
}
function closeMachineDialog(): void {
  if (machineSaving.value) return;
  machineDialogOpen.value = false;
  machineInstallation.value = null;
  machinePreviousFocus?.focus();
}
function trapMachineFocus(event: KeyboardEvent): void {
  const targets = [...(machineDialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),textarea:not(:disabled)') ?? [])];
  const first = targets[0], last = targets[targets.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}
async function addMachine(): Promise<void> {
  machineSaving.value = true; machineError.value = '';
  try {
    const labels: Record<string, string> = {};
    for (const line of machineLabels.value.split('\n').map(value => value.trim()).filter(Boolean)) {
      const equal = line.indexOf('=');
      if (equal <= 0 || equal === line.length - 1) throw new Error('Укажите каждую метку в виде имя=значение.');
      labels[line.slice(0, equal).trim()] = line.slice(equal + 1).trim();
    }
    machineInstallation.value = await addExternalWorker({ name: machineName.value.trim(), slots: machineSlots.value, labels });
    await nextTick(); machineDialog.value?.focus();
    await loadWorkers();
  } catch (error) { machineError.value = error instanceof Error ? error.message : 'Не удалось добавить машину'; }
  finally { machineSaving.value = false; }
}
async function copyMachineCommand(): Promise<void> {
  try { await navigator.clipboard.writeText(machineInstallation.value?.command ?? ''); machineCommandCopied.value = true; }
  catch { machineError.value = 'Выделите и скопируйте команду из поля.'; }
}
function workerTokenLabel(worker: WorkerDto): string {
  return ({ pending: 'Ожидает подключения', active: 'Внешняя машина', expired: 'Ключ подключения истёк', revoked: 'Токен отозван' })[worker.token_status ?? 'active'];
}
function workerActions(worker: WorkerDto): ActionMenuItem[] {
  const busy = workerStatusChangingId.value === worker.worker_id;
  const options = worker.connection_type === 'external' ? (worker.token_status === 'active' ? ['online', 'draining', 'disabled'] as WorkerStatus[] : []) : workerStatusOptions;
  const items: ActionMenuItem[] = options.filter(status => status !== worker.status).map(status => ({ id: status, label: workerStatusLabel(status), disabled: busy, danger: status === 'disabled' }));
  if (worker.connection_type === 'external') {
    items.unshift({ id: 'connect', label: 'Переподключить машину', disabled: busy });
    if (worker.token_status !== 'revoked') items.push({ id: 'revoke', label: 'Отозвать токен', danger: true, disabled: busy });
  }
  return items;
}
async function handleWorkerAction(worker: WorkerDto, action: string): Promise<void> {
  if (action !== 'connect' && action !== 'revoke') { await updateWorkerStatus(worker.worker_id, action as WorkerStatus); return; }
  workerStatusChangingId.value = worker.worker_id; workerErrorMessage.value = '';
  try {
    if (action === 'revoke') await revokeExternalWorker(worker.worker_id);
    else {
      openMachineDialog(); machineSaving.value = true;
      machineInstallation.value = await reconnectExternalWorker(worker.worker_id);
      await nextTick(); machineDialog.value?.focus();
    }
    await loadWorkers();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось обновить подключение';
    if (machineDialogOpen.value) machineError.value = message; else workerErrorMessage.value = message;
  } finally { workerStatusChangingId.value = ''; machineSaving.value = false; }
}

const pollingIntervalSeconds = 3;
const workerStatusOptions: WorkerStatus[] = ['online', 'offline', 'draining', 'disabled'];

const canManageSources = computed(() => sessionStore.role === 'admin');
const canManageWorkers = computed(() => sessionStore.role === 'admin');
const pageTitle = computed(() => (canManageWorkers.value ? 'Статус системы' : 'Источники игр'));
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

function sourceMenu(source: GameSourceDto): ActionMenuItem[] {
  return [
    { id: 'history', label: 'История синхронизации' },
    { id: 'toggle', label: source.status === 'active' ? 'Отключить источник' : 'Включить источник', disabled: !canManageSources.value || statusChangingSourceId.value === source.source_id || source.last_sync_status === 'syncing', danger: source.status === 'active' },
  ];
}
function handleSourceMenu(source: GameSourceDto, action: string): void {
  if (action === 'history') void selectSource(source.source_id);
  if (action === 'toggle') void toggleSourceStatus(source);
}
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
  align-items: center;
  flex-wrap: wrap;
  padding-bottom: 8px;
  gap: 16px;
  background: var(--agp-surface);
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.admin-sources-hero::before {
  content: none;
}

.admin-sources-hero > * {
  position: relative;
}

.admin-sources-kicker {
  color: var(--agp-primary);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.agp-status-card {
  border-color: var(--agp-border);
  background: var(--agp-surface);
}

.admin-source-create-card {
  position: relative;
  overflow: hidden;
  background: var(--agp-surface);
}

.admin-source-create-card::before {
  content: none;
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
  border-color: var(--agp-border);
}

.admin-source-table thead th {
  color: var(--agp-text-muted);
  font-size: 0.74rem;
  font-weight: 700;
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
  font-weight: 700;
  white-space: nowrap;
}

.admin-source-status--ok {
  border-color: var(--agp-border);
  background: var(--arena-success-soft);
  color: var(--agp-success);
}

.admin-source-status--syncing {
  border-color: var(--agp-border);
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.admin-source-status--warning {
  border-color: var(--agp-border);
  background: var(--arena-warning-soft);
  color: var(--agp-warning);
}

.admin-source-status--danger {
  border-color: var(--agp-border);
  background: var(--arena-error-soft);
  color: var(--agp-danger);
}

.admin-source-status--muted {
  border-color: var(--agp-border);
  background: var(--agp-surface-soft);
  color: var(--agp-text-muted);
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
  color: var(--agp-text-muted);
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
  background: var(--agp-border);
}

.worker-capacity-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--agp-primary);
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

<style scoped>
.worker-dialog-backdrop { position: fixed; inset: 0; z-index: 1200; display: grid; place-items: center; padding: 24px; background: #11182766; }
.worker-dialog { width: min(640px,100%); max-height: calc(100dvh - 48px); overflow: auto; padding: 24px; }
.worker-dialog-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 20px; }
.worker-dialog-head h2 { margin: 0; font-size: 20px; line-height: 28px; }
.worker-dialog-close { width: 36px; height: 36px; padding: 0; font-size: 24px; line-height: 1; }
.worker-dialog-form { display: grid; gap: 16px; }
.worker-dialog-form label { display: grid; gap: 6px; font-size: 13px; color: var(--agp-text-muted); }
.worker-dialog-actions { display: flex; justify-content: flex-end; gap: 8px; padding-top: 4px; }
.worker-install-command { min-height: 200px; font-family: monospace; font-size: 12px; line-height: 20px; color: var(--agp-text); background: var(--agp-bg); }
@media (max-width: 767px) { .worker-dialog-backdrop { padding: 12px; } .worker-dialog { padding: 16px; max-height: calc(100dvh - 24px); } .worker-dialog .btn { min-height: 44px; } .worker-dialog-close { min-width: 44px; } }
</style>
