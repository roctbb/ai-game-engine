<template>
  <section class="arena-match-review" :class="{ 'arena-match-review--embedded': isEmbedded, 'arena-match-review--source': sourceOpen, 'arena-match-review--fullscreen': fieldFullscreen }">
    <header v-if="!isEmbedded" class="arena-match-bar">
      <RouterLink :to="backTarget" class="agp-back-link" :aria-label="backLabel"><AppIcon name="back" /></RouterLink>
      <h1 :title="watchContext?.game_title">{{ watchContext?.game_title || 'Разбор запуска' }}</h1>
      <time v-if="run">{{ formatTime(run.created_at) }}</time>
      <button class="btn btn-outline-secondary arena-match-mobile-players" @click="statsOpen = true">Игроки</button>
      <button v-if="sourceParticipants.length" class="btn btn-outline-secondary" :aria-pressed="sourceOpen" @click="toggleSource">{{ sourceOpen ? 'Скрыть код' : 'Код' }}</button>
      <ActionMenu v-if="canSeeTechnicalDetails" label="Действия с визуализацией" :items="[{ id: 'restart', label: 'Перезапустить визуализацию', disabled: !canRestartRenderer }]" @select="restartRenderer" />
    </header>
    <LoadingSkeleton v-if="isLoading" :count="isEmbedded ? 1 : 2" layout="workspace" :style="{ '--agp-skeleton-workspace-columns': isEmbedded ? 'minmax(0, 1fr)' : 'minmax(0, 1fr) minmax(18rem, 20rem)' }" label="Загрузка матча…" />
    <article v-else-if="errorMessage" class="agp-card p-4 text-danger" role="alert">{{ errorMessage }}</article>
    <div v-else-if="watchContext && run" class="arena-match-columns">
      <article v-if="sourceOpen && !isEmbedded" class="agp-card arena-match-source">
        <header class="arena-match-pane-head arena-match-source-head">
          <select v-if="sourceParticipants.length > 1" :value="sourceRunId" class="form-select form-select-sm" aria-label="Код участника" @change="loadSource(($event.target as HTMLSelectElement).value)"><option v-for="p in sourceParticipants" :key="p.run_id" :value="p.run_id">{{ p.display_name }}</option></select>
          <strong v-else>{{ sourceParticipants[0]?.display_name }}</strong>
          <span class="arena-match-code-time">Код {{ formatTime(sourceCapturedAt) }} · только чтение</span>
        </header>
        <div v-if="Object.keys(sourceCodes).length > 1" class="arena-match-files"><label for="review-source-slot">Файл</label><select id="review-source-slot" v-model="sourceSlot" class="form-select form-select-sm"><option v-for="slot in Object.keys(sourceCodes)" :key="slot">{{ slot }}</option></select></div>
        <p v-if="sourceError" role="alert" class="text-danger p-3">{{ sourceError }}</p>
        <CodeEditor v-else :model-value="sourceCodes[sourceSlot] || ''" readonly :focus-line="sourceLine" :error-line="sourceRunId === errorSourceRunId ? currentBotError?.line : undefined" />
        <footer v-if="sourceParticipants.find(p => p.run_id === sourceRunId)?.captain_user_id === sessionStore.nickname" class="arena-match-source-foot"><RouterLink class="btn btn-primary" :to="{ name: 'player-code', params: { teamId: sourceParticipants.find(p => p.run_id === sourceRunId)?.team_id }, query: { from_run: sourceRunId, slot: sourceSlot, back: route.fullPath } }">Взять код в работу</RouterLink></footer>
      </article>
      <article class="agp-card arena-match-field">
        <header v-if="!isEmbedded" class="arena-match-pane-head">
          <strong :class="{ 'text-danger': runStatusTone === 'danger' }">{{ showWinnerBanner ? finalOutcomeLabel : runStatusLabel }}</strong>
          <button class="agp-panel-toggle" @click="fieldFullscreen = !fieldFullscreen">{{ fieldFullscreen ? 'Вернуть панели' : 'На весь экран' }}</button>
        </header>
        <div v-if="currentBotError && !firstShowWaiting" class="arena-match-code-error" role="alert">
          <strong>Ошибка кода · ход пропущен</strong>
          <span>{{ currentBotError.detail }}</span>
          <button v-if="!isEmbedded && sourceParticipants.length" class="btn btn-sm btn-outline-danger" @click="openRunLine({ line: currentBotError.line ?? 1, role: currentBotError.role })">К строке {{ currentBotError.line ?? 1 }}</button>
        </div>
        <div class="arena-match-view">
          <div v-if="(!rendererReady && safeRendererUrl) || firstShowWaiting || (isReplayLoading && !replayFrames.length)" class="arena-match-loading"><SnakeLoader :label="firstShowWaiting ? 'Подготовка матча' : isReplayLoading ? 'Загрузка матча' : 'Загрузка визуализации'" /></div>
          <div v-if="firstReplayLockActive && !firstShowWaiting && isEmbedded" class="arena-match-lock">Первый показ</div>
          <iframe v-if="safeRendererUrl" ref="rendererFrameRef" :key="rendererKey" :src="safeRendererUrl" title="Визуализация игры" sandbox="allow-scripts" @load="onRendererLoad"></iframe>
          <p v-else class="text-muted m-3">Для этой игры визуализация не настроена.</p>
        </div>
        <ReplayControls v-if="!isEmbedded" v-model:frame-index="replayFrameIndex" v-model:delay="replaySpeedMs" class="arena-match-playback" :frame-count="replayFrames.length" :playing="replayIsPlaying" :can-play="canPlayReplay" :can-step-backward="canStepBackward" :can-step-forward="canStepForward" :seek-disabled="firstReplayLockActive" :live="firstReplayLockActive" :live-label="firstShowWaiting ? 'Подготовка' : 'Первый показ'" :markers="watchMoments" @toggle="toggleReplayPlay" @step="stepReplay" />
        <p v-if="replayError && !isEmbedded" class="text-danger small m-2" role="alert">{{ replayError }}</p>
        <details v-if="!isEmbedded && replayFrames.length" class="arena-match-insights"><summary>Разбор хода</summary><ReplayInsights @pause="stopReplayPlayback()" :frames="replay?.frames ?? []" :events="replay?.events ?? []" :frame-index="replayFrameIndex" :locked="firstReplayLockActive" :actor-names="eventActorNames" @seek="seekMoment" @line="openRunLine" /></details>
        <BotConsole v-if="showBotConsole" initially-collapsed label="Консоль и события">
          <div v-if="!currentConsoleLines.length" class="agp-bot-console-empty">Вывод отсутствует</div>
          <div v-for="line in currentConsoleLines" :key="line.id" class="agp-bot-console-line"><span v-if="line.role" class="agp-bot-console-role">{{ line.role }}</span><span class="mono agp-bot-console-message">{{ line.message }}</span></div>
        </BotConsole>
      </article>
      <aside v-if="!isEmbedded && !sourceOpen" class="agp-card arena-match-standings">
        <h2>{{ showWinnerBanner ? 'Результаты' : 'Участники' }} · {{ matchPlayerStats.length }}</h2>
        <LiveMatchScoreboard :players="reviewPlayers" />
        <details v-if="canSeeTechnicalDetails" class="arena-match-technical"><summary>Технические детали</summary><dl><dt>Визуализация</dt><dd>{{ rendererStatusLabel }}</dd><dt>Тип</dt><dd>{{ runKindLabel }}</dd><dt>Обновления</dt><dd>{{ liveMode }}</dd></dl><RunReasonBadge v-if="run.error_message" :reason="run.error_message" :show-raw="false" /></details>
      </aside>
    </div>
    <Teleport to="body"><div v-if="statsOpen" class="arena-modal-backdrop" @click.self="statsOpen = false"><section class="agp-card arena-match-dialog" role="dialog" aria-modal="true" aria-label="Участники матча" v-dialog-focus="() => statsOpen = false"><header><h2>Участники матча</h2><button class="btn btn-outline-secondary" aria-label="Закрыть участников" @click="statsOpen = false"><AppIcon name="close" /></button></header><LiveMatchScoreboard :players="reviewPlayers" /></section></div></Teleport>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import CodeEditor from '../components/CodeEditor.vue';
import ActionMenu from '../components/ActionMenu.vue';
import LiveMatchScoreboard from '../components/LiveMatchScoreboard.vue';
import { replayParticipant } from '../lib/replayParticipant';
import { firstShowPosition, sampleFirstShow, type FirstShowSample } from '../lib/firstShowClock';
import { formatTime } from '../lib/attemptPresentation';
import AppIcon from '../components/AppIcon.vue';
import BotConsole from '../components/BotConsole.vue';
import ReplayControls from '../components/ReplayControls.vue';
import ReplayInsights from '../components/ReplayInsights.vue';
import { replayMoments } from '../lib/replayInsights';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import SnakeLoader from '../components/SnakeLoader.vue';
import { createReplayClock, loadReplayDelay, saveReplayDelay } from '../lib/replayPlayback';
import { isShortcutInput } from '../lib/keyboard';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import RunReasonBadge from '../components/RunReasonBadge.vue';
import {
  getRun,
  getRunCode,
  getRunReplay,
  getRunWatchContext,
  type ReplayDto,
  type RunDto,
  type RunWatchContextDto,
  type StreamEnvelopeDto,
} from '../lib/api';
import { sanitizeForPostMessage } from '../lib/postMessage';
import { createResilientSSE } from '../lib/resilientSSE';
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
const router = useRouter();
const watchMoments = computed(() => replayMoments((replay.value?.events ?? []).filter(e => !firstReplayLockActive.value || Number(e.tick ?? 0) <= replayFrameTick.value), replay.value?.frames ?? []).filter(moment => !firstReplayLockActive.value || moment.frame <= replayFrameIndex.value));
const currentBotError = computed(() => watchMoments.value.filter(moment => moment.label === 'Ошибка Python' && moment.tick <= replayFrameTick.value).slice(-1)[0] ?? null);
const errorSourceRunId = computed(() => {
  const role = currentBotError.value?.role;
  return (watchContext.value?.participants.find(p => p.team_id === role)
    ?? (role === '1' ? watchContext.value?.participants[0] : role === '-1' ? watchContext.value?.participants[1] : undefined))?.run_id;
});
function seekMoment(frame: number): void {
  if (firstReplayLockActive.value) return;
  stopReplayPlayback();
  replayFrameIndex.value = Math.max(0, Math.min(frame, replayFrames.value.length - 1));
}
function openRunLine(location: { line: number; role?: string }): void {
  if (!run.value) return;
  if (run.value.run_kind === 'single_task') {
    void router.push({ name: 'task-run', params: { gameId: run.value.game_id }, query: { inspect_run: run.value.run_id, line: location.line, ...(location.role ? { role: location.role } : {}) } });
  } else if (sourceParticipants.value.length) {
    sourceLine.value = location.line;
    sourceOpen.value = true;
    const participant = watchContext.value?.participants.find(p => p.team_id === location.role)
      ?? (location.role === '1' ? watchContext.value?.participants[0] : location.role === '-1' ? watchContext.value?.participants[1] : undefined);
    const target = sourceParticipants.value.find(p => p.run_id === participant?.run_id);
    void loadSource(target?.run_id || sourceRunId.value || sourceParticipants.value[0].run_id);
  }
}
const sessionStore = useSessionStore();
const isEmbedded = computed(() => route.query.embed === '1');
const showBotConsole = computed(() => route.query.show_print !== '0' && (sessionStore.role !== 'student' || watchContext.value?.participants.some(p => p.captain_user_id === sessionStore.nickname)));
const canSeeTechnicalDetails = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');

const watchContext = ref<RunWatchContextDto | null>(null);
const run = ref<RunDto | null>(null);
const replay = ref<ReplayDto | null>(null);
const replayError = ref('');
const sourceOpen = ref(false);
const statsOpen = ref(false);
const fieldFullscreen = ref(false);
const reviewPlayers = computed(() => matchPlayerStats.value.map(player => ({
  team_id: player.id, display_name: player.name, score: player.scoreLabel, isSelf: player.isSelf,
  status: player.alive ? (isReplayAtLastFrame.value ? 'финиш' : 'в игре') : 'выбыл',
  place: player.placeLabel,
  meta: [player.life === null ? '' : 'Здоровье ' + player.life, player.shield === null ? '' : 'Щит ' + player.shield].filter(Boolean).join(' · '),
})));
const sourceCodes = ref<Record<string, string>>({});
const sourceSlot = ref('');
const sourceRunId = ref('');
const sourceCapturedAt = ref('');
const sourceLine = ref(1);
const sourceError = ref('');
const sourceParticipants = computed(() => (watchContext.value?.participants ?? []).filter(p => sessionStore.role !== 'student' || p.captain_user_id === sessionStore.nickname));
async function loadSource(runId: string): Promise<void> {
  sourceError.value = '';
  try { const snapshot = await getRunCode(runId); sourceRunId.value = runId; sourceCodes.value = snapshot.codes_by_slot; sourceSlot.value = Object.keys(snapshot.codes_by_slot)[0] || ''; sourceCapturedAt.value = snapshot.captured_at; }
  catch (e) { sourceError.value = e instanceof Error ? e.message : 'Не удалось открыть исходник'; }
}
async function toggleSource(): Promise<void> { sourceOpen.value = !sourceOpen.value; if (sourceOpen.value && !sourceRunId.value && sourceParticipants.value[0]) await loadSource(sourceParticipants.value[0].run_id); }

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
const firstShowSample = ref<FirstShowSample | null>(null);
const followingFirstShow = ref(false);
const awaitingFirstShowTurn = ref(false);
let firstShowRefreshHandle: ReturnType<typeof setTimeout> | null = null;
let refreshingFirstShow = false;
let disposed = false;
let rendererLogCounter = 0;
let runPollingHandle: ReturnType<typeof setInterval> | null = null;
let runEventSource: EventSource | null = null;
const replayPlaybackClock = createReplayClock(() => {
  if (replayFrameIndex.value >= replayFrames.value.length - 1) { stopReplayPlayback(); return; }
  if (firstReplayLockActive.value) return;
  replayFrameIndex.value += 1;
}, () => replaySpeedMs.value);
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
  if (firstShowWaiting.value) return 'Подготовка матча';
  if (firstReplayLockActive.value) return 'Первый показ';
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
  if (firstReplayLockActive.value) return 'active';
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
  if (typeof route.query.back === 'string' && /^\/(lobbies|competitions|tasks)\//.test(route.query.back)) return route.query.back;
  if (run.value?.run_kind === 'single_task') return `/tasks/${encodeURIComponent(run.value.game_id)}`;
  if (run.value?.run_kind === 'competition_match' && run.value.lobby_id) return `/competitions/${encodeURIComponent(run.value.lobby_id)}`;
  if (run.value?.lobby_id) return `/lobbies/${encodeURIComponent(run.value.lobby_id)}`;
  return '/lobbies';
});
const backLabel = computed(() => {
  if (run.value?.run_kind === 'single_task') return 'К задаче';
  if (run.value?.run_kind === 'competition_match') return 'К соревнованию';
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

const eventActorNames = computed<Record<string, string>>(() => {
  const names = { ...participantNamesByTeam.value };
  const first = replayFrames.value[0]?.frame ?? {};
  const snakes = isRecord(first.snakes) ? first.snakes : {};
  for (const [role, raw] of Object.entries(snakes)) {
    if (isRecord(raw)) names[role] = names[String(raw.team_id)] || String(raw.name || role);
  }
  const positions = isRecord(first.positions) ? first.positions : {};
  Object.keys(positions).forEach((role, index) => {
    const participant = watchContext.value?.participants[index];
    if (participant) names[role] = participant.display_name;
  });
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
  if (players.size === 0 && isReplayAtLastFrame.value) {
    collectSummaryPlayers(players);
  }
  collectContextPlayers(players);
  mergeSummaryPlacements(players);
  const sorted = [...players.values()].sort((left, right) => {
    const leftPlace = left.place ?? Number.POSITIVE_INFINITY;
    const rightPlace = right.place ?? Number.POSITIVE_INFINITY;
    if (leftPlace !== rightPlace) return leftPlace - rightPlace;
    return (right.score ?? -Infinity) - (left.score ?? -Infinity);
  });
  let place = 1;
  return sorted.map((player, index) => {
    if (index > 0 && player.score !== sorted[index - 1].score) place = index + 1;
    const rank = player.place ?? (player.score === null ? null : place);
    return { ...player, place: rank, placeLabel: rank === null ? '—' : String(rank) };
  });
});
const matchLeaderLabel = computed(() => matchPlayerStats.value[0]?.name ?? '—');
function collectContextPlayers(players: Map<string, MatchPlayerStat>): void {
  const participants = watchContext.value?.participants ?? [];
  if (!participants.length) return;
  const canonical = new Map<string, MatchPlayerStat>();
  for (const player of players.values()) {
    const participant = replayParticipant(player, participants);
    if (!participant) continue;
    const previous = canonical.get(participant.team_id);
    canonical.set(participant.team_id, buildPlayerStat({
      id: participant.team_id, teamId: participant.team_id, name: participant.display_name,
      score: player.score ?? previous?.score ?? null, life: player.life ?? previous?.life ?? null,
      shield: player.shield ?? previous?.shield ?? null, alive: player.alive, place: player.place,
    }));
  }
  players.clear();
  for (const [id, player] of canonical) players.set(id, player);
  for (const participant of participants) {
    if (players.has(participant.team_id)) continue;
    players.set(participant.team_id, buildPlayerStat({ id: participant.team_id, teamId: participant.team_id, name: participant.display_name, score: null, life: null, shield: null, alive: true, place: null }));
  }
}
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
const firstShowWaiting = computed(() => firstShowSample.value?.timeline.started_at === null || awaitingFirstShowTurn.value);
const firstReplayLockActive = computed(() => firstShowWaiting.value || followingFirstShow.value);
const canPlayReplay = computed(() => !firstReplayLockActive.value && replayFrames.value.length > 1);
const canStepBackward = computed(() => !firstReplayLockActive.value && replayFrames.value.length > 0 && replayFrameIndex.value > 0);
const canStepForward = computed(
  () => !firstReplayLockActive.value && replayFrames.value.length > 0 && replayFrameIndex.value < replayFrames.value.length - 1,
);
const shouldAutoplayReplay = computed(() => isEmbedded.value || route.query.autoplay === '1');
const isReplayAtLastFrame = computed(
  () => !firstShowWaiting.value && replayFrames.value.length > 0 && replayFrameIndex.value >= replayFrames.value.length - 1,
);
const showWinnerBanner = computed(() => replayFrames.value.length > 0 && isReplayAtLastFrame.value && !firstReplayLockActive.value);
const finalOutcomeLabel = computed(() => {
  const metrics = replay.value?.summary?.metrics ?? run.value?.result_payload?.metrics;
  if (isRecord(metrics) && metrics.draw === true) return 'Ничья';
  const explicitWinners = explicitReplayWinnerTeamIds();
  if (explicitWinners.length > 1) return 'Совместное 1-е место · ' + explicitWinners.length;
  if (explicitWinners.length === 1) return 'Победитель: ' + playerDisplayName(explicitWinners[0], compactTeamLabel(explicitWinners[0]));
  const placedWinners = matchPlayerStats.value.filter((player) => player.place === 1);
  if (placedWinners.length === 1) return 'Победитель: ' + placedWinners[0].name;
  if (placedWinners.length > 1) return 'Совместное 1-е место · ' + placedWinners.length;
  return 'Матч завершён';
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
  if (!isReplayAtLastFrame.value) return;
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
    teamId: previous.teamId || next.teamId,
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
  const isSelf = watchContext.value?.participants.some(participant => participant.captain_user_id === sessionStore.nickname && (participant.team_id === input.teamId || participant.team_id === input.id)) ?? false;
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
  if (!isReplayAtLastFrame.value) return null;
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
  if (watchContext.value?.participants.some(p => p.team_id === teamId && p.captain_user_id === sessionStore.nickname)) return 'ваш бот';
  if (teamId.startsWith('team_')) return `Игрок ${teamId.slice(-4)}`;
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
  frame.contentWindow.postMessage(sanitizeForPostMessage(message), '*');
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
  if (isTerminalStatus(run.value.status) && !activeReplayFrame && !replay.value) {
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
      motion: { duration_ms: firstReplayLockActive.value ? 180 : replayIsPlaying.value ? Math.min(180, replaySpeedMs.value / 2) : 0 },
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
    !firstReplayLockActive.value && (replay.value !== null ? isReplayAtLastFrame.value : !shouldAutoplayReplay.value);
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
      firstShowActive: firstReplayLockActive.value,
      firstShowWaiting: firstShowWaiting.value,
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
  if (players.size === 0 && isReplayAtLastFrame.value) {
    collectSummaryPlayers(players);
  }
  collectContextPlayers(players);
  mergeSummaryPlacements(players);
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
  if (!Number.isFinite(value)) return loadReplayDelay();
  return Math.max(150, Math.min(3000, value));
}

function onRendererLoad(): void {
  syncFirstReplayFrame();
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
  replayPlaybackClock.stop();
  replayIsPlaying.value = false;
}

function startReplayPlayback(): void {
  if (firstReplayLockActive.value) return;
  if (!canPlayReplay.value) {
    replayIsPlaying.value = false;
    return;
  }
  stopReplayPlayback();
  if (replayFrameIndex.value >= replayFrames.value.length - 1) {
    replayFrameIndex.value = 0;
  }
  replayIsPlaying.value = true;
  replayPlaybackClock.start();
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
}

function syncFirstReplayFrame(): void {
  if (document.hidden) return;
  const sample = firstShowSample.value;
  if (!sample) return;
  if (sample.timeline.started_at !== null && !replayFrames.value.length) return;
  const position = firstShowPosition(sample, replayFrames.value.length, performance.now());
  awaitingFirstShowTurn.value = position.waiting;
  const wasFollowing = followingFirstShow.value;
  followingFirstShow.value = position.following;
  if (position.following || wasFollowing || isEmbedded.value) {
    stopReplayPlayback();
    replayFrameIndex.value = position.frame;
  }
  if (wasFollowing !== position.following) sendRendererStateAndResult();
}

function applyWatchClock(context: RunWatchContextDto, requestedAt: number, receivedAt: number): void {
  firstShowSample.value = ['failed', 'timeout', 'canceled'].includes(context.status) ? null
    : sampleFirstShow(context.first_show, context.server_now, requestedAt, receivedAt, context.server_received_at);
  if (!firstShowSample.value) {
    followingFirstShow.value = false;
    awaitingFirstShowTurn.value = false;
  }
  syncFirstReplayFrame();
  sendRendererStateAndResult();
  scheduleFirstShowRefresh();
}

function scheduleFirstShowRefresh(): void {
  if (firstShowRefreshHandle) clearTimeout(firstShowRefreshHandle);
  firstShowRefreshHandle = null;
  if (disposed || !firstShowWaiting.value) return;
  firstShowRefreshHandle = setTimeout(() => {
    if (document.hidden) scheduleFirstShowRefresh();
    else void refreshWatchClock();
  }, 1000);
}

async function refreshWatchClock(): Promise<void> {
  if (refreshingFirstShow || disposed) return;
  refreshingFirstShow = true;
  const requestedAt = performance.now();
  try {
    const context = await getRunWatchContext(String(route.params.runId));
    if (disposed) return;
    watchContext.value = context;
    applyWatchClock(context, requestedAt, performance.now());
  } catch {
    // Keep the latest server anchor through a transient connection failure.
  } finally {
    refreshingFirstShow = false;
    scheduleFirstShowRefresh();
  }
}

function onVisibilityChange(): void {
  if (document.hidden) return;
  syncFirstReplayFrame();
  void refreshWatchClock();
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
  if (type === 'agp.renderer.shortcut' && ['Space', 'ArrowLeft', 'ArrowRight', 'Escape'].includes(data.payload?.code)) {
    handlePlaybackKeydown(new KeyboardEvent('keydown', { key: String(data.payload.key), code: data.payload.code }));
    return;
  }
  if (type === 'agp.renderer.ready') {
    syncFirstReplayFrame();
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
  const requestedAt = performance.now();
  const [contextSample, freshRun] = await Promise.all([
    getRunWatchContext(runId).then(context => ({ context, receivedAt: performance.now() })),
    getRun(runId, { compactPayload: true }),
  ]);
  if (disposed) return;
  watchContext.value = contextSample.context;
  run.value = freshRun;
  applyWatchClock(contextSample.context, requestedAt, contextSample.receivedAt);
}

async function ensureReplayLoaded(runId: string): Promise<void> {
  if (run.value?.run_id !== runId || run.value.status !== 'finished') return;
  if (replay.value?.run_id === runId || isReplayLoading.value) {
    return;
  }
  isReplayLoading.value = true;
  replayError.value = '';
  try {
    const loadedReplay = await getRunReplay(runId);
    if (disposed) return;
    replay.value = loadedReplay;
    clampReplayFrameIndex();
    if (replayFrames.value.length > 0) {
      replayFrameIndex.value = 0;
      syncFirstReplayFrame();
      sendRendererStateAndResult();
      if (!firstReplayLockActive.value && shouldAutoplayReplay.value && replayFrames.value.length > 1 && replayFrameIndex.value < replayFrames.value.length - 1) {
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

  const handleTerminal = async (statusFromEnvelope?: string): Promise<void> => {
    if (run.value && statusFromEnvelope) {
      run.value = {
        ...run.value,
        status: statusFromEnvelope as RunDto['status'],
      };
      sendRendererStateAndResult();
    }
    if (run.value) {
      await refreshWatchClock();
      await ensureReplayLoaded(run.value.run_id);
    }
    stopRunLiveUpdates();
  };

  const sse = createResilientSSE({
    url: `/api/v1/runs/${encodeURIComponent(runId)}/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`,
    onOpen(source) {
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
    },
    onFallbackToPolling() {
      if (run.value && isTerminalStatus(run.value.status)) {
        stopRunLiveUpdates();
        return;
      }
      appendRendererLog('warn', 'Поток обновлений отключился, включен периодический опрос');
      startRunPolling(runId);
    },
  });
  runEventSource = sse as unknown as EventSource;
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
        const nextRun = await getRun(runId, { compactPayload: true });
        if (token !== runPollingToken) return;
        if (nextRun.run_id !== runId) return;
        run.value = nextRun;
        sendRendererStateAndResult();
      } while (pendingRunPoll);
      if (token !== runPollingToken) return;
      if (run.value && isTerminalStatus(run.value.status)) {
        stopRunPolling();
        await refreshWatchClock();
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
    if (document.hidden) return;
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
  (runEventSource as unknown as { close: () => void }).close();
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


watch(replaySpeedMs, (delay) => {
  if (!isEmbedded.value) saveReplayDelay(delay);
  if (replayIsPlaying.value) {
    startReplayPlayback();
  }
});

function handlePlaybackKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') { fieldFullscreen.value = false; statsOpen.value = false; return; }
  if (isEmbedded.value || firstReplayLockActive.value || event.ctrlKey || event.metaKey || event.altKey || isShortcutInput(event.target)) return;
  if (event.code === 'Space') {
    event.preventDefault();
    toggleReplayPlay();
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    stepReplay(event.key === 'ArrowLeft' ? -1 : 1);
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handlePlaybackKeydown);
  window.addEventListener('message', onRendererMessage);
  document.addEventListener('visibilitychange', onVisibilityChange);
  replayClockHandle = setInterval(syncFirstReplayFrame, 100);
  await bootstrapPage();
});

onUnmounted(() => {
  disposed = true;
  document.removeEventListener('visibilitychange', onVisibilityChange);
  if (firstShowRefreshHandle) clearTimeout(firstShowRefreshHandle);
  window.removeEventListener('keydown', handlePlaybackKeydown);
  window.removeEventListener('message', onRendererMessage);
  if (replayClockHandle) clearInterval(replayClockHandle);
  stopReplayPlayback();
  stopRunLiveUpdates();
});
</script>

<style scoped>
.arena-match-code-error { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 12px 16px; color: var(--agp-danger); background: var(--arena-error-soft); border-bottom: 1px solid var(--agp-border); font-size: 13px; }
.arena-match-code-error span { flex: 1 1 240px; overflow-wrap: anywhere; }
.arena-match-review { display: flex; flex-direction: column; height: calc(100dvh - 24px); min-height: 0; gap: 8px; }
.arena-match-bar { display: flex; align-items: center; flex: none; min-width: 0; min-height: 44px; gap: 8px; }
.arena-match-bar h1 { font-size: 14px; line-height: 20px; font-weight: 600; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.arena-match-bar time { margin-left: auto; font-size: 11px; color: var(--agp-text-muted); white-space: nowrap; }
.arena-match-columns { display: grid; grid-template-columns: minmax(0,1fr) 320px; gap: 8px; flex: 1; min-height: 0; }
.arena-match-review--source .arena-match-columns { grid-template-columns: minmax(0,52fr) minmax(0,48fr); }
.arena-match-source, .arena-match-field { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.arena-match-pane-head { display: flex; align-items: center; flex: none; gap: 8px; min-height: 44px; padding: 6px 12px; border-bottom: 1px solid var(--agp-border); font-size: 12px; }
.arena-match-pane-head > .agp-panel-toggle { margin-left: auto; }
.arena-match-source-head .form-select { width: auto; max-width: 50%; }
.arena-match-code-time { color: var(--agp-text-muted); font-size: 11px; margin-left: auto; text-align: right; }
.arena-match-source > .agp-code-editor { flex: 1; min-height: 0; overflow: hidden; }
.arena-match-source :deep(.cm-editor) { height: 100%; min-height: 0 !important; border: 0 !important; border-radius: 0 !important; }
.arena-match-files { display: flex; align-items: center; gap: 8px; padding: 4px 12px; border-bottom: 1px solid var(--agp-border); font-size: 12px; }
.arena-match-files select { width: auto; }
.arena-match-source-foot { padding: 8px 12px; border-top: 1px solid var(--agp-border); }
.arena-match-view { position: relative; flex: 1; min-height: 0; background: var(--agp-surface-soft); }
.arena-match-view > iframe { display: block; width: 100%; height: 100%; border: 0; }
.arena-match-loading { position: absolute; z-index: 2; inset: 0; display: grid; place-items: center; background: var(--agp-surface); }
.arena-match-lock { position: absolute; top: 8px; right: 8px; z-index: 2; padding: 4px 8px; border-radius: 6px; color: var(--agp-text-muted); background: var(--agp-surface); font-size: 11px; }
.arena-match-playback { flex: none; padding: 6px 8px; border-top: 1px solid var(--agp-border); }
.arena-match-insights { flex: none; max-height: 40%; overflow: auto; border-top: 1px solid var(--agp-border); font-size: 12px; }
.arena-match-insights > summary { padding: 8px 12px; color: var(--agp-text-muted); cursor: pointer; }
.arena-match-standings { min-height: 0; overflow: auto; padding: 16px; }
.arena-match-standings h2, .arena-match-dialog h2 { font-size: 16px; line-height: 24px; margin: 0 0 12px; }
.arena-match-technical { font-size: 12px; margin-top: 16px; color: var(--agp-text-muted); }
.arena-match-technical dl { display: grid; grid-template-columns: auto 1fr; gap: 8px; margin: 12px 0 0; }
.arena-match-technical dd { margin: 0; text-align: right; color: var(--agp-text); }
.arena-match-mobile-players { display: none; }
.arena-match-review--embedded { height: 100dvh; gap: 0; }
.arena-match-review--embedded .arena-match-columns { grid-template-columns: minmax(0,1fr); gap: 0; }
.arena-match-review--embedded .arena-match-field { border: 0; border-radius: 0; }
.arena-match-review--fullscreen .arena-match-field { position: fixed; inset: 8px; z-index: 150; }
.arena-match-dialog { width: min(100%, 560px); max-height: 80dvh; overflow: auto; padding: 16px; }
.arena-modal-backdrop { position: fixed; inset: 0; z-index: 300; display: grid; place-items: center; padding: 16px; background: #10182766; }
.arena-match-dialog > header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.arena-match-dialog h2 { margin: 0; }
@media(max-width:900px) {
  .arena-match-review:not(.arena-match-review--embedded) { height: calc(100dvh - 16px); }
  .arena-match-bar { flex-wrap: wrap; }
  .arena-match-bar h1 { flex: 1; }
  .arena-match-bar time { order: 3; width: 100%; margin: 0; }
  .arena-match-mobile-players { display: inline-flex; }
  .arena-match-columns, .arena-match-review--source .arena-match-columns { grid-template-columns: minmax(0,1fr); }
  .arena-match-standings, .arena-match-review--source .arena-match-field { display: none; }
  .arena-match-review--fullscreen .arena-match-field { display: flex; }
}
</style>
