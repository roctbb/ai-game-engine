<template>
  <section class="agp-grid agp-task-workspace agp-watch-page" :class="{ 'agp-watch-page--embedded': isEmbedded }">
    <header v-if="!isEmbedded" class="agp-task-header">
      <div class="agp-task-header-main">
        <RouterLink :to="backTarget" class="agp-back-link" :title="backLabel" :aria-label="backLabel">←</RouterLink>
        <h1>{{ watchContext?.game_title || watchContext?.game_slug || 'Просмотр запуска' }}</h1>
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
          :disabled="replayFrames.length <= 1 || firstReplayLockActive"
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
          <div v-if="showWinnerBanner" class="agp-watch-winner-banner">
            <span>Победитель</span>
            <strong>{{ finalWinnerLabel }}</strong>
          </div>
          <div v-else-if="firstReplayLockActive" class="agp-watch-replay-lock">
            <strong>Идет первый показ</strong>
            <span>Перемотка откроется после реплея.</span>
          </div>
          <div v-if="safeRendererUrl" class="agp-viewer-frame">
            <iframe
              ref="rendererFrameRef"
              :key="rendererKey"
              :src="safeRendererUrl"
              title="Визуализация игры"
              sandbox="allow-scripts allow-same-origin"
              @load="onRendererLoad"
            ></iframe>
          </div>
          <div v-else class="agp-card-soft p-3 text-muted small">
            Для этой игры визуализация не настроена.
          </div>
          <section v-if="showBotConsole" class="agp-bot-console" aria-label="Вывод бота">
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
          <header class="agp-match-panel-head">
            <div>
              <h2 class="h6 mb-1">Статистика матча</h2>
              <span>{{ replayFrames.length ? `кадр ${replayFrameIndex + 1}/${replayFrames.length}` : runStatusLabel }}</span>
            </div>
            <span class="agp-run-pill" :class="`agp-run-pill--${runStatusTone}`">{{ runStatusLabel }}</span>
          </header>

          <div v-if="showWinnerBanner" class="agp-watch-side-winner">
            <span>Победитель</span>
            <strong>{{ finalWinnerLabel }}</strong>
          </div>
          <div v-else-if="firstReplayLockActive" class="agp-watch-side-lock">
            Первый показ идет синхронно. Перемотка временно закрыта.
          </div>

          <div v-if="matchPlayerStats.length" class="agp-match-scoreboard">
            <article
              v-for="player in matchPlayerStats"
              :key="player.id"
              class="agp-match-player"
              :class="{ 'agp-match-player--self': player.isSelf, 'agp-match-player--out': !player.alive }"
            >
              <div class="agp-match-player-rank">{{ player.placeLabel }}</div>
              <div class="agp-match-player-main">
                <strong>{{ player.name }}</strong>
                <span v-if="player.detailLabel">{{ player.detailLabel }}</span>
                <div class="agp-match-bars">
                  <span>
                    <i :style="{ width: `${player.lifePercent}%` }"></i>
                  </span>
                  <span>
                    <i :style="{ width: `${player.shieldPercent}%` }"></i>
                  </span>
                </div>
              </div>
              <div class="agp-match-player-score">
                <strong>{{ player.scoreLabel }}</strong>
                <span>{{ player.alive ? 'в игре' : 'выбыл' }}</span>
              </div>
            </article>
          </div>
          <div v-else class="agp-match-empty">
            Статистика появится вместе с кадрами матча.
          </div>

          <section class="agp-match-mini-stats" aria-label="Показатели матча">
            <div>
              <span>Лидер</span>
              <strong>{{ matchLeaderLabel }}</strong>
            </div>
            <div>
              <span>Ходов</span>
              <strong>{{ replayFrameTick }}</strong>
            </div>
            <div>
              <span>Игроков</span>
              <strong>{{ matchPlayerStats.length || '—' }}</strong>
            </div>
          </section>

          <h3 class="h6 mb-2 mt-3">Лог ходов</h3>
          <div v-if="!replay" class="text-muted small">Лог появится вместе с повтором.</div>
          <div v-else-if="moveLogItems.length === 0" class="text-muted small">
            В повторе нет событий ходов.
          </div>
          <div v-else class="agp-watch-move-log">
            <div
              v-for="item in visibleMoveLogItems"
              :key="item.id"
              class="agp-watch-move-row"
              :class="`agp-watch-move-row--${item.tone}`"
            >
              <span class="mono small">#{{ item.tick }}</span>
              <strong v-if="item.actor">{{ item.actor }}</strong>
              <span v-else class="text-muted small">событие</span>
              <span class="agp-watch-move-action">{{ item.action }}</span>
              <small v-if="item.detail">{{ item.detail }}</small>
            </div>
          </div>

          <details v-if="canSeeTechnicalDetails" class="agp-tech-details mt-3">
            <summary class="agp-details-summary">Технические детали</summary>
            <div class="agp-watch-stat mt-2">
              <span class="text-muted small">Визуализация</span>
              <strong>{{ rendererStatusLabel }}</strong>
            </div>
            <div class="agp-watch-stat">
              <span class="text-muted small">Тип</span>
              <strong>{{ runKindLabel }}</strong>
            </div>
            <div class="agp-watch-stat">
              <span class="text-muted small">Обновления</span>
              <strong class="mono">{{ liveMode }}</strong>
            </div>
            <div v-if="run.error_message" class="mt-3">
              <RunReasonBadge :reason="run.error_message" :show-raw="false" />
            </div>
          </details>

          <div class="agp-replay-foot">
            <div v-if="isReplayLoading" class="text-muted small">Загрузка повтора...</div>
            <div v-else-if="replayError" class="text-danger small">{{ replayError }}</div>
            <div v-else-if="!replay" class="text-muted small">Повтор появится после завершения запуска.</div>
            <div v-else class="agp-watch-replay-summary">
              <span class="text-muted small">Кадр</span>
              <strong class="mono">{{ replayFrameIndex + 1 }}/{{ replayFrames.length }}</strong>
            </div>
          </div>
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
import { sanitizeForPostMessage } from '../lib/postMessage';
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

interface MoveLogItem {
  id: string;
  tick: number;
  actor: string;
  action: string;
  detail: string;
  tone: 'move' | 'event' | 'error';
}

interface MatchPlayerStat {
  id: string;
  name: string;
  teamId: string;
  teamLabel: string;
  detailLabel: string;
  place: number | null;
  placeLabel: string;
  score: number | null;
  scoreLabel: string;
  life: number | null;
  shield: number | null;
  lifePercent: number;
  shieldPercent: number;
  alive: boolean;
  isSelf: boolean;
}

const route = useRoute();
const sessionStore = useSessionStore();
const isEmbedded = computed(() => route.query.embed === '1');
const showBotConsole = computed(() => route.query.show_print !== '0');
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
const nowMs = ref(Date.now());
let rendererLogCounter = 0;
let runPollingHandle: ReturnType<typeof setInterval> | null = null;
let runEventSource: EventSource | null = null;
let replayPlaybackHandle: ReturnType<typeof setInterval> | null = null;
let replayClockHandle: ReturnType<typeof setInterval> | null = null;
let isPollingRun = false;
let pendingRunPoll = false;
let runPollingToken = 0;

const safeRendererUrl = computed(() => {
  const url = watchContext.value?.renderer_url?.trim() ?? '';
  return url.startsWith('/api/v1/renderers/') ? url : '';
});
const canRestartRenderer = computed(() => canSeeTechnicalDetails.value && Boolean(safeRendererUrl.value));
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
  return 'запуск';
});
const backTarget = computed(() => {
  if (run.value?.run_kind === 'single_task') return '/tasks';
  return '/lobbies';
});
const backLabel = computed(() => {
  if (run.value?.run_kind === 'single_task') return 'К задачам';
  return 'К лобби';
});
const rendererStatusLabel = computed(() => {
  if (!safeRendererUrl.value) return watchContext.value?.renderer_url ? 'ошибка renderer url' : 'без визуализации';
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

const participantNamesByTeam = computed<Record<string, string>>(() => {
  const names: Record<string, string> = {};
  for (const participant of watchContext.value?.participants ?? []) {
    const displayName = participant.display_name.trim();
    if (displayName) {
      names[participant.team_id] = displayName;
    }
  }
  return names;
});

const currentReplayFrame = computed<ReplayFrameView | null>(() => {
  if (replayFrames.value.length === 0) return null;
  const index = Math.max(0, Math.min(replayFrameIndex.value, replayFrames.value.length - 1));
  return replayFrames.value[index] ?? null;
});

const replayFrameTick = computed(() => currentReplayFrame.value?.tick ?? 0);
const matchPlayerStats = computed<MatchPlayerStat[]>(() => {
  const players = new Map<string, MatchPlayerStat>();
  const frame = currentReplayFrame.value?.frame ?? null;
  collectFramePlayers(players, frame);
  if (players.size === 0) {
    collectSummaryPlayers(players);
  } else {
    mergeSummaryPlacements(players);
  }
  return [...players.values()].sort((left, right) => {
    const leftPlace = left.place ?? Number.POSITIVE_INFINITY;
    const rightPlace = right.place ?? Number.POSITIVE_INFINITY;
    if (leftPlace !== rightPlace) return leftPlace - rightPlace;
    return (right.score ?? -Infinity) - (left.score ?? -Infinity);
  });
});
const matchLeaderLabel = computed(() => matchPlayerStats.value[0]?.name ?? '—');
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
const moveLogItems = computed<MoveLogItem[]>(() => {
  const items: MoveLogItem[] = [];
  const replayEvents = replay.value?.events ?? [];
  replayEvents.forEach((event, index) => {
    const item = createMoveLogItem(event, index);
    if (item) {
      items.push(item);
    }
  });
  return items.sort((left, right) => left.tick - right.tick || left.id.localeCompare(right.id));
});
const visibleMoveLogItems = computed(() => {
  const items = replayFrames.value.length === 0
    ? moveLogItems.value
    : moveLogItems.value.filter((item) => item.tick <= replayFrameTick.value);
  return items.slice(-14);
});
const firstReplayFrameMs = computed(() => replayFrameMsFromQuery());
const firstReplayStartedAtMs = computed(() => {
  const rawSyncedStart = route.query.sync_started_at;
  if (typeof rawSyncedStart === 'string' && rawSyncedStart) {
    const value = Date.parse(rawSyncedStart);
    if (Number.isFinite(value)) return value;
  }
  const finishedAt = run.value?.finished_at;
  if (!finishedAt || route.query.unlock_replay === '1') return null;
  const value = Date.parse(finishedAt);
  return Number.isFinite(value) ? value : null;
});
const firstReplayAllowedFrameIndex = computed(() => {
  if (firstReplayStartedAtMs.value === null || replayFrames.value.length === 0) return replayFrames.value.length - 1;
  const elapsedMs = Math.max(0, nowMs.value - firstReplayStartedAtMs.value);
  return Math.min(replayFrames.value.length - 1, Math.floor(elapsedMs / firstReplayFrameMs.value));
});
const firstReplayLockActive = computed(() => {
  if (firstReplayStartedAtMs.value === null || replayFrames.value.length <= 1) return false;
  return firstReplayAllowedFrameIndex.value < replayFrames.value.length - 1;
});
const canPlayReplay = computed(() => replayFrames.value.length > 1);
const canStepBackward = computed(() => !firstReplayLockActive.value && replayFrames.value.length > 0 && replayFrameIndex.value > 0);
const canStepForward = computed(
  () => !firstReplayLockActive.value && replayFrames.value.length > 0 && replayFrameIndex.value < replayFrames.value.length - 1,
);
const shouldAutoplayReplay = computed(() => isEmbedded.value || route.query.autoplay === '1');
const isReplayAtLastFrame = computed(
  () => replayFrames.value.length === 0 || replayFrameIndex.value >= replayFrames.value.length - 1,
);
const showWinnerBanner = computed(() => replayFrames.value.length > 0 && isReplayAtLastFrame.value && !firstReplayLockActive.value);
const finalWinnerLabel = computed(() => {
  const explicitWinner = primaryReplayWinnerTeamId(explicitReplayWinnerTeamIds());
  if (explicitWinner) return playerDisplayName(explicitWinner, compactTeamLabel(explicitWinner));
  const placedWinners = matchPlayerStats.value.filter((player) => player.place === 1);
  if (placedWinners.length === 1) return placedWinners[0].name;
  if (placedWinners.length > 1) {
    const bestScore = Math.max(...placedWinners.map((player) => player.score ?? Number.NEGATIVE_INFINITY));
    const scoredWinner = placedWinners.find((player) => (player.score ?? Number.NEGATIVE_INFINITY) === bestScore);
    if (scoredWinner) return scoredWinner.name;
  }
  return matchLeaderLabel.value;
});

function isTerminalStatus(status: RunDto['status']): boolean {
  return ['finished', 'failed', 'timeout', 'canceled'].includes(status);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function explicitReplayWinnerTeamIds(): string[] {
  const summary = isRecord(replay.value?.summary) ? replay.value.summary : {};
  const payload = isRecord(run.value?.result_payload) ? run.value.result_payload : {};
  const candidates = [
    summary.winner_team_ids,
    summary.winners,
    summary.winner,
    payload.winner_team_ids,
    payload.winners,
    payload.winner,
  ];
  const result: string[] = [];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      for (const value of candidate) {
        if (typeof value === 'string' && value && !result.includes(value)) result.push(value);
      }
    } else if (typeof candidate === 'string' && candidate && !result.includes(candidate)) {
      result.push(candidate);
    }
  }
  return result;
}

function primaryReplayWinnerTeamId(teamIds: string[]): string {
  const uniqueTeamIds = [...new Set(teamIds.filter(Boolean))];
  if (uniqueTeamIds.length <= 1) return uniqueTeamIds[0] ?? '';
  const scores = replayScoresByTeam();
  const placements = replayPlacementsByTeam();
  return uniqueTeamIds.sort((left, right) => {
    const leftPlace = placements[left] ?? Number.POSITIVE_INFINITY;
    const rightPlace = placements[right] ?? Number.POSITIVE_INFINITY;
    if (leftPlace !== rightPlace) return leftPlace - rightPlace;
    const leftScore = scores[left] ?? Number.NEGATIVE_INFINITY;
    const rightScore = scores[right] ?? Number.NEGATIVE_INFINITY;
    if (leftScore !== rightScore) return rightScore - leftScore;
    return compactTeamLabel(left).localeCompare(compactTeamLabel(right), 'ru');
  })[0] ?? '';
}

function replayScoresByTeam(): Record<string, number> {
  const summary = isRecord(replay.value?.summary) ? replay.value.summary : {};
  const payload = isRecord(run.value?.result_payload) ? run.value.result_payload : {};
  const rawScores = isRecord(summary.scores) ? summary.scores : isRecord(payload.scores) ? payload.scores : {};
  const result: Record<string, number> = {};
  for (const [teamId, score] of Object.entries(rawScores)) {
    const value = numericOrNull(score);
    if (value !== null) result[teamId] = value;
  }
  return result;
}

function replayPlacementsByTeam(): Record<string, number> {
  const summary = isRecord(replay.value?.summary) ? replay.value.summary : {};
  const payload = isRecord(run.value?.result_payload) ? run.value.result_payload : {};
  const rawPlacements = isRecord(summary.placements)
    ? summary.placements
    : isRecord(payload.placements)
      ? payload.placements
      : {};
  const result: Record<string, number> = {};
  for (const [teamId, placement] of Object.entries(rawPlacements)) {
    const value = numericOrNull(placement);
    if (value !== null) result[teamId] = value;
  }
  return result;
}

function normalizeTick(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function collectFramePlayers(players: Map<string, MatchPlayerStat>, value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach((item) => collectFramePlayers(players, item));
    return;
  }
  if (!isRecord(value)) return;

  collectRoleMapFramePlayers(players, value);
  collectSnakeFramePlayers(players, value);

  const nameRaw = value.name ?? value.player ?? value.role ?? value.key;
  const hasPlayerShape =
    nameRaw !== undefined &&
    (
      value.score !== undefined ||
      value.points !== undefined ||
      value.life !== undefined ||
      value.hp !== undefined ||
      value.coins !== undefined ||
      value.food_eaten !== undefined ||
      value.alive !== undefined
    );
  if (hasPlayerShape) {
    const id = String(value.team_id ?? value.key ?? value.role ?? value.name ?? `player-${players.size + 1}`);
    const teamId = typeof value.team_id === 'string' ? value.team_id : id;
    upsertPlayerStat(players, buildPlayerStat({
      id,
      name: playerDisplayName(teamId, String(nameRaw)),
      teamId,
      score: numericOrNull(value.score ?? value.points),
      life: numericOrNull(value.life ?? value.hp ?? (Array.isArray(value.body) ? value.body.length : null)),
      shield: numericOrNull(value.shield),
      alive: booleanOrDefault(value.alive, numericOrNull(value.life ?? value.hp) !== 0),
      place: summaryPlaceFor(id),
    }));
  }

  Object.values(value).forEach((item) => collectFramePlayers(players, item));
}

function collectRoleMapFramePlayers(players: Map<string, MatchPlayerStat>, frame: Record<string, unknown>): void {
  const positions = isRecord(frame.positions) ? frame.positions : null;
  if (!positions) return;
  const roleEntries = Object.entries(positions).filter(([, value]) => isRecord(value) || Array.isArray(value));
  if (!roleEntries.length) return;

  const batteries = isRecord(frame.batteries) ? frame.batteries : {};
  const collected = isRecord(frame.collected) ? frame.collected : {};
  const carrying = isRecord(frame.carrying) ? frame.carrying : {};
  const delivered = isRecord(frame.delivered) ? frame.delivered : {};
  const throws = isRecord(frame.throws) ? frame.throws : {};
  const frozen = isRecord(frame.frozen) ? frame.frozen : {};
  const labels = isRecord(frame.labels) ? frame.labels : {};
  const invalidMoves = isRecord(frame.invalid_moves) ? frame.invalid_moves : {};
  const slotScores = isRecord(frame.slot_scores) ? frame.slot_scores : {};
  roleEntries.forEach(([role], index) => {
    const label = typeof labels[role] === 'string' ? labels[role] : '';
    const participant = watchContext.value?.participants[index]
      ?? watchContext.value?.participants.find((item) => item.display_name === label);
    const teamId = participant?.team_id ?? role;
    const collectedValue = numericOrNull(collected[role]) ?? 0;
    const carryingValue = numericOrNull(carrying[role]) ?? 0;
    const deliveredValue = numericOrNull(delivered[role]) ?? 0;
    const throwsValue = numericOrNull(throws[role]) ?? 0;
    const frozenValue = numericOrNull(frozen[role]) ?? 0;
    const batteryValue = numericOrNull(batteries[role]);
    const invalidValue = numericOrNull(invalidMoves[role]) ?? 0;
    const score = numericOrNull(slotScores[role])
      ?? (
        Object.keys(delivered).length || Object.keys(carrying).length || Object.keys(throws).length
          ? Math.max(0, deliveredValue * 120 + carryingValue * 30 + throwsValue * 5 - invalidValue * 10)
          : Math.max(0, collectedValue * 100 + (batteryValue ?? 0) - invalidValue * 10)
      );
    upsertPlayerStat(players, buildPlayerStat({
      id: teamId,
      name: participant?.display_name || label || role,
      teamId,
      score,
      life: batteryValue ?? (frozenValue > 0 ? 0 : null),
      shield: null,
      alive: batteryValue === null ? true : batteryValue > 0,
      place: summaryPlaceFor(teamId),
    }));
  });
}

function collectSnakeFramePlayers(players: Map<string, MatchPlayerStat>, frame: Record<string, unknown>): void {
  const snakes = isRecord(frame.snakes) ? frame.snakes : null;
  if (!snakes) return;

  const slotScores = isRecord(frame.slot_scores) ? frame.slot_scores : {};
  Object.entries(snakes).forEach(([role, raw], index) => {
    if (!isRecord(raw)) return;
    const participant = watchContext.value?.participants[index];
    const teamId = typeof raw.team_id === 'string' && raw.team_id
      ? raw.team_id
      : participant?.team_id ?? role;
    const food = numericOrNull(raw.food_eaten) ?? 0;
    const invalid = numericOrNull(raw.invalid_moves) ?? 0;
    const length = Array.isArray(raw.body) ? raw.body.length : null;
    const alive = booleanOrDefault(raw.alive, true);
    const score = numericOrNull(raw.score)
      ?? numericOrNull(slotScores[role])
      ?? Math.max(0, food * 100 + (length ?? 0) * 5 + (alive ? 30 : 0) - invalid * 10);

    upsertPlayerStat(players, buildPlayerStat({
      id: teamId,
      name: typeof raw.name === 'string' && raw.name ? raw.name : participant?.display_name || role,
      teamId,
      score,
      life: length,
      shield: null,
      alive,
      place: summaryPlaceFor(teamId),
    }));
  });
}

function collectSummaryPlayers(players: Map<string, MatchPlayerStat>): void {
  const metrics = isRecord(replay.value?.summary?.metrics) ? replay.value.summary.metrics : {};
  const rawPlayers = Array.isArray(metrics.players) ? metrics.players : [];
  rawPlayers.forEach((raw, index) => {
    if (!isRecord(raw)) return;
    const id = String(raw.team_id ?? raw.key ?? raw.name ?? `summary-${index}`);
    const teamId = typeof raw.team_id === 'string' ? raw.team_id : id;
    players.set(id, buildPlayerStat({
      id,
      name: playerDisplayName(teamId, String(raw.name ?? raw.key ?? id)),
      teamId,
      score: numericOrNull(raw.score ?? raw.points),
      life: numericOrNull(raw.life ?? raw.hp),
      shield: numericOrNull(raw.shield),
      alive: booleanOrDefault(raw.alive, numericOrNull(raw.life ?? raw.hp) !== 0),
      place: summaryPlaceFor(id),
    }));
  });

  const scores = isRecord(replay.value?.summary?.scores)
    ? replay.value.summary.scores
    : isRecord(run.value?.result_payload?.scores)
      ? run.value.result_payload.scores
      : {};
  Object.entries(scores).forEach(([teamId, scoreRaw]) => {
    if (players.has(teamId)) return;
    players.set(teamId, buildPlayerStat({
      id: teamId,
      name: compactTeamLabel(teamId),
      teamId,
      score: numericOrNull(scoreRaw),
      life: null,
      shield: null,
      alive: true,
      place: summaryPlaceFor(teamId),
    }));
  });
}

function mergeSummaryPlacements(players: Map<string, MatchPlayerStat>): void {
  const scores = isRecord(replay.value?.summary?.scores) ? replay.value.summary.scores : {};
  const placements = isRecord(replay.value?.summary?.placements) ? replay.value.summary.placements : {};
  for (const [id, player] of players.entries()) {
    const score = player.score ?? numericOrNull(scores[id]);
    const place = player.place ?? numericOrNull(placements[id]);
    players.set(id, {
      ...player,
      score,
      scoreLabel: score === null ? '—' : Math.round(score).toLocaleString('ru-RU'),
      place,
      placeLabel: place === null ? '•' : String(place),
    });
  }
}

function upsertPlayerStat(players: Map<string, MatchPlayerStat>, next: MatchPlayerStat): void {
  const duplicateId = findDuplicatePlayerId(players, next);
  if (!duplicateId) {
    players.set(next.id, next);
    return;
  }

  const previous = players.get(duplicateId);
  if (!previous) {
    players.set(next.id, next);
    return;
  }

  players.set(duplicateId, buildPlayerStat({
    id: previous.id,
    name: previous.name || next.name,
    teamId: previous.isSelf || next.isSelf ? run.value?.team_id ?? previous.teamId : previous.teamId || next.teamId,
    score: next.score ?? previous.score,
    life: next.life ?? previous.life,
    shield: next.shield ?? previous.shield,
    alive: previous.alive || next.alive,
    place: previous.place ?? next.place,
  }));
}

function findDuplicatePlayerId(players: Map<string, MatchPlayerStat>, next: MatchPlayerStat): string | null {
  const nextName = normalizePlayerName(next.name);
  const nextTeam = normalizePlayerName(next.teamLabel);
  for (const [id, existing] of players.entries()) {
    if (id === next.id) return id;
    const existingName = normalizePlayerName(existing.name);
    const existingTeam = normalizePlayerName(existing.teamLabel);
    if (!nextName || !existingName || nextName !== existingName) continue;
    if (nextTeam === existingTeam || nextTeam === nextName || existingTeam === existingName) {
      return id;
    }
  }
  return null;
}

function normalizePlayerName(value: string): string {
  return value.trim().toLocaleLowerCase('ru-RU');
}

function buildPlayerStat(input: {
  id: string;
  name: string;
  teamId: string;
  score: number | null;
  life: number | null;
  shield: number | null;
  alive: boolean;
  place: number | null;
}): MatchPlayerStat {
  const name = input.name || compactTeamLabel(input.teamId);
  const teamLabel = compactTeamLabel(input.teamId);
  const isSelf = input.teamId === run.value?.team_id || input.id === run.value?.team_id;
  const detailLabel = isSelf
    ? 'ваш бот'
    : normalizePlayerName(name) === normalizePlayerName(teamLabel)
      ? ''
      : teamLabel;

  return {
    id: input.id,
    name,
    teamId: input.teamId,
    teamLabel,
    detailLabel,
    place: input.place,
    placeLabel: input.place === null ? '•' : String(input.place),
    score: input.score,
    scoreLabel: input.score === null ? '—' : Math.round(input.score).toLocaleString('ru-RU'),
    life: input.life,
    shield: input.shield,
    lifePercent: percentFromValue(input.life, 50),
    shieldPercent: percentFromValue(input.shield, 25),
    alive: input.alive,
    isSelf,
  };
}

function summaryPlaceFor(teamId: string): number | null {
  const placements = isRecord(replay.value?.summary?.placements)
    ? replay.value.summary.placements
    : isRecord(run.value?.result_payload?.placements)
      ? run.value.result_payload.placements
      : {};
  return numericOrNull(placements[teamId]);
}

function numericOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function booleanOrDefault(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function percentFromValue(value: number | null, max: number): number {
  if (value === null) return 0;
  return Math.max(0, Math.min(100, (value / max) * 100));
}

function compactTeamLabel(teamId: string): string {
  if (!teamId) return 'игрок';
  const participantName = participantNamesByTeam.value[teamId];
  if (participantName) return participantName;
  if (teamId.startsWith('builtin-')) return teamId.replace('builtin-', '');
  if (teamId === run.value?.team_id) return 'ваш бот';
  if (teamId.startsWith('team_')) return `team ${teamId.slice(-4)}`;
  return teamId;
}

function playerDisplayName(teamId: string, fallback: string): string {
  const participantName = participantNamesByTeam.value[teamId];
  if (participantName) return participantName;
  return fallback || compactTeamLabel(teamId);
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
  const role = typeof roleRaw === 'string' || typeof roleRaw === 'number'
    ? playerDisplayName(String(raw.team_id ?? roleRaw), String(roleRaw))
    : '';
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

function createMoveLogItem(raw: Record<string, unknown>, index: number): MoveLogItem | null {
  const type = typeof raw.type === 'string' ? raw.type : '';
  if (isConsoleEventType(type) || 'stdout' in raw) {
    return null;
  }

  const actionRaw = raw.action ?? raw.choice ?? raw.decision ?? raw.move ?? raw.command ?? raw.value;
  const hasAction = actionRaw !== undefined && actionRaw !== null && actionRaw !== '';
  const hasCoordinates = raw.x !== undefined || raw.y !== undefined || raw.row !== undefined || raw.col !== undefined;
  if (!type && !hasAction && !hasCoordinates) {
    return null;
  }

  const tick = normalizeTick(raw.tick ?? raw.turn ?? raw.step ?? raw.frame, index);
  const actorRaw = raw.role ?? raw.slot ?? raw.slot_key ?? raw.team_id ?? raw.bot ?? raw.player ?? raw.agent;
  const actor = typeof actorRaw === 'string' || typeof actorRaw === 'number'
    ? playerDisplayName(String(raw.team_id ?? actorRaw), String(actorRaw))
    : '';
  const action = hasAction ? formatMoveValue(actionRaw) : formatEventType(type || 'move');
  const detail = formatMoveDetail(raw, hasAction);
  const tone = eventTone(type);
  return {
    id: `move-${index}-${tick}`,
    tick,
    actor,
    action,
    detail,
    tone,
  };
}

function isConsoleEventType(type: string): boolean {
  return ['bot_print', 'print', 'stdout', 'bot_stdout', 'console'].includes(type);
}

function eventTone(type: string): MoveLogItem['tone'] {
  if (type.includes('error') || type.includes('invalid') || type.includes('blocked') || type.includes('failed')) {
    return 'error';
  }
  if (type === 'move' || type.includes('move') || type.includes('choice') || type.includes('decision')) {
    return 'move';
  }
  return 'event';
}

function formatEventType(type: string): string {
  const labels: Record<string, string> = {
    move: 'ход',
    action: 'действие',
    choice: 'выбор',
    decision: 'решение',
    invalid_action: 'недопустимый ход',
    invalid_move: 'недопустимый ход',
    blocked_move: 'ход заблокирован',
    blocked_step: 'ход заблокирован',
    pickup: 'подбор',
    delivered: 'доставка',
    delivery: 'доставка',
    score: 'очки',
    winner: 'победа',
    timeout: 'таймаут',
    runtime_error: 'ошибка выполнения',
    compile_error: 'ошибка кода',
  };
  return labels[type] ?? type.replace(/_/g, ' ');
}

function formatMoveDetail(raw: Record<string, unknown>, actionAlreadyShown: boolean): string {
  const parts: string[] = [];
  const type = typeof raw.type === 'string' ? raw.type : '';
  if (actionAlreadyShown && type) {
    parts.push(formatEventType(type));
  }
  const coordinates = formatCoordinates(raw);
  if (coordinates) {
    parts.push(coordinates);
  }
  appendDetailPart(parts, 'цель', raw.target);
  appendDetailPart(parts, 'от', raw.from);
  appendDetailPart(parts, 'к', raw.to);
  appendDetailPart(parts, 'линия', raw.lane);
  appendDetailPart(parts, 'счет', raw.score);
  const message = raw.message ?? raw.reason ?? raw.error;
  if (typeof message === 'string' && message.trim()) {
    parts.push(message.trim());
  }
  return parts.join(' · ');
}

function formatCoordinates(raw: Record<string, unknown>): string {
  const x = raw.x ?? raw.col;
  const y = raw.y ?? raw.row;
  if (x === undefined && y === undefined) {
    return '';
  }
  return `(${formatMoveValue(x)}, ${formatMoveValue(y)})`;
}

function appendDetailPart(parts: string[], label: string, value: unknown): void {
  if (value === undefined || value === null || value === '') return;
  parts.push(`${label}: ${formatMoveValue(value)}`);
}

function formatMoveValue(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatMoveValue(item)).join(', ');
  }
  if (value === undefined || value === null) {
    return '';
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
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
  emitEmbeddedFrame({
    tick: rendererTick.value,
    phase: rendererPhase,
    frame: rendererFrame,
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

function emitEmbeddedFrame(payload: { tick: number; phase: string; frame: unknown }): void {
  if (!isEmbedded.value || !run.value) return;
  const players = embeddedPlayerStatsForFrame(payload.frame);
  const message = sanitizeForPostMessage({
    type: 'agp.watch.frame',
    payload: {
      runId: run.value.run_id,
      status: run.value.status,
      tick: payload.tick,
      phase: payload.phase,
      frame: payload.frame,
      replayFrameIndex: replayFrameIndex.value,
      replayFrameCount: replayFrames.value.length,
      participants: watchContext.value?.participants ?? [],
      players: players.map((player) => ({
        id: player.id,
        name: player.name,
        team_id: player.teamId,
        score: player.score,
        score_label: player.scoreLabel,
        life_percent: player.lifePercent,
        shield_percent: player.shieldPercent,
        alive: player.alive,
        is_self: player.isSelf,
        detail_label: player.detailLabel,
      })),
    },
  });
  window.parent.postMessage(message, window.location.origin);
}

function embeddedPlayerStatsForFrame(frame: unknown): MatchPlayerStat[] {
  const players = new Map<string, MatchPlayerStat>();
  collectFramePlayers(players, frame);
  if (players.size === 0 && !firstReplayLockActive.value) {
    collectSummaryPlayers(players);
  }
  return [...players.values()].sort((left, right) => {
    const rightScore = right.score ?? Number.NEGATIVE_INFINITY;
    const leftScore = left.score ?? Number.NEGATIVE_INFINITY;
    if (rightScore !== leftScore) return rightScore - leftScore;
    return left.name.localeCompare(right.name, 'ru');
  });
}

function replaySpeedFromQuery(): number {
  const raw = route.query.speed_ms;
  const value = typeof raw === 'string' ? Number(raw) : NaN;
  if (!Number.isFinite(value)) return 1000;
  return Math.max(150, Math.min(3000, value));
}

function replayFrameMsFromQuery(): number {
  const raw = route.query.sync_frame_ms;
  const value = typeof raw === 'string' ? Number(raw) : NaN;
  if (!Number.isFinite(value)) return replaySpeedMs.value;
  return Math.max(150, Math.min(3000, value));
}

function replayFrameIndexFromQuery(): number | null {
  const raw = route.query.sync_frame_index;
  const value = typeof raw === 'string' ? Number(raw) : NaN;
  if (!Number.isInteger(value)) return null;
  return Math.max(0, value);
}

function applyReplaySyncFromQuery(): boolean {
  const raw = route.query.sync_started_at;
  if (replayFrames.value.length === 0) return false;
  let frameIndex: number | null = null;
  if (typeof raw === 'string' && raw) {
    const startedAtMs = Date.parse(raw);
    if (Number.isFinite(startedAtMs)) {
      const elapsedMs = Math.max(0, Date.now() - startedAtMs);
      frameIndex = Math.floor(elapsedMs / replayFrameMsFromQuery());
    }
  }
  frameIndex ??= replayFrameIndexFromQuery();
  if (frameIndex === null) return false;
  replayFrameIndex.value = Math.min(replayFrames.value.length - 1, Math.max(0, frameIndex));
  return true;
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
  if (replayFrameIndex.value >= replayFrames.value.length - 1) {
    replayFrameIndex.value = 0;
  }
  replayIsPlaying.value = true;
  replayPlaybackHandle = setInterval(() => {
    if (replayFrameIndex.value >= replayFrames.value.length - 1) {
      stopReplayPlayback();
      return;
    }
    if (firstReplayLockActive.value && replayFrameIndex.value >= firstReplayAllowedFrameIndex.value) {
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
  if (firstReplayLockActive.value) return;
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
  if (firstReplayLockActive.value) {
    replayFrameIndex.value = Math.min(replayFrameIndex.value, firstReplayAllowedFrameIndex.value);
  }
}

function syncFirstReplayFrame(): void {
  nowMs.value = Date.now();
  if (!firstReplayLockActive.value) return;
  replayFrameIndex.value = firstReplayAllowedFrameIndex.value;
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
    appendRendererLog('info', version ? `визуализация готова v${version}` : 'визуализация готова');
    sendRendererInit();
    sendRendererStateAndResult();
    return;
  }
  if (type === 'agp.renderer.error') {
    const message =
      (data as { payload?: { message?: string } }).payload?.message ??
      'визуализация сообщила об ошибке';
    appendRendererLog('error', String(message));
    return;
  }
  if (type === 'agp.renderer.event') {
    const eventName = (data as { payload?: { name?: string } }).payload?.name ?? 'событие';
    appendRendererLog('info', `событие визуализации: ${String(eventName)}`);
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
      const synced = applyReplaySyncFromQuery();
      if (!synced) replayFrameIndex.value = 0;
      syncFirstReplayFrame();
      sendRendererStateAndResult();
      if (shouldAutoplayReplay.value && replayFrames.value.length > 1 && replayFrameIndex.value < replayFrames.value.length - 1) {
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
    errorMessage.value = 'Не найден запуск для просмотра';
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
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить запуск';
  } finally {
    isLoading.value = false;
  }
}

function startRunLiveUpdates(runId: string): void {
  stopRunLiveUpdates();
  if (typeof EventSource === 'undefined') {
    appendRendererLog('warn', 'Поток обновлений недоступен, включен периодический опрос');
    startRunPolling(runId);
    return;
  }

  const source = new EventSource(
    `/api/v1/runs/${encodeURIComponent(runId)}/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`,
  );
  runEventSource = source;
  liveMode.value = 'sse';
  appendRendererLog('info', 'Поток обновлений подключен');

  const applyRunUpdate = (candidate: RunDto | null): void => {
    if (!candidate) {
      appendRendererLog('warn', 'Некорректное сообщение запуска из потока');
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
      appendRendererLog('warn', 'Некорректное сообщение обновления из потока');
    }
  });

  source.addEventListener('run', (event: MessageEvent) => {
    try {
      applyRunUpdate(JSON.parse(event.data) as RunDto);
    } catch {
      appendRendererLog('warn', 'Некорректное старое сообщение запуска из потока');
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
    appendRendererLog('warn', 'Поток обновлений отключился, включен периодический опрос');
    stopRunLiveUpdates();
    startRunPolling(runId);
  };
}

function startRunPolling(runId: string): void {
  liveMode.value = 'polling';
  stopRunPolling();
  const token = ++runPollingToken;
  const poll = async (): Promise<void> => {
    if (token !== runPollingToken) return;
    if (isPollingRun) {
      pendingRunPoll = true;
      return;
    }
    isPollingRun = true;
    try {
      do {
        pendingRunPoll = false;
        const nextRun = await getRun(runId);
        if (token !== runPollingToken) return;
        if (nextRun.run_id !== runId) return;
        run.value = nextRun;
        sendRendererStateAndResult();
      } while (pendingRunPoll);
      if (token !== runPollingToken) return;
      if (run.value && isTerminalStatus(run.value.status)) {
        stopRunPolling();
        await ensureReplayLoaded(runId);
      }
    } catch {
      // keep the latest known state and continue polling
    } finally {
      isPollingRun = false;
    }
  };
  void poll();
  runPollingHandle = setInterval(() => {
    void poll();
  }, 1200);
}

function stopRunPolling(): void {
  runPollingToken += 1;
  pendingRunPoll = false;
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
  syncFirstReplayFrame();
  if (replayFrames.value.length <= 1) {
    stopReplayPlayback();
  }
});

watch(replayFrameIndex, () => {
  clampReplayFrameIndex();
  sendRendererStateAndResult();
});

watch(firstReplayAllowedFrameIndex, () => {
  syncFirstReplayFrame();
});

watch(replaySpeedMs, () => {
  if (replayIsPlaying.value) {
    startReplayPlayback();
  }
});

onMounted(async () => {
  window.addEventListener('message', onRendererMessage);
  replayClockHandle = setInterval(syncFirstReplayFrame, 500);
  await bootstrapPage();
});

onUnmounted(() => {
  window.removeEventListener('message', onRendererMessage);
  if (replayClockHandle) clearInterval(replayClockHandle);
  stopReplayPlayback();
  stopRunLiveUpdates();
});
</script>

<style scoped>
.agp-watch-columns {
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 23rem);
  gap: 0;
}

.agp-watch-page--embedded {
  height: 100dvh;
  background: #020617;
}

.agp-watch-page {
  min-height: 100dvh;
  background-color: #050b1a;
  background-image:
    url("data:image/svg+xml,%3Csvg width='180' height='180' viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.16' stroke-width='2'%3E%3Cpath d='M20 20h34v34H20zM126 20h34v34h-34zM20 126h34v34H20zM126 126h34v34h-34z'/%3E%3Cpath d='M72 90h36M90 72v36M0 90h28M152 90h28M90 0v28M90 152v28'/%3E%3C/g%3E%3C/svg%3E"),
    radial-gradient(circle at 12% 10%, rgba(45, 212, 191, 0.22), transparent 26rem),
    radial-gradient(circle at 84% 22%, rgba(251, 191, 36, 0.14), transparent 22rem),
    linear-gradient(135deg, #050b1a 0%, #071528 52%, #030712 100%);
  background-size: 180px 180px, auto, auto, auto;
  color: #dbeafe;
}

.agp-watch-page .agp-task-header {
  background:
    linear-gradient(90deg, rgba(7, 16, 31, 0.98), rgba(8, 26, 48, 0.96)),
    url("data:image/svg+xml,%3Csvg width='128' height='64' viewBox='0 0 128 64' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.14'%3E%3Cpath d='M0 32h128M32 0v64M96 0v64M48 16h32v32H48z'/%3E%3C/g%3E%3C/svg%3E");
}

.agp-watch-page--embedded .agp-watch-columns {
  height: 100dvh;
  grid-template-columns: 1fr;
}

.agp-watch-page--embedded .agp-viewer-card {
  border: 0;
  border-radius: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 0;
  padding: 0 !important;
  background: #020617;
  box-shadow: none;
}

.agp-watch-page--embedded .agp-viewer-card .agp-viewer-frame {
  height: auto !important;
  min-height: 0;
}

.agp-watch-page .agp-viewer-card .agp-viewer-frame {
  height: calc(100dvh - 7.15rem);
  min-height: 30rem;
}

.agp-watch-page .agp-viewer-card {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(34, 211, 238, 0.24);
  border-radius: 0;
  background: #020617;
  box-shadow: inset 0 0 0 1px rgba(125, 211, 252, 0.08), 0 0 42px rgba(34, 211, 238, 0.08);
  padding: 0 !important;
}

.agp-watch-page .agp-viewer-card::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  border: 1px solid rgba(34, 211, 238, 0.26);
  pointer-events: none;
}

.agp-watch-page .agp-viewer-card::after {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  z-index: 1;
  height: 0.22rem;
  background: linear-gradient(90deg, #22d3ee, #facc15, #14b8a6, #2563eb);
  opacity: 0.74;
  pointer-events: none;
}

.agp-watch-renderer-state {
  left: auto;
  right: 0.75rem;
  max-width: min(26rem, calc(100% - 1.5rem));
}

.agp-watch-winner-banner,
.agp-watch-replay-lock {
  position: absolute;
  z-index: 5;
  left: 50%;
  bottom: 1rem;
  width: min(34rem, calc(100% - 2rem));
  transform: translateX(-50%);
  border: 1px solid rgba(250, 204, 21, 0.36);
  border-radius: 0.75rem;
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(8, 47, 73, 0.9)),
    rgba(15, 23, 42, 0.94);
  color: #f8fafc;
  padding: 0.8rem 1rem;
  text-align: center;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(10px);
}

.agp-watch-winner-banner span,
.agp-watch-replay-lock span {
  display: block;
  color: #a7f3d0;
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
}

.agp-watch-winner-banner strong,
.agp-watch-replay-lock strong {
  display: block;
  color: #fef3c7;
  font-size: clamp(1.3rem, 2vw, 2rem);
  line-height: 1.1;
}

.agp-watch-replay-lock {
  border-color: rgba(34, 211, 238, 0.34);
}

.agp-watch-replay-lock strong {
  color: #dff8ff;
}

.agp-watch-side-card {
  position: sticky;
  top: 0;
  align-self: stretch;
  overflow: hidden;
  border-width: 0 0 0 1px;
  border-color: rgba(34, 211, 238, 0.24);
  border-radius: 0;
  background:
    radial-gradient(circle at 12% 4%, rgba(34, 211, 238, 0.16), transparent 11rem),
    radial-gradient(circle at 92% 18%, rgba(250, 204, 21, 0.1), transparent 10rem),
    linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.98)),
    url("data:image/svg+xml,%3Csvg width='96' height='96' viewBox='0 0 96 96' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23facc15' stroke-opacity='.10'%3E%3Cpath d='M12 48h72M48 12v72M24 24l48 48M72 24 24 72'/%3E%3C/g%3E%3C/svg%3E");
  color: #dbeafe;
  max-height: calc(100dvh - 3.4rem);
  overflow-y: auto;
  box-shadow: none;
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

.agp-watch-side-winner,
.agp-watch-side-lock {
  border: 1px solid rgba(250, 204, 21, 0.28);
  border-radius: 0.75rem;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.16), rgba(250, 204, 21, 0.08));
  margin: 0.75rem 0;
  padding: 0.75rem;
}

.agp-watch-side-winner span {
  display: block;
  color: #99f6e4;
  font-size: 0.72rem;
  font-weight: 850;
  text-transform: uppercase;
}

.agp-watch-side-winner strong {
  display: block;
  color: #fef3c7;
  font-size: 1.25rem;
}

.agp-watch-side-lock {
  border-color: rgba(34, 211, 238, 0.24);
  color: #c6d7ea;
  font-size: 0.86rem;
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

.agp-match-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.agp-match-panel-head h2::before {
  content: '';
  display: inline-block;
  width: 0.58rem;
  height: 0.58rem;
  margin-right: 0.45rem;
  border-radius: 999px;
  background: linear-gradient(135deg, #22d3ee, #facc15);
  box-shadow: 0 0 16px rgba(34, 211, 238, 0.55);
  vertical-align: 0.05rem;
}

.agp-match-panel-head span {
  color: #8ea7c1;
  font-size: 0.78rem;
}

.agp-run-pill {
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 999px;
  padding: 0.25rem 0.55rem;
  color: #dbeafe;
  font-size: 0.76rem;
  font-weight: 850;
  white-space: nowrap;
}

.agp-run-pill--active {
  border-color: rgba(251, 191, 36, 0.4);
  background: rgba(251, 191, 36, 0.16);
  color: #fde68a;
}

.agp-run-pill--success {
  border-color: rgba(45, 212, 191, 0.36);
  background: rgba(20, 184, 166, 0.16);
  color: #99f6e4;
}

.agp-run-pill--danger {
  border-color: rgba(248, 113, 113, 0.45);
  background: rgba(127, 29, 29, 0.22);
  color: #fecaca;
}

.agp-match-scoreboard {
  display: grid;
  gap: 0.45rem;
}

.agp-match-player {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) minmax(3.25rem, auto);
  gap: 0.6rem;
  align-items: center;
  border: 1px solid rgba(34, 211, 238, 0.18);
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(34, 211, 238, 0.08), transparent 42%),
    rgba(15, 23, 42, 0.68);
  padding: 0.6rem 0.55rem 0.6rem 0.7rem;
}

.agp-match-player::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 0.2rem;
  background: linear-gradient(180deg, #22d3ee, #facc15);
  opacity: 0.72;
}

.agp-match-player--self {
  border-color: rgba(45, 212, 191, 0.5);
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.26), rgba(15, 23, 42, 0.68));
}

.agp-match-player--out {
  opacity: 0.62;
}

.agp-match-player-rank {
  width: 1.85rem;
  height: 1.85rem;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background:
    radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.24), transparent 38%),
    rgba(34, 211, 238, 0.16);
  color: #a5f3fc;
  font-weight: 900;
  box-shadow: 0 0 18px rgba(34, 211, 238, 0.16);
}

.agp-match-player-main,
.agp-match-player-score {
  display: grid;
  gap: 0.1rem;
  min-width: 0;
}

.agp-match-player-main strong {
  overflow: hidden;
  color: #f8fbff;
  font-size: 0.95rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agp-match-player-main span,
.agp-match-player-score span {
  color: #8ea7c1;
  font-size: 0.74rem;
}

.agp-match-player-score {
  justify-items: end;
  text-align: right;
}

.agp-match-player-score strong {
  min-width: 2.8rem;
  border: 1px solid rgba(125, 211, 252, 0.22);
  border-radius: 999px;
  background:
    linear-gradient(135deg, rgba(34, 211, 238, 0.16), rgba(250, 204, 21, 0.1));
  padding: 0.16rem 0.5rem;
  color: #fefce8;
  font-size: 0.95rem;
  text-align: center;
}

.agp-match-bars {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem;
  margin-top: 0.15rem;
}

.agp-match-bars span {
  height: 0.3rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
}

.agp-match-bars i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.agp-match-bars span:first-child i {
  background: linear-gradient(90deg, #fb7185, #facc15);
}

.agp-match-bars span:last-child i {
  background: linear-gradient(90deg, #38bdf8, #22d3ee);
}

.agp-match-mini-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
  margin-top: 0.75rem;
}

.agp-match-mini-stats div,
.agp-match-empty {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(34, 211, 238, 0.08), rgba(250, 204, 21, 0.04)),
    rgba(15, 23, 42, 0.62);
  padding: 0.55rem;
}

.agp-match-mini-stats span {
  display: block;
  color: #8ea7c1;
  font-size: 0.72rem;
}

.agp-match-empty {
  color: #8ea7c1;
  font-size: 0.86rem;
}

.agp-tech-details {
  border-top: 1px solid rgba(148, 163, 184, 0.18);
  padding-top: 0.65rem;
}

.agp-replay-foot {
  margin-top: 0.75rem;
}

.agp-watch-stat strong {
  font-size: 0.95rem;
}

.agp-watch-replay-summary {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 0.45rem;
  background: rgba(15, 23, 42, 0.72);
  padding: 0.55rem 0.65rem;
}

.agp-watch-move-log {
  display: grid;
  gap: 0.45rem;
  max-height: 20rem;
  overflow: auto;
  padding-right: 0.2rem;
}

.agp-watch-move-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.1rem 0.55rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.45rem;
  background: rgba(15, 23, 42, 0.72);
  padding: 0.5rem 0.6rem;
}

.agp-watch-move-row > .mono {
  color: #8ea7c1;
}

.agp-watch-move-row strong,
.agp-watch-move-row > .text-muted {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agp-watch-move-action {
  grid-column: 2;
  color: #e5f3ff;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.agp-watch-move-row small {
  grid-column: 2;
  color: #8ea7c1;
  overflow-wrap: anywhere;
}

.agp-watch-move-row--move {
  border-color: rgba(45, 212, 191, 0.28);
}

.agp-watch-move-row--event {
  border-color: rgba(125, 211, 252, 0.24);
}

.agp-watch-move-row--error {
  border-color: rgba(248, 113, 113, 0.38);
  background: rgba(127, 29, 29, 0.18);
}

.agp-bot-console {
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 8px;
  background:
    url("data:image/svg+xml,%3Csvg width='32' height='32' viewBox='0 0 32 32' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.05'%3E%3Cpath d='M0 16h32M16 0v32'/%3E%3C/g%3E%3C/svg%3E"),
    #050812;
  color: #d1d5db;
}

.agp-bot-console-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.96), rgba(12, 74, 110, 0.45));
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
    height: 24rem;
    min-height: 24rem;
  }

  .agp-bot-console-line {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .agp-bot-console-role {
    display: none;
  }
}

@media (max-width: 720px) {
  .agp-watch-page .agp-task-header {
    padding: 0.45rem;
    gap: 0.35rem;
  }

  .agp-watch-page .agp-task-header-main {
    min-height: 2.2rem;
  }

  .agp-watch-page .agp-task-header-player {
    display: grid;
    grid-template-columns: auto auto auto minmax(4.5rem, 1fr) auto;
    align-items: center;
    width: 100%;
    gap: 0.35rem;
  }

  .agp-watch-page .agp-task-header-player .agp-player-frame-label {
    min-width: 0;
    overflow: hidden;
    color: #c7d2fe !important;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .agp-watch-page .agp-task-header-player .agp-speed-control {
    grid-column: 5;
    grid-row: 1;
    width: auto !important;
    min-width: 0 !important;
    margin: 0 !important;
    justify-content: flex-end !important;
  }

  .agp-watch-page .agp-task-header-player .agp-speed-label {
    display: none;
  }

  .agp-watch-page .agp-task-header-player .agp-speed-select {
    width: 6rem;
    min-height: 2.2rem;
  }

  .agp-watch-page .agp-task-header-player .agp-player-range {
    grid-column: 1 / -1;
    grid-row: 2;
    order: initial;
    width: 100%;
    min-width: 0 !important;
  }

  .agp-watch-page .agp-task-header-actions {
    justify-content: space-between;
  }

  .agp-watch-side-card {
    max-height: none;
    border-width: 1px 0 0;
  }

  .agp-match-mini-stats {
    grid-template-columns: 1fr;
  }
}
</style>
