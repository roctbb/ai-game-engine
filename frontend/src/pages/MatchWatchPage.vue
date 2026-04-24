<template>
  <section class="agp-grid agp-task-workspace agp-watch-page" :class="{ 'agp-watch-page--embedded': isEmbedded }">
    <header v-if="!isEmbedded" class="agp-task-header">
      <div class="agp-task-header-main">
        <RouterLink to="/lobbies" class="agp-back-link" title="К лобби" aria-label="К лобби">←</RouterLink>
        <h1>{{ watchContext?.game_slug || 'Просмотр запуска' }}</h1>
      </div>

      <div v-if="!isLoading" class="agp-task-header-player">
        <button
          class="agp-icon-button agp-icon-button--replay"
          :disabled="!canPlayReplay"
          :title="replayIsPlaying ? 'Пауза' : 'Воспроизвести'"
          aria-label="Воспроизвести повтор"
          @click="toggleReplayPlay"
        >
          {{ replayIsPlaying ? '❚❚' : '▶' }}
        </button>
        <button
          class="agp-icon-button agp-icon-button--ghost"
          :disabled="!canStepBackward"
          title="Предыдущий кадр"
          aria-label="Предыдущий кадр"
          @click="stepReplay(-1)"
        >
          ‹
        </button>
        <button
          class="agp-icon-button agp-icon-button--ghost"
          :disabled="!canStepForward"
          title="Следующий кадр"
          aria-label="Следующий кадр"
          @click="stepReplay(1)"
        >
          ›
        </button>
        <span class="small text-muted agp-player-frame-label">
          <template v-if="replayFrames.length">кадр {{ replayFrameIndex + 1 }}/{{ replayFrames.length }}</template>
          <template v-else>повтор после завершения</template>
        </span>
        <input
          v-model.number="replayFrameIndex"
          class="form-range agp-player-range"
          type="range"
          min="0"
          :max="Math.max(0, replayFrames.length - 1)"
          :disabled="replayFrames.length <= 1"
        />
        <label class="agp-speed-control small text-muted">
          <span class="agp-speed-label">скорость</span>
          <select v-model.number="replaySpeedMs" class="form-select form-select-sm agp-speed-select">
            <option :value="2000">медленно</option>
            <option :value="1000">обычно</option>
            <option :value="500">быстро</option>
            <option :value="250">очень быстро</option>
          </select>
        </label>
      </div>

      <div class="agp-task-header-actions">
        <div class="agp-run-status">
          <span class="agp-run-state-badge" :class="`agp-run-state-badge--${runStatusTone}`"></span>
          <span class="small text-muted">Запуск</span>
          <strong>{{ runStatusLabel }}</strong>
        </div>
        <button
          v-if="canSeeTechnicalDetails"
          class="agp-icon-button agp-icon-button--restart"
          :disabled="!canRestartRenderer"
          title="Перезапустить визуализацию"
          aria-label="Перезапустить визуализацию"
          @click="restartRenderer"
        >
          ↻
        </button>
      </div>
    </header>

    <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка матча...</article>
    <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>

    <template v-else-if="watchContext && run">
      <div class="agp-main-columns agp-watch-columns">
        <article class="agp-card p-3 agp-viewer-card">
          <div class="agp-viewer-overlay agp-viewer-overlay--status">
            <span class="agp-run-state-badge" :class="`agp-run-state-badge--${runStatusTone}`"></span>
            {{ runStatusLabel }}
          </div>
          <div class="agp-viewer-overlay agp-viewer-overlay--message agp-watch-renderer-state">
            {{ rendererStatusLabel }}
          </div>
          <div v-if="watchContext.renderer_url" class="agp-viewer-frame">
            <iframe
              ref="rendererFrameRef"
              :key="rendererKey"
              :src="watchContext.renderer_url"
              title="Визуализация игры"
              sandbox="allow-scripts allow-same-origin"
              @load="onRendererLoad"
            ></iframe>
          </div>
          <div v-else class="agp-card-soft p-3 text-muted small">
            Для этой игры визуализация не настроена.
          </div>
          <section class="agp-bot-console" aria-label="Вывод бота">
            <div class="agp-bot-console-head">
              <strong>Вывод print</strong>
              <span v-if="replayFrames.length > 0" class="text-muted">
                кадр {{ replayFrameIndex + 1 }}/{{ replayFrames.length }}
              </span>
            </div>
            <div class="agp-bot-console-body">
              <div v-if="currentConsoleLines.length === 0" class="agp-bot-console-empty">
                print появится здесь
              </div>
              <div v-for="line in currentConsoleLines" :key="line.id" class="agp-bot-console-line">
                <span v-if="line.role" class="agp-bot-console-role">{{ line.role }}</span>
                <span class="mono agp-bot-console-message">{{ line.message }}</span>
              </div>
            </div>
          </section>
        </article>

        <aside v-if="!isEmbedded" class="agp-card p-3 agp-watch-side-card">
          <h2 class="h6 mb-3">Состояние</h2>
          <div class="agp-watch-stat">
            <span class="text-muted small">Статус запуска</span>
            <strong>{{ runStatusLabel }}</strong>
          </div>
          <div class="agp-watch-stat">
            <span class="text-muted small">Визуализация</span>
            <strong>{{ rendererStatusLabel }}</strong>
          </div>
          <div class="agp-watch-stat">
            <span class="text-muted small">Тип</span>
            <strong>{{ runKindLabel }}</strong>
          </div>
          <div v-if="canSeeTechnicalDetails" class="agp-watch-stat">
            <span class="text-muted small">Обновления</span>
            <strong class="mono">{{ liveMode }}</strong>
          </div>
          <div v-if="run.error_message" class="mt-3">
            <RunReasonBadge :reason="run.error_message" :show-raw="false" />
          </div>
          <hr />
          <h3 class="h6 mb-2">Повтор</h3>
          <div v-if="isReplayLoading" class="text-muted small">Загрузка повтора...</div>
          <div v-else-if="replayError" class="text-danger small">{{ replayError }}</div>
          <div v-else-if="!replay" class="text-muted small">Повтор появится после завершения запуска.</div>
          <div class="d-flex flex-wrap gap-2 align-items-center mb-3" v-if="replayFrames.length > 0">
            <button class="btn btn-sm btn-outline-secondary" :disabled="!canStepBackward" @click="stepReplay(-1)">
              ◀
            </button>
            <button class="btn btn-sm btn-outline-secondary" :disabled="!canPlayReplay" @click="toggleReplayPlay">
              {{ replayIsPlaying ? 'Пауза' : 'Пуск' }}
            </button>
            <button class="btn btn-sm btn-outline-secondary" :disabled="!canStepForward" @click="stepReplay(1)">
              ▶
            </button>
            <select v-model.number="replaySpeedMs" class="form-select form-select-sm mono" style="width: 7rem">
              <option :value="250">x4</option>
              <option :value="500">x2</option>
              <option :value="1000">x1</option>
              <option :value="2000">x0.5</option>
            </select>
            <span class="small text-muted">
              кадр <span class="mono">{{ replayFrameIndex + 1 }}</span>/<span class="mono">{{ replayFrames.length }}</span>
            </span>
          </div>
          <input
            v-if="replayFrames.length > 0"
            v-model.number="replayFrameIndex"
            type="range"
            class="form-range mb-3"
            :min="0"
            :max="Math.max(0, replayFrames.length - 1)"
            step="1"
          />

          <details v-if="canSeeTechnicalDetails" class="mt-3">
            <summary class="agp-details-summary">Технические детали</summary>
            <section class="agp-card-soft p-3 mt-3">
              <h2 class="h6">Данные запуска</h2>
              <table class="table table-sm align-middle mb-0">
                <tbody>
                  <tr>
                    <th class="w-25">id запуска</th>
                    <td class="mono small">{{ run.run_id }}</td>
                  </tr>
                  <tr>
                    <th>статус</th>
                    <td class="mono small">{{ run.status }}</td>
                  </tr>
                  <tr>
                    <th>причина</th>
                    <td><RunReasonBadge :reason="run.error_message" /></td>
                  </tr>
                  <tr>
                    <th>тип</th>
                    <td class="mono small">{{ run.run_kind }}</td>
                  </tr>
                  <tr>
                    <th>игра</th>
                    <td class="mono small">{{ watchContext.game_slug }}</td>
                  </tr>
                  <tr>
                    <th>worker</th>
                    <td class="mono small">{{ run.worker_id ?? '—' }}</td>
                  </tr>
                  <tr>
                    <th>снимок кода</th>
                    <td class="mono small">{{ run.snapshot_id ?? '—' }}</td>
                  </tr>
                  <tr>
                    <th>протокол</th>
                    <td class="mono small">{{ watchContext.renderer_protocol }}</td>
                  </tr>
                  <tr v-if="watchContext.renderer_url">
                    <th>визуализация</th>
                    <td class="mono small">{{ watchContext.renderer_url }}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section class="agp-card-soft p-3 mt-3">
              <h2 class="h6">События визуализации</h2>
              <div v-if="rendererLogs.length === 0" class="text-muted small">События визуализации пока не поступали.</div>
              <ul v-else class="list-group list-group-flush">
                <li
                  v-for="item in rendererLogs"
                  :key="item.id"
                  class="list-group-item px-0 d-flex justify-content-between gap-2"
                >
                  <span class="mono small">{{ item.message }}</span>
                  <span
                    class="small"
                    :class="item.level === 'error' ? 'text-danger' : item.level === 'warn' ? 'text-warning' : 'text-muted'"
                  >
                    {{ item.timestamp }}
                  </span>
                </li>
              </ul>
            </section>

            <details class="mt-3">
              <summary class="small fw-semibold">Итоговые данные</summary>
              <pre class="mono small mb-0 mt-2">{{ resultPayloadJson }}</pre>
            </details>

            <details class="mt-3">
              <summary class="small fw-semibold">Данные повтора</summary>
              <div v-if="replay" class="mt-2">
              <div class="small mb-2">
                id повтора: <span class="mono">{{ replay.replay_id }}</span>
              </div>
              <div class="small text-muted mb-2">
                кадры: <span class="mono">{{ replay.frames.length }}</span>
                · события: <span class="mono">{{ replay.events.length }}</span>
                · видимость: <span class="mono">{{ replay.visibility }}</span>
              </div>
              <details class="mb-2" v-if="replay.events.length > 0">
                <summary class="small">События повтора ({{ replay.events.length }})</summary>
                <pre class="mono small mb-0">{{ replayEventsJson }}</pre>
              </details>
              <pre class="mono small mb-0">{{ replaySummaryJson }}</pre>
              </div>
              <div v-else class="text-muted small mt-2">
                Повтор пока недоступен.
              </div>
            </details>
          </details>
        </aside>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import RunReasonBadge from '../components/RunReasonBadge.vue';
import {
  getRun,
  getRunReplay,
  getRunWatchContext,
  type ReplayDto,
  type RunDto,
  type RunWatchContextDto,
  type StreamEnvelopeDto,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

interface RendererLogItem {
  id: number;
  level: 'info' | 'warn' | 'error';
  message: string;
  timestamp: string;
}

interface ReplayFrameView {
  tick: number;
  phase: string;
  frame: Record<string, unknown>;
}

interface BotConsoleLine {
  id: string;
  tick: number;
  role: string;
  message: string;
}

const route = useRoute();
const sessionStore = useSessionStore();
const isEmbedded = computed(() => route.query.embed === '1');
const canSeeTechnicalDetails = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');

const watchContext = ref<RunWatchContextDto | null>(null);
const run = ref<RunDto | null>(null);
const replay = ref<ReplayDto | null>(null);
const replayError = ref('');
const isReplayLoading = ref(false);
const isLoading = ref(false);
const errorMessage = ref('');

const rendererFrameRef = ref<HTMLIFrameElement | null>(null);
const rendererKey = ref(0);
const rendererReady = ref(false);
const rendererTick = ref(0);
const rendererLogs = ref<RendererLogItem[]>([]);
const liveMode = ref<'idle' | 'sse' | 'polling'>('idle');
const replayFrameIndex = ref(0);
const replayIsPlaying = ref(false);
const replaySpeedMs = ref(replaySpeedFromQuery());
let rendererLogCounter = 0;
let runPollingHandle: ReturnType<typeof setInterval> | null = null;
let runEventSource: EventSource | null = null;
let replayPlaybackHandle: ReturnType<typeof setInterval> | null = null;

const canRestartRenderer = computed(() => canSeeTechnicalDetails.value && Boolean(watchContext.value?.renderer_url));
const resultPayloadJson = computed(() => JSON.stringify(run.value?.result_payload ?? {}, null, 2));
const replaySummaryJson = computed(() => JSON.stringify(replay.value?.summary ?? {}, null, 2));
const replayEventsJson = computed(() => JSON.stringify(replay.value?.events ?? [], null, 2));
const runStatusLabel = computed(() => {
  const status = run.value?.status ?? 'created';
  const labels: Record<RunDto['status'], string> = {
    created: 'создан',
    queued: 'в очереди',
    running: 'выполняется',
    finished: 'завершен',
    failed: 'ошибка',
    timeout: 'таймаут',
    canceled: 'отменен',
  };
  return labels[status];
});
const runStatusTone = computed<'idle' | 'active' | 'success' | 'danger'>(() => {
  const status = run.value?.status;
  if (!status || status === 'created') return 'idle';
  if (status === 'queued' || status === 'running') return 'active';
  if (status === 'finished') return 'success';
  return 'danger';
});
const runKindLabel = computed(() => {
  const kind = run.value?.run_kind;
  if (kind === 'single_task') return 'задача';
  if (kind === 'training_match') return 'тренировка';
  if (kind === 'competition_match') return 'соревнование';
  return 'run';
});
const rendererStatusLabel = computed(() => {
  if (!watchContext.value?.renderer_url) return 'без визуализации';
  return rendererReady.value ? 'готова' : 'загружается';
});
const replayFrames = computed<ReplayFrameView[]>(() => {
  const normalized: ReplayFrameView[] = [];
  const rawFrames = replay.value?.frames;
  if (!rawFrames || rawFrames.length === 0) {
    return normalized;
  }
  for (let index = 0; index < rawFrames.length; index += 1) {
    const item = rawFrames[index];
    if (!isRecord(item)) continue;
    const tickRaw = item.tick;
    const phaseRaw = item.phase;
    const frameRaw = item.frame;
    normalized.push({
      tick: typeof tickRaw === 'number' && Number.isFinite(tickRaw) ? tickRaw : index,
      phase: typeof phaseRaw === 'string' ? phaseRaw : run.value?.status ?? 'unknown',
      frame: isRecord(frameRaw) ? frameRaw : {},
    });
  }
  return normalized;
});

const currentReplayFrame = computed<ReplayFrameView | null>(() => {
  if (replayFrames.value.length === 0) return null;
  const index = Math.max(0, Math.min(replayFrameIndex.value, replayFrames.value.length - 1));
  return replayFrames.value[index] ?? null;
});

const replayFrameTick = computed(() => currentReplayFrame.value?.tick ?? 0);
const botConsoleLines = computed<BotConsoleLine[]>(() => {
  const lines: BotConsoleLine[] = [];
  const replayEvents = replay.value?.events ?? [];
  replayEvents.forEach((event, index) => {
    appendConsoleLine(lines, event, `event-${index}`);
  });

  const rawFrames = replay.value?.frames ?? [];
  rawFrames.forEach((frame, index) => {
    if (!isRecord(frame)) return;
    const tick = normalizeTick(frame.tick, index);
    const framePayload = isRecord(frame.frame) ? frame.frame : frame;
    appendConsoleCollection(lines, framePayload.prints, tick, '', `frame-${index}-prints`);
    appendConsoleCollection(lines, framePayload.logs, tick, '', `frame-${index}-logs`);
    appendConsoleCollection(lines, framePayload.console, tick, '', `frame-${index}-console`);
    appendConsoleCollection(lines, framePayload.stdout, tick, '', `frame-${index}-stdout`);
  });

  if (replayEvents.length === 0 && run.value?.result_payload) {
    appendConsoleCollection(lines, run.value.result_payload.prints, 0, '', 'result-prints');
    appendConsoleCollection(lines, run.value.result_payload.logs, 0, '', 'result-logs');
    appendConsoleCollection(lines, run.value.result_payload.stdout, 0, '', 'result-stdout');
  }

  return lines.sort((left, right) => left.tick - right.tick || left.id.localeCompare(right.id));
});
const currentConsoleLines = computed(() => {
  if (replayFrames.value.length === 0) {
    return botConsoleLines.value;
  }
  return botConsoleLines.value.filter((line) => line.tick <= replayFrameTick.value);
});
const canPlayReplay = computed(() => replayFrames.value.length > 1);
const canStepBackward = computed(() => replayFrames.value.length > 0 && replayFrameIndex.value > 0);
const canStepForward = computed(
  () => replayFrames.value.length > 0 && replayFrameIndex.value < replayFrames.value.length - 1,
);
const shouldAutoplayReplay = computed(() => isEmbedded.value || route.query.autoplay === '1');
const isReplayAtLastFrame = computed(
  () => replayFrames.value.length === 0 || replayFrameIndex.value >= replayFrames.value.length - 1,
);

function isTerminalStatus(status: RunDto['status']): boolean {
  return ['finished', 'failed', 'timeout', 'canceled'].includes(status);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeTick(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function appendConsoleLine(lines: BotConsoleLine[], raw: unknown, id: string, fallbackTick = 0): void {
  if (typeof raw === 'string') {
    appendConsoleMessage(lines, raw, fallbackTick, '', id);
    return;
  }
  if (!isRecord(raw)) return;

  const type = typeof raw.type === 'string' ? raw.type : '';
  const hasConsoleShape =
    type === 'bot_print' ||
    type === 'print' ||
    type === 'stdout' ||
    type === 'bot_stdout' ||
    type === 'console' ||
    'stdout' in raw;
  if (!hasConsoleShape) return;

  const messageRaw = raw.message ?? raw.text ?? raw.line ?? raw.stdout ?? raw.value;
  const message = typeof messageRaw === 'string' ? messageRaw : String(messageRaw ?? '');
  if (!message) return;
  const tick = normalizeTick(raw.tick ?? raw.turn ?? raw.step ?? raw.frame, fallbackTick);
  const roleRaw = raw.role ?? raw.slot ?? raw.slot_key ?? raw.team_id ?? raw.bot;
  const role = typeof roleRaw === 'string' || typeof roleRaw === 'number' ? String(roleRaw) : '';
  appendConsoleMessage(lines, message, tick, role, id);
}

function appendConsoleCollection(
  lines: BotConsoleLine[],
  raw: unknown,
  tick: number,
  role: string,
  idPrefix: string,
): void {
  if (raw === undefined || raw === null) return;
  if (typeof raw === 'string') {
    appendConsoleMessage(lines, raw, tick, role, idPrefix);
    return;
  }
  if (Array.isArray(raw)) {
    raw.forEach((item, index) => appendConsoleLine(lines, item, `${idPrefix}-${index}`, tick));
    return;
  }
  appendConsoleLine(lines, raw, idPrefix, tick);
}

function appendConsoleMessage(
  lines: BotConsoleLine[],
  message: string,
  tick: number,
  role: string,
  idPrefix: string,
): void {
  const chunks = message.split(/\r?\n/);
  chunks.forEach((chunk, index) => {
    if (!chunk) return;
    lines.push({
      id: `${idPrefix}-${index}`,
      tick,
      role,
      message: chunk,
    });
  });
}

function appendRendererLog(level: RendererLogItem['level'], message: string): void {
  rendererLogCounter += 1;
  const timestamp = new Date().toISOString().slice(11, 19);
  rendererLogs.value = [
    {
      id: rendererLogCounter,
      level,
      message,
      timestamp,
    },
    ...rendererLogs.value,
  ].slice(0, 40);
}

function sendToRenderer(message: Record<string, unknown>): void {
  const frame = rendererFrameRef.value;
  if (!frame || !frame.contentWindow) {
    return;
  }
  frame.contentWindow.postMessage(sanitizeForPostMessage(message), window.location.origin);
}

function sanitizeForPostMessage(value: unknown): unknown {
  try {
    return JSON.parse(JSON.stringify(value ?? {}));
  } catch {
    return {};
  }
}

function sendRendererInit(): void {
  if (!watchContext.value || !run.value) return;
  sendToRenderer({
    type: 'agp.renderer.init',
    payload: {
      gameId: watchContext.value.game_id,
      gameSlug: watchContext.value.game_slug,
      mode: run.value.run_kind,
      runId: run.value.run_id,
    },
  });
}

function sendRendererStateAndResult(): void {
  if (!run.value) return;
  const activeReplayFrame = currentReplayFrame.value;
  if (isTerminalStatus(run.value.status) && shouldAutoplayReplay.value && !activeReplayFrame && !replay.value) {
    return;
  }
  rendererTick.value = activeReplayFrame?.tick ?? rendererTick.value + 1;
  const rendererPhase = activeReplayFrame?.phase ?? run.value.status;
  const rendererFrame =
    activeReplayFrame?.frame ??
    (isTerminalStatus(run.value.status) && shouldAutoplayReplay.value ? {} : run.value.result_payload ?? {});

  sendToRenderer({
    type: 'agp.renderer.state',
    payload: {
      tick: rendererTick.value,
      phase: rendererPhase,
      frame: rendererFrame,
    },
  });
  const canSendTerminalResult =
    replay.value !== null ? isReplayAtLastFrame.value : !shouldAutoplayReplay.value;
  if (isTerminalStatus(run.value.status) && canSendTerminalResult) {
    sendToRenderer({
      type: 'agp.renderer.result',
      payload:
        run.value.result_payload ??
        {
          status: run.value.status,
          error_message: run.value.error_message,
        },
    });
  }
}

function replaySpeedFromQuery(): number {
  const raw = route.query.speed_ms;
  const value = typeof raw === 'string' ? Number(raw) : NaN;
  if (!Number.isFinite(value)) return 1000;
  return Math.max(150, Math.min(3000, value));
}

function onRendererLoad(): void {
  appendRendererLog('info', 'iframe loaded');
  sendRendererInit();
  sendRendererStateAndResult();
}

function restartRenderer(): void {
  rendererKey.value += 1;
  rendererReady.value = false;
  rendererTick.value = 0;
  appendRendererLog('warn', 'renderer restarted');
}

function stopReplayPlayback(): void {
  if (!replayPlaybackHandle) {
    replayIsPlaying.value = false;
    return;
  }
  clearInterval(replayPlaybackHandle);
  replayPlaybackHandle = null;
  replayIsPlaying.value = false;
}

function startReplayPlayback(): void {
  if (!canPlayReplay.value) {
    replayIsPlaying.value = false;
    return;
  }
  stopReplayPlayback();
  replayIsPlaying.value = true;
  replayPlaybackHandle = setInterval(() => {
    if (replayFrameIndex.value >= replayFrames.value.length - 1) {
      stopReplayPlayback();
      return;
    }
    replayFrameIndex.value += 1;
  }, replaySpeedMs.value);
}

function toggleReplayPlay(): void {
  if (replayIsPlaying.value) {
    stopReplayPlayback();
    return;
  }
  startReplayPlayback();
}

function stepReplay(delta: -1 | 1): void {
  stopReplayPlayback();
  if (delta < 0 && canStepBackward.value) {
    replayFrameIndex.value -= 1;
    return;
  }
  if (delta > 0 && canStepForward.value) {
    replayFrameIndex.value += 1;
  }
}

function clampReplayFrameIndex(): void {
  if (replayFrames.value.length === 0) {
    replayFrameIndex.value = 0;
    return;
  }
  replayFrameIndex.value = Math.max(0, Math.min(replayFrameIndex.value, replayFrames.value.length - 1));
}

function onRendererMessage(event: MessageEvent): void {
  const frame = rendererFrameRef.value;
  if (!frame || event.source !== frame.contentWindow) {
    return;
  }
  const data = event.data;
  if (!data || typeof data !== 'object') {
    return;
  }
  const type = 'type' in data ? String(data.type) : '';
  if (!type.startsWith('agp.renderer.')) {
    return;
  }
  if (type === 'agp.renderer.ready') {
    rendererReady.value = true;
    const version = (data as { payload?: { version?: string } }).payload?.version;
    appendRendererLog('info', version ? `renderer ready v${version}` : 'renderer ready');
    sendRendererInit();
    sendRendererStateAndResult();
    return;
  }
  if (type === 'agp.renderer.error') {
    const message =
      (data as { payload?: { message?: string } }).payload?.message ??
      'renderer reported unknown error';
    appendRendererLog('error', String(message));
    return;
  }
  if (type === 'agp.renderer.event') {
    const eventName = (data as { payload?: { name?: string } }).payload?.name ?? 'event';
    appendRendererLog('info', `renderer event: ${String(eventName)}`);
    return;
  }
  appendRendererLog('info', `message: ${type}`);
}

async function loadRunAndContext(runId: string): Promise<void> {
  const [freshContext, freshRun] = await Promise.all([getRunWatchContext(runId), getRun(runId)]);
  watchContext.value = freshContext;
  run.value = freshRun;
}

async function ensureReplayLoaded(runId: string): Promise<void> {
  if (replay.value?.run_id === runId || isReplayLoading.value) {
    return;
  }
  isReplayLoading.value = true;
  replayError.value = '';
  try {
    replay.value = await getRunReplay(runId);
    clampReplayFrameIndex();
    if (replayFrames.value.length > 0) {
      replayFrameIndex.value = shouldAutoplayReplay.value ? 0 : replayFrames.value.length - 1;
      sendRendererStateAndResult();
      if (shouldAutoplayReplay.value && replayFrames.value.length > 1) {
        startReplayPlayback();
      }
    }
  } catch (error) {
    replayError.value = error instanceof Error ? error.message : 'Повтор пока недоступен';
  } finally {
    isReplayLoading.value = false;
  }
}

async function bootstrapPage(): Promise<void> {
  const runId = String(route.params.runId || '').trim();
  if (!runId) {
    errorMessage.value = 'Не передан runId';
    return;
  }
  isLoading.value = true;
  errorMessage.value = '';
  replay.value = null;
  replayError.value = '';
  try {
    await loadRunAndContext(runId);
    if (run.value && !isTerminalStatus(run.value.status)) {
      startRunLiveUpdates(runId);
    } else if (run.value && isTerminalStatus(run.value.status)) {
      await ensureReplayLoaded(runId);
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить run';
  } finally {
    isLoading.value = false;
  }
}

function startRunLiveUpdates(runId: string): void {
  stopRunLiveUpdates();
  if (typeof EventSource === 'undefined') {
    appendRendererLog('warn', 'EventSource недоступен, переключено на polling');
    startRunPolling(runId);
    return;
  }

  const source = new EventSource(
    `/api/v1/runs/${encodeURIComponent(runId)}/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`,
  );
  runEventSource = source;
  liveMode.value = 'sse';
  appendRendererLog('info', 'SSE stream connected');

  const applyRunUpdate = (candidate: RunDto | null): void => {
    if (!candidate) {
      appendRendererLog('warn', 'Некорректное сообщение run из SSE');
      return;
    }
    run.value = candidate;
    sendRendererStateAndResult();
  };

  source.addEventListener('agp.update', (event: MessageEvent) => {
    try {
      const envelope = JSON.parse(event.data) as StreamEnvelopeDto<RunDto>;
      if (envelope.channel !== 'run') return;
      applyRunUpdate(envelope.payload ?? null);
    } catch {
      appendRendererLog('warn', 'Некорректное agp.update сообщение из SSE');
    }
  });

  source.addEventListener('run', (event: MessageEvent) => {
    try {
      applyRunUpdate(JSON.parse(event.data) as RunDto);
    } catch {
      appendRendererLog('warn', 'Некорректное legacy run сообщение из SSE');
    }
  });

  const handleTerminal = async (statusFromEnvelope?: string): Promise<void> => {
    if (run.value && statusFromEnvelope) {
      run.value = {
        ...run.value,
        status: statusFromEnvelope as RunDto['status'],
      };
      sendRendererStateAndResult();
    }
    if (run.value) {
      await ensureReplayLoaded(run.value.run_id);
    }
    stopRunLiveUpdates();
  };

  source.addEventListener('agp.terminal', (event: MessageEvent) => {
    try {
      const envelope = JSON.parse(event.data) as StreamEnvelopeDto<Record<string, unknown>>;
      if (envelope.channel !== 'run') return;
      void handleTerminal(envelope.status);
    } catch {
      void handleTerminal();
    }
  });

  source.addEventListener('terminal', () => {
    void handleTerminal();
  });

  source.onerror = () => {
    if (run.value && isTerminalStatus(run.value.status)) {
      stopRunLiveUpdates();
      return;
    }
    appendRendererLog('warn', 'SSE stream disconnected, fallback to polling');
    stopRunLiveUpdates();
    startRunPolling(runId);
  };
}

function startRunPolling(runId: string): void {
  liveMode.value = 'polling';
  stopRunPolling();
  runPollingHandle = setInterval(async () => {
    try {
      run.value = await getRun(runId);
      sendRendererStateAndResult();
      if (run.value && isTerminalStatus(run.value.status)) {
        stopRunPolling();
        await ensureReplayLoaded(runId);
      }
    } catch {
      // keep the latest known state and continue polling
    }
  }, 1200);
}

function stopRunPolling(): void {
  if (!runPollingHandle) return;
  clearInterval(runPollingHandle);
  runPollingHandle = null;
}

function stopRunEventStream(): void {
  if (!runEventSource) return;
  runEventSource.close();
  runEventSource = null;
}

function stopRunLiveUpdates(): void {
  stopRunEventStream();
  stopRunPolling();
  liveMode.value = 'idle';
}

watch(replayFrames, () => {
  clampReplayFrameIndex();
  if (replayFrames.value.length <= 1) {
    stopReplayPlayback();
  }
});

watch(replayFrameIndex, () => {
  clampReplayFrameIndex();
  sendRendererStateAndResult();
});

watch(replaySpeedMs, () => {
  if (replayIsPlaying.value) {
    startReplayPlayback();
  }
});

onMounted(async () => {
  window.addEventListener('message', onRendererMessage);
  await bootstrapPage();
});

onUnmounted(() => {
  window.removeEventListener('message', onRendererMessage);
  stopReplayPlayback();
  stopRunLiveUpdates();
});
</script>

<style scoped>
.agp-watch-columns {
  grid-template-columns: minmax(0, 1.25fr) minmax(20rem, 0.75fr);
  gap: 0.5rem;
}

.agp-watch-page--embedded {
  height: 100dvh;
  background: #030712;
}

.agp-watch-page {
  background: #06101f;
  color: #dbeafe;
}

.agp-watch-page--embedded .agp-watch-columns {
  height: 100dvh;
  grid-template-columns: 1fr;
}

.agp-watch-page--embedded .agp-viewer-card {
  border: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 0.75rem;
}

.agp-watch-page--embedded .agp-viewer-card .agp-viewer-frame {
  height: auto !important;
  min-height: 0;
}

.agp-watch-page .agp-viewer-card .agp-viewer-frame {
  height: clamp(22rem, 64vh, 46rem);
}

.agp-watch-renderer-state {
  left: auto;
  right: 0.75rem;
  max-width: min(26rem, calc(100% - 1.5rem));
}

.agp-watch-side-card {
  position: sticky;
  top: 0.75rem;
  overflow: hidden;
  border-color: rgba(135, 226, 255, 0.22);
  border-radius: 0;
  background: #07101c;
  color: #dbeafe;
}

.agp-watch-side-card h2,
.agp-watch-side-card h3,
.agp-watch-side-card strong,
.agp-watch-side-card summary {
  color: #e5f3ff;
}

.agp-watch-side-card .text-muted {
  color: #8ea7c1 !important;
}

.agp-watch-side-card hr {
  border-color: rgba(148, 163, 184, 0.22);
  opacity: 1;
}

.agp-watch-side-card .btn-outline-secondary {
  border-color: rgba(148, 163, 184, 0.38);
  color: #dbeafe;
  background: rgba(15, 23, 42, 0.72);
}

.agp-watch-side-card .btn-outline-secondary:hover:not(:disabled) {
  border-color: rgba(125, 211, 252, 0.65);
  background: rgba(14, 116, 144, 0.42);
  color: #fff;
}

.agp-watch-side-card .form-select,
.agp-watch-side-card .form-range {
  color-scheme: dark;
}

.agp-watch-side-card .form-select {
  border-color: rgba(148, 163, 184, 0.36);
  background-color: #0f172a;
  color: #dbeafe;
}

.agp-watch-side-card .agp-card-soft {
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.72);
  color: #dbeafe;
}

.agp-watch-side-card .table {
  --bs-table-bg: transparent;
  --bs-table-color: #dbeafe;
  --bs-table-border-color: rgba(148, 163, 184, 0.22);
  margin-bottom: 0;
}

.agp-watch-side-card .table th {
  color: #8ea7c1;
  font-weight: 700;
}

.agp-watch-side-card pre {
  max-height: 18rem;
  overflow: auto;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 0.35rem;
  background: #020617;
  color: #dbeafe;
  padding: 0.65rem;
}

.agp-watch-side-card .list-group-item {
  border-color: rgba(148, 163, 184, 0.18);
  background: transparent;
  color: #dbeafe;
}

.agp-watch-stat {
  display: grid;
  gap: 0.15rem;
  padding: 0.55rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
}

.agp-watch-stat strong {
  font-size: 0.95rem;
}

.agp-bot-console {
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 8px;
  background: #050812;
  color: #d1d5db;
}

.agp-bot-console-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.92);
  font-size: 0.78rem;
  letter-spacing: 0;
  text-transform: uppercase;
}

.agp-bot-console-body {
  max-height: 9.5rem;
  overflow: auto;
  padding: 0.6rem 0.75rem;
  font-size: 0.82rem;
}

.agp-bot-console-empty {
  color: #64748b;
  font-style: italic;
}

.agp-bot-console-line {
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
  min-height: 1.35rem;
}

.agp-bot-console-role {
  max-width: 8rem;
  overflow: hidden;
  padding: 0.08rem 0.35rem;
  border: 1px solid rgba(45, 212, 191, 0.36);
  border-radius: 999px;
  color: #99f6e4;
  font-size: 0.72rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agp-bot-console-message {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
  color: #e5e7eb;
}

@media (max-width: 992px) {
  .agp-watch-columns {
    grid-template-columns: 1fr;
  }

  .agp-watch-side-card {
    position: static;
  }

  .agp-watch-page .agp-viewer-card .agp-viewer-frame {
    height: 22rem;
  }

  .agp-bot-console-line {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .agp-bot-console-role {
    display: none;
  }
}
</style>
