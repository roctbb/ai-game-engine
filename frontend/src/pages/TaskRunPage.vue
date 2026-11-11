<template>
  <section
    class="arena-workspace"
    :class="{
      'arena-workspace--field': mobilePanel === 'viewer' || conditionPanelOpen,
      'arena-workspace--fullscreen': isViewerFullscreen,
    }"
  >
    <header class="arena-workbar">
      <RouterLink :to="taskBackTarget" class="agp-back-link" :aria-label="reviewBackLabel" @click="onReviewBack"><AppIcon name="back" /></RouterLink>
      <h1 :title="isReviewMode ? reviewTitle : game?.title">{{ isReviewMode ? reviewTitle : game?.title || 'Задача' }}</h1>
      <span class="arena-save-time" role="status">{{ isReviewMode ? formatTime(currentRun?.created_at) : draftStateLabel }}</span>
      <template v-if="isReviewMode">
        <div v-if="canUseDemoStrategy" class="arena-review-navigation">
          <button class="btn btn-outline-secondary" aria-label="Новее" :disabled="isInspecting || inspectionIndex <= 0" @click="inspectAdjacent(-1)">←<span>Новее</span></button>
          <button class="btn btn-outline-secondary" aria-label="Старее" :disabled="isInspecting || inspectionIndex < 0 || inspectionIndex >= inspectionAttempts.length - 1" @click="inspectAdjacent(1)"><span>Старее</span>→</button>
        </div>
        <button v-if="canTakeSnapshot" class="btn btn-primary arena-review-own-action" aria-label="Взять код в работу" @click="takeSnapshot"><span class="arena-review-action-wide">Взять код в работу</span><span class="arena-review-action-compact">Взять код</span></button>
        <ActionMenu label="Действия с попыткой" :items="reviewMenuItems" @select="handleReviewAction" />
      </template>
      <template v-else>
        <SnakeLoader v-if="!isBootstrapping && (isRunActive || isLaunching)" :label="runStatusLabel" />
        <button class="btn btn-outline-secondary" :aria-pressed="conditionPanelOpen" :disabled="isBootstrapping" @click="toggleConditionPanel">Условие</button>
        <button v-if="isRunActive" class="btn btn-outline-danger" :disabled="!canStop" @click="stopRun"><AppIcon name="stop" />Стоп</button>
        <button v-else class="btn btn-primary" :disabled="!canLaunch || isSaving" title="⌘ / Ctrl + Enter" @click="launchRun()"><AppIcon name="play" />Запустить</button>
      </template>
    </header>
    <p v-if="errorMessage" class="text-danger mb-0" role="alert">
      {{ errorMessage }}
    </p>
    <nav v-if="isMobile" class="arena-mobile-panes" aria-label="Рабочая панель">
      <button
        :aria-pressed="mobilePanel === 'code' && !conditionPanelOpen"
        @click="
          mobilePanel = 'code';
          closeConditionPanel();
        "
      >
        Код</button
      ><button
        :aria-pressed="mobilePanel === 'viewer' || conditionPanelOpen"
        @click="mobilePanel = 'viewer'"
      >
        Поле
      </button>
    </nav>
    <LoadingSkeleton
      v-if="isBootstrapping"
      :count="2"
      layout="workspace"
      :style="{ '--agp-skeleton-workspace-columns': `${splitRatio}fr ${100 - splitRatio}fr` }"
      label="Готовим рабочее место"
    />
    <div
      v-if="game && !isBootstrapping"
      ref="mainColumnsRef"
      class="arena-workpanes"
      :class="{ 'arena-workpanes--resizing': isSplitResizing }"
      :style="{
        gridTemplateColumns: isMobile
          ? 'minmax(0, 1fr)'
          : `${splitRatio}fr 8px ${100 - splitRatio}fr`,
      }"
    >
      <article class="arena-code-pane agp-card">
        <header class="arena-pane-head">
          <strong>strategy.py<span v-if="reviewingRunCode && diagnostic" class="arena-review-file-error" role="img" :aria-label="'Ошибка кода' + (diagnostic.line ? ', строка ' + diagnostic.line : '')">×</span></strong>
          <span v-if="reviewingRunCode" class="arena-review-code-meta"><time>Код {{ formatTime(reviewCapturedAt) }}</time><span>только чтение</span></span>
          <details v-if="!reviewingRunCode" class="arena-file-menu">
            <summary aria-label="Меню файла">⋯</summary>
            <div>
              <button :disabled="!selectedSlotKey" @click="applyTemplate">
                Вставить шаблон</button
              ><button v-if="replacementUndo !== null" @click="undoReplacement">
                Отменить замену</button
              ><button
                v-if="canUseDemoStrategy"
                :disabled="!firstDemoCode"
                @click="applyDemo"
              >
                Пример стратегии</button
              ><button :disabled="!isDirty || isSaving" @click="saveCode">
                Сохранить</button
              ><button
                v-if="currentRun?.snapshot_id"
                @click="inspectRunLine({ line: 1 })"
              >
                Код запуска</button
              ><label
                ><input v-model="debugEnabled" type="checkbox" />Записать
                отладку</label
              >
            </div>
          </details>
        </header>
        <CodeEditor
          v-if="reviewingRunCode"
          :model-value="reviewCode"
          readonly
          :focus-line="reviewLine"
          :error-line="diagnostic?.line"
          language="python"
        />
        <CodeEditor
          v-show="!reviewingRunCode"
          ref="codeEditorRef"
          v-model="editorCode"
          :readonly="!selectedSlotKey"
          language="python"
          @run="launchRun()"
        />
      </article>
      <button
        v-if="!isMobile"
        class="agp-main-splitter"
        role="separator"
        aria-label="Ширина редактора"
        aria-orientation="vertical"
        :aria-valuenow="splitRatio"
        aria-valuemin="32"
        aria-valuemax="70"
        @pointerdown="startSplitResize"
        @keydown.left.prevent="splitRatio = clampSplitRatio(splitRatio - 2)"
        @keydown.right.prevent="splitRatio = clampSplitRatio(splitRatio + 2)"
      ></button>
      <article
        class="arena-field-pane agp-card"
        :class="{ 'arena-field-pane--reference': conditionPanelOpen }"
      >
        <GameReference
          v-show="conditionPanelOpen"
          :title="game.title"
          :description="game.description"
          :instruction="docs?.player_instruction"
          :template="selectedTemplateCode"
          :docs="docs"
          :frame="referenceFrame"
          :arguments="currentDebugArguments"
          :is-actual="!!currentReplayFrame"
          @close="closeConditionPanel"
        />
        <template v-if="!conditionPanelOpen">
          <header v-if="!reviewingRunCode || !diagnostic" class="arena-pane-head">
            <strong v-if="reviewingRunCode && currentRun" :class="'arena-review-outcome--' + attemptPresentation(currentRun).tone">{{ attemptPresentation(currentRun).icon }} {{ attemptPresentation(currentRun).label }} · {{ attemptPresentation(currentRun).score }}</strong>
            <strong v-else>{{
              isRunActive ? runStatusLabel : currentRun ? "Результат" : "Поле"
            }}</strong
            ><span v-if="currentRun && !reviewingRunCode" class="small text-muted">{{
              formatTime(currentRun.created_at)
            }}</span
            ><button
              v-if="currentRun && !isRunActive && !reviewingRunCode"
              class="agp-panel-toggle"
              :disabled="!canLaunch"
              @click="launchRun(currentRun.run_id)"
            >
              Повторить поле
            </button>
            <button v-if="reviewingRunCode" class="agp-panel-toggle" @click="isViewerFullscreen ? closeViewerFullscreen() : openViewerFullscreen()">{{ isViewerFullscreen ? 'Вернуть код' : 'На весь экран' }}</button>
          </header>
          <div v-if="diagnostic" class="arena-diagnostic" role="alert">
            <strong>× {{ diagnostic.title }}</strong
            ><button
              v-if="diagnostic.line"
              @click="
                inspectRunLine({ line: diagnostic.line, role: diagnostic.role })
              "
            >
              Строка {{ diagnostic.line }}
            </button>
            <details v-if="!reviewingRunCode">
              <summary>Подробности</summary>
              <pre>{{ diagnostic.message }}</pre>
            </details>
          </div>
        </template>
        <div v-show="!conditionPanelOpen" class="arena-field-canvas">
          <iframe
            v-if="rendererUrl"
            ref="rendererFrameRef"
            :key="rendererKey"
            :src="rendererUrl"
            title="Визуализация задачи"
            sandbox="allow-scripts"
            @load="sendRendererInit"
          ></iframe>
          <div v-if="isReplayLoading" class="arena-field-loading">
            <SnakeLoader label="Загрузка повтора" />
          </div>
          <p
            v-if="replayError"
            role="alert"
            class="arena-field-loading text-danger"
          >
            {{ replayError }}
          </p>
        </div>
        <template v-if="!conditionPanelOpen">
          <ReplayControls
            v-if="replayFrames.length"
            v-model:frame-index="replayFrameIndex"
            v-model:delay="replayPlaybackDelayMs"
            :frame-count="replayFrames.length"
            :playing="replayIsPlaying"
            :can-play="replayFrames.length > 1"
            :can-step-backward="replayFrameIndex > 0"
            :can-step-forward="replayFrameIndex < replayFrames.length - 1"
            :markers="moments"
            @toggle="toggleReplay"
            @step="stepReplay"
          />
          <details
            v-if="replayFrames.length"
            class="agp-analysis-disclosure"
            :open="analysisOpen"
            @toggle="analysisOpen = ($event.target as HTMLDetailsElement).open"
          >
            <summary>Разбор хода</summary>
            <ReplayInsights
              @pause="stopReplayPlayback()"
              :frames="replay?.frames ?? []"
              :events="replay?.events ?? []"
              :frame-index="replayFrameIndex"
              @seek="seekReplay"
              @line="inspectRunLine"
            />
          </details>
          <BotConsole initially-collapsed :label="reviewingRunCode ? (diagnostic ? 'Подробности ошибки' : 'Консоль и события') : 'Вывод запуска'">
            <pre v-if="reviewingRunCode && diagnostic" class="arena-review-error-details">{{ diagnostic.message }}</pre>
            <div
              v-for="line in (reviewingRunCode && diagnostic ? [] : currentConsoleLines)"
              :key="line.id"
              class="agp-bot-console-line"
              :class="{ 'agp-bot-console-line--error': line.tone === 'error' }"
            >
              <span class="mono agp-bot-console-message">{{
                line.message
              }}</span
              ><button
                v-if="line.line"
                class="agp-error-line"
                @click="inspectRunLine({ line: line.line, role: line.role })"
              >
                Строка {{ line.line }}
              </button>
            </div></BotConsole
          >
        </template>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import ActionMenu, { type ActionMenuItem } from '../components/ActionMenu.vue';
import { attemptPresentation } from '../lib/attemptPresentation';
import { RouterLink, useRoute, useRouter } from "vue-router";

import SnakeLoader from "../components/SnakeLoader.vue";
import { formatTime } from "../lib/attemptPresentation";
import CodeEditor from "../components/CodeEditor.vue";
import GameReference from "../components/GameReference.vue";
import ReplayInsights from "../components/ReplayInsights.vue";
import { record, replayMoments } from "../lib/replayInsights";
import AppIcon from "../components/AppIcon.vue";
import BotConsole from "../components/BotConsole.vue";
import ReplayControls from "../components/ReplayControls.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import {
  createReplayClock,
  loadReplayDelay,
  saveReplayDelay,
} from "../lib/replayPlayback";
import { isShortcutInput } from "../lib/keyboard";
import {
  createTeam,
  getGame,
  getGameDocs,
  getGameTemplates,
  getRendererPreview,
  getRun,
  getRunReplay,
  getRunCode,
  getWorkspace,
  listSingleTaskAttempts,
  listTeamsByGame,
  startSingleTaskRun,
  stopSingleTaskRun,
  updateSlotCode,
  type GameDto,
  type GameDocumentationDto,
  type GameTemplatesDto,
  type ReplayDto,
  type RendererPreviewDto,
  type RunDto,
  type TeamDto,
  type TeamWorkspaceDto,
} from "../lib/api";
import { sanitizeForPostMessage } from "../lib/postMessage";
import { loadTeamMapping, saveTeamMapping } from "../lib/teamMapping";
import { useSessionStore } from "../stores/session";

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
  tone?: "error";
  line?: number;
}
type WorkspaceViewMode = "viewer" | "split" | "code";

const route = useRoute();
const router = useRouter();
const contextQuery = computed(() =>
  Object.fromEntries(
    Object.entries(route.query).filter(
      ([key]) =>
        ![
          "inspect_run",
          "line",
          "role",
          "back",
          "attempt_user",
          "attempt_offset",
        ].includes(key),
    ),
  ),
);
async function resumeDraft(): Promise<void> {
  inspectionToken += 1;
  isInspecting.value = false;
  stopRunPolling();
  reviewingRunCode.value = false;
  await router.replace({ query: contextQuery.value });
  await refreshStats();
}
const sessionStore = useSessionStore();
const SPLIT_RATIO_STORAGE_KEY = "agp_task_workspace_split_ratio";
const VIEW_MODE_STORAGE_KEY = "agp_task_workspace_view_mode";
const game = ref<GameDto | null>(null);
const reviewReturnToEditor = ref(false);
const taskBackTarget = computed(() =>
  reviewReturnToEditor.value && reviewingRunCode.value
    ? { name: 'task-run', params: { gameId: String(route.params.gameId) }, query: contextQuery.value }
    : typeof route.query.back === "string" &&
  route.query.back.startsWith(
    `/tasks/${game.value?.game_id || String(route.params.gameId)}`,
  )
    ? route.query.back
    : {
        name: "task",
        params: { gameId: game.value?.game_id || String(route.params.gameId) },
        query: contextQuery.value,
      },
);
const templates = ref<GameTemplatesDto | null>(null);
const docs = ref<GameDocumentationDto | null>(null);
const workspace = ref<TeamWorkspaceDto | null>(null);
const teamsByGame = ref<TeamDto[]>([]);
const teamId = ref("");
const selectedSlotKey = ref("");
const editorCode = ref("");
const savedCode = ref("");
const currentRun = ref<RunDto | null>(null);
const replay = ref<ReplayDto | null>(null);
const rendererPreview = ref<RendererPreviewDto | null>(null);
const repeatPreview = ref<RendererPreviewDto | null>(null);
const attempts = ref<RunDto[]>([]);
const conditionPanelOpen = ref(false);
const debugEnabled = ref(false);
const previousRun = ref<RunDto | null>(null);
const analysisOpen = ref(false);
const replacementUndo = ref<string | null>(null);
const draftSavedAt = ref("");
const draftStorageFailed = ref(false);
const reviewingRunCode = ref(false);
const reviewCode = ref("");
const reviewLine = ref(1);
const reviewCapturedAt = ref("");
const inspectionAttempts = ref<RunDto[]>([]);
const isInspecting = ref(false);
let inspectionToken = 0;
const isReviewMode = computed(() => reviewingRunCode.value || typeof route.query.inspect_run === 'string');
const reviewTitle = computed(() => {
  const author = currentRun.value?.requested_by;
  return author ? 'Попытка · ' + author : 'Разбор запуска';
});
const reviewBackLabel = computed(() => reviewReturnToEditor.value && reviewingRunCode.value ? 'К редактору' : typeof route.query.back === 'string' && route.query.back.includes('/attempts') ? 'К истории попыток' : 'К задаче');
function onReviewBack(event: MouseEvent): void {
  if (reviewReturnToEditor.value && reviewingRunCode.value) { event.preventDefault(); resumeDraft(); }
}
const reviewMenuItems = computed<ActionMenuItem[]>(() => [
  { id: 'condition', label: 'Условие и API', disabled: isBootstrapping.value },
  { id: 'draft', label: 'Мой редактор', disabled: isBootstrapping.value || isInspecting.value },
  { id: 'repeat', label: 'Повторить поле с моим кодом', disabled: !canLaunch.value || isInspecting.value || !reviewingRunCode.value || !currentRun.value },
]);
async function handleReviewAction(action: string): Promise<void> {
  if (action === 'condition') toggleConditionPanel();
  if (action === 'draft') resumeDraft();
  if (action === 'repeat' && currentRun.value) {
    const repeatRunId = currentRun.value.run_id;
    reviewingRunCode.value = false;
    await router.replace({ query: contextQuery.value });
    await launchRun(repeatRunId);
  }
}

const inspectionIndex = computed(() =>
  inspectionAttempts.value.findIndex(
    (run) => run.run_id === currentRun.value?.run_id,
  ),
);
const canTakeSnapshot = computed(
  () =>
    reviewingRunCode.value &&
    !isBootstrapping.value && !isInspecting.value &&
    currentRun.value?.requested_by === sessionStore.nickname,
);
function takeSnapshot(): void {
  if (!canTakeSnapshot.value) return;
  replacementUndo.value = editorCode.value;
  editorCode.value = reviewCode.value;
  resumeDraft();
}
function inspectAdjacent(delta: number): void {
  const run = inspectionAttempts.value[inspectionIndex.value + delta];
  if (run) void inspectRunLine({ line: 1 }, run.run_id);
}

const draftStateLabel = computed(() => {
  if (isSaving.value) return "Сохраняем…";
  if (!savedCode.value && editorCode.value === selectedTemplateCode.value)
    return "Стартовый шаблон";
  if (!isDirty.value)
    return formatTime(
      workspace.value?.slot_states.find(
        (s) => s.slot_key === selectedSlotKey.value,
      )?.updated_at,
    );
  if (draftStorageFailed.value) return "Черновик не сохранён на устройстве";
  return draftSavedAt.value
    ? `Черновик на устройстве · ${draftSavedAt.value}`
    : "Черновик";
});
const moments = computed(() =>
  replayMoments(replay.value?.events ?? [], replay.value?.frames ?? []),
);
const referenceFrame = computed(
  () =>
    currentReplayFrame.value?.frame ??
    repeatPreview.value?.frame ??
    rendererPreview.value?.frame ??
    {},
);
const currentDebugArguments = computed(
  () =>
    replay.value?.events.find(
      (e) =>
        e.type === "debug_snapshot" &&
        e.tick === currentReplayFrame.value?.tick,
    )?.arguments,
);

const isViewerFullscreen = ref(false);
const replayFrameIndex = ref(0);
const replayIsPlaying = ref(false);
const replayPlaybackDelayMs = ref(loadReplayDelay());
const isBootstrapping = ref(false);
const isSaving = ref(false);
const isLaunching = ref(false);
const isCancelling = ref(false);
const isRestarting = ref(false);
const isReplayLoading = ref(false);
const isRefreshingStats = ref(false);
const statusNow = ref(Date.now());
const statusTimer = setInterval(() => {
  if (isRunActive.value) statusNow.value = Date.now();
}, 1000);
const errorMessage = ref("");
const replayError = ref("");
const launchNotice = ref("");
const rendererFrameRef = ref<HTMLIFrameElement | null>(null);
const mainColumnsRef = ref<HTMLElement | null>(null);
const rendererKey = ref(0);
const splitRatio = ref(loadSplitRatio());
const isSplitResizing = ref(false);
const viewMode = ref<WorkspaceViewMode>(loadViewMode());
const isHeaderCondensed = ref(false);
let pollingHandle: ReturnType<typeof setInterval> | null = null;
const replayPlaybackClock = createReplayClock(
  () => {
    const last = replayFrames.value.length - 1;
    if (replayFrameIndex.value < last) replayFrameIndex.value += 1;
    if (replayFrameIndex.value >= last) stopReplayPlayback({ completed: true });
  },
  () => replayPlaybackDelayMs.value,
);
const isMobile = ref(window.matchMedia("(max-width: 900px)").matches);
const mobilePanel = ref<
  "code" | "viewer" | "console" | "analysis" | "reference"
>("code");
const mobileMedia = window.matchMedia("(max-width: 900px)");
watch(mobilePanel, (panel) => {
  conditionPanelOpen.value = panel === "reference";
});
function updateMobileMode(): void {
  isMobile.value = mobileMedia.matches;
}
let isPollingRun = false;
let pendingRunPoll = false;
let runPollingToken = 0;

const rendererUrl = computed(() =>
  game.value ? `/api/v1/renderers/${game.value.slug}/renderer/index.html` : "",
);
const selectedTemplateCode = computed(
  () =>
    templates.value?.templates.find(
      (item) => item.slot_key === selectedSlotKey.value,
    )?.code ?? "",
);
const firstDemoCode = computed(
  () =>
    templates.value?.demo_strategies.find(
      (item) => item.slot_key === selectedSlotKey.value,
    )?.code ?? "",
);
const isDirty = computed(() => editorCode.value !== savedCode.value);
const isRunActive = computed(() =>
  currentRun.value
    ? ["created", "queued", "running"].includes(currentRun.value.status)
    : false,
);
const canLaunch = computed(
  () =>
    Boolean(
      game.value &&
        teamId.value &&
        selectedSlotKey.value &&
        editorCode.value.trim(),
    ) &&
    !isLaunching.value &&
    !isBootstrapping.value &&
    !isRestarting.value &&
    !isRunActive.value,
);
const canStop = computed(
  () =>
    Boolean(game.value && currentRun.value && isRunActive.value) &&
    !isCancelling.value &&
    !isRestarting.value,
);
const canRestart = computed(
  () =>
    Boolean(
      game.value &&
        currentRun.value &&
        isRunActive.value &&
        selectedSlotKey.value &&
        editorCode.value.trim(),
    ) &&
    !isCancelling.value &&
    !isLaunching.value &&
    !isRestarting.value,
);
const replayFrames = computed<ReplayFrameView[]>(() =>
  (replay.value?.frames ?? []).map((item, index) => {
    const tick = typeof item.tick === "number" ? item.tick : index;
    const phase =
      typeof item.phase === "string"
        ? item.phase
        : (replay.value?.status ?? "unknown");
    const frame = isRecord(item.frame) ? item.frame : {};
    return { tick, phase, frame };
  }),
);
const currentReplayFrame = computed(
  () => replayFrames.value[replayFrameIndex.value] ?? null,
);
const botConsoleLines = computed<BotConsoleLine[]>(() => {
  const lines: BotConsoleLine[] = [];
  const replayEvents = replay.value?.events ?? [];
  replayEvents.forEach((event, index) =>
    appendConsoleLine(lines, event, `event-${index}`),
  );
  (replay.value?.frames ?? []).forEach((frame, index) => {
    if (!isRecord(frame)) return;
    const tick = normalizeTick(frame.tick, index);
    const framePayload = isRecord(frame.frame) ? frame.frame : frame;
    appendConsoleCollection(
      lines,
      framePayload.prints,
      tick,
      "",
      `frame-${index}-prints`,
    );
    appendConsoleCollection(
      lines,
      framePayload.logs,
      tick,
      "",
      `frame-${index}-logs`,
    );
    appendConsoleCollection(
      lines,
      framePayload.console,
      tick,
      "",
      `frame-${index}-console`,
    );
    appendConsoleCollection(
      lines,
      framePayload.stdout,
      tick,
      "",
      `frame-${index}-stdout`,
    );
  });
  if (replayEvents.length === 0 && currentRun.value?.result_payload) {
    appendConsoleCollection(
      lines,
      currentRun.value.result_payload.prints,
      0,
      "",
      "result-prints",
    );
    appendConsoleCollection(
      lines,
      currentRun.value.result_payload.logs,
      0,
      "",
      "result-logs",
    );
    appendConsoleCollection(
      lines,
      currentRun.value.result_payload.stdout,
      0,
      "",
      "result-stdout",
    );
  }
  appendRunDiagnosticLines(lines, currentRun.value, replay.value);
  return lines.sort(
    (left, right) => left.tick - right.tick || left.id.localeCompare(right.id),
  );
});
const diagnostic = computed(() => {
  const error =
    botConsoleLines.value.find((line) => line.tone === "error" && line.line) ||
    botConsoleLines.value.find((line) => line.tone === "error");
  if (!error && !friendlyRunProblem.value) return null;
  const message = error?.message || friendlyRunProblem.value;
  const line =
    error?.line || Number(message.match(/line (\d+)/)?.[1]) || undefined;
  return {
    message,
    line,
    role: error?.role,
    title: message.split("\n").filter(Boolean).at(-1) || "Ошибка выполнения",
  };
});
const currentConsoleLines = computed(() => {
  if (replayFrames.value.length === 0) return botConsoleLines.value;
  const tick = currentReplayFrame.value?.tick ?? 0;
  return botConsoleLines.value.filter((line) => line.tick <= tick);
});
const canUseDemoStrategy = computed(
  () => sessionStore.role === "teacher" || sessionStore.role === "admin",
);
const hasBotError = computed(() => {
  const metrics = record(
    currentRun.value?.result_payload?.metrics ??
      (replay.value?.run_id === currentRun.value?.run_id
        ? replay.value?.summary.metrics
        : undefined),
  );
  return Number(metrics.bot_errors) > 0 || Boolean(metrics.compile_error);
});
const runStatusLabel = computed(() => {
  if (hasBotError.value) return "Ошибка в коде";
  if (!currentRun.value) return "Готов к запуску";
  const label = attemptStatusLabel(currentRun.value.status);
  if (!isRunActive.value) return label;
  const started = Date.parse(
    currentRun.value.started_at ||
      currentRun.value.queued_at ||
      currentRun.value.created_at,
  );
  const seconds = Math.max(0, Math.floor((statusNow.value - started) / 1000));
  return `${label} · ${seconds} с`;
});
const runStatusTone = computed<"idle" | "active" | "success" | "danger">(() => {
  if (!currentRun.value) return "idle";
  if (["created", "queued", "running"].includes(currentRun.value.status))
    return "active";
  if (hasBotError.value) return "danger";
  if (currentRun.value.status === "finished") return "success";
  if (["failed", "timeout", "canceled"].includes(currentRun.value.status))
    return "danger";
  return "idle";
});
const friendlyRunProblem = computed(() => {
  if (!currentRun.value) return "";
  if (currentRun.value.status === "failed")
    return (
      currentRun.value.error_message ||
      "Код не запустился. Детали можно посмотреть в подробном просмотре."
    );
  if (currentRun.value.status === "timeout")
    return "Решение работало слишком долго и было остановлено.";
  if (currentRun.value.status === "canceled") return "Запуск остановлен.";
  return "";
});

function gameIdFromRoute(): string {
  return String(route.params.gameId || "").trim();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeTick(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function appendConsoleLine(
  lines: BotConsoleLine[],
  raw: unknown,
  id: string,
  fallbackTick = 0,
): void {
  if (typeof raw === "string") {
    appendConsoleMessage(lines, raw, fallbackTick, "", id);
    return;
  }
  if (!isRecord(raw)) return;

  const type = typeof raw.type === "string" ? raw.type : "";
  const hasConsoleShape =
    type === "bot_print" ||
    type === "print" ||
    type === "stdout" ||
    type === "bot_stdout" ||
    type === "console" ||
    type === "compile_error" ||
    type === "runtime_error" ||
    type === "bot_error" ||
    type === "run_error" ||
    type === "timeout" ||
    "stdout" in raw;
  if (!hasConsoleShape) return;

  const messageRaw =
    raw.message ?? raw.text ?? raw.line ?? raw.stdout ?? raw.value;
  const message =
    typeof messageRaw === "string" ? messageRaw : String(messageRaw ?? "");
  if (!message) return;
  const tick = normalizeTick(
    raw.tick ?? raw.turn ?? raw.step ?? raw.frame,
    fallbackTick,
  );
  const roleRaw =
    raw.role ?? raw.slot ?? raw.slot_key ?? raw.team_id ?? raw.bot;
  const role =
    typeof roleRaw === "string" || typeof roleRaw === "number"
      ? String(roleRaw)
      : diagnosticRoleForEvent(type);
  appendConsoleMessage(
    lines,
    message,
    tick,
    role,
    id,
    isDiagnosticConsoleEvent(type) ? "error" : undefined,
  );
  if (type === "bot_error" && typeof raw.line === "number" && lines.length)
    lines[lines.length - 1].line = raw.line;
}

function appendConsoleCollection(
  lines: BotConsoleLine[],
  raw: unknown,
  tick: number,
  role: string,
  idPrefix: string,
): void {
  if (raw === undefined || raw === null) return;
  if (typeof raw === "string") {
    appendConsoleMessage(lines, raw, tick, role, idPrefix);
    return;
  }
  if (Array.isArray(raw)) {
    raw.forEach((item, index) =>
      appendConsoleLine(lines, item, `${idPrefix}-${index}`, tick),
    );
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
  tone?: BotConsoleLine["tone"],
): void {
  const chunks = message.split(/\r?\n/);
  chunks.forEach((chunk, index) => {
    if (!chunk) return;
    lines.push({
      id: `${idPrefix}-${index}`,
      tick,
      role,
      message: chunk,
      tone,
    });
  });
}

function appendRunDiagnosticLines(
  lines: BotConsoleLine[],
  run: RunDto | null,
  currentReplay: ReplayDto | null,
): void {
  if (!run || isRunActive.value) return;
  const diagnostics: string[] = [];
  if (run.error_message) {
    diagnostics.push(run.error_message);
  }
  appendResultPayloadDiagnostics(diagnostics, run.result_payload);
  const summaryError = currentReplay?.summary?.error_message;
  if (
    typeof summaryError === "string" &&
    summaryError.trim() &&
    !diagnostics.includes(summaryError)
  ) {
    diagnostics.push(summaryError);
  }
  if (run.status === "timeout" && diagnostics.length === 0) {
    diagnostics.push("Решение работало слишком долго и было остановлено.");
  } else if (run.status === "failed" && diagnostics.length === 0) {
    diagnostics.push("Код не запустился.");
  }
  diagnostics
    .filter((message) => !lines.some((line) => line.message === message))
    .forEach((message, index) => {
      appendConsoleMessage(
        lines,
        message,
        0,
        diagnosticRoleForStatus(run.status, message),
        `run-diagnostic-${index}`,
        "error",
      );
    });
}

function appendResultPayloadDiagnostics(
  diagnostics: string[],
  payload: Record<string, unknown> | null,
): void {
  const error = payload?.error;
  if (typeof error === "string" && error.trim()) diagnostics.push(error);
  const metrics = isRecord(payload?.metrics) ? payload.metrics : {};
  const compileError = metrics.compile_error;
  if (typeof compileError === "string" && compileError.trim())
    diagnostics.push(compileError);
  const compileErrors = metrics.compile_errors;
  if (isRecord(compileErrors)) {
    Object.entries(compileErrors).forEach(([slot, message]) => {
      if (typeof message === "string" && message.trim()) {
        diagnostics.push(`${slot}: ${message}`);
      }
    });
  }
}

function diagnosticRoleForStatus(
  status: RunDto["status"],
  message = "",
): string {
  const normalized = message.toLowerCase();
  if (
    status === "timeout" ||
    normalized.includes("timed out") ||
    normalized.includes("timeout")
  )
    return "таймаут";
  if (status === "canceled") return "остановлено";
  return "ошибка запуска";
}

function diagnosticRoleForEvent(type: string): string {
  if (type === "timeout") return "таймаут";
  if (type === "compile_error") return "ошибка кода";
  if (type === "runtime_error") return "ошибка выполнения";
  if (type === "run_error") return "ошибка запуска";
  return "";
}

function isDiagnosticConsoleEvent(type: string): boolean {
  return [
    "compile_error",
    "runtime_error",
    "bot_error",
    "run_error",
    "timeout",
  ].includes(type);
}

function isActiveRun(run: RunDto | null): run is RunDto {
  return Boolean(run && ["created", "queued", "running"].includes(run.status));
}

function toggleConditionPanel(): void {
  conditionPanelOpen.value = !conditionPanelOpen.value;
  if (conditionPanelOpen.value) {
    viewMode.value = "split";
    if (isMobile.value) mobilePanel.value = "reference";
  }
}

function closeConditionPanel(): void {
  conditionPanelOpen.value = false;
  if (mobilePanel.value === "reference") mobilePanel.value = "viewer";
}

function closeSidePanels(): void {
  closeConditionPanel();
}

function openViewerFullscreen(): void {
  isViewerFullscreen.value = true;
}

function closeViewerFullscreen(): void {
  isViewerFullscreen.value = false;
}

function updateHeaderCondensed(): void {
  isHeaderCondensed.value = false;
}

function onRendererMessage(event: MessageEvent): void {
  if (event.source !== rendererFrameRef.value?.contentWindow) return;
  const data = event.data;
  if (data?.type === "agp.renderer.ready") {
    sendRendererInit();
    return;
  }
  if (
    data?.type !== "agp.renderer.shortcut" ||
    ![
      "Space",
      "ArrowLeft",
      "ArrowRight",
      "Digit1",
      "Digit2",
      "Digit3",
      "Escape",
    ].includes(data.payload?.code)
  )
    return;
  handlePageKeydown(
    new KeyboardEvent("keydown", {
      key: String(data.payload.key),
      code: data.payload.code,
    }),
  );
}
function handlePageKeydown(event: KeyboardEvent): void {
  if (event.defaultPrevented) return;
  if (
    (event.metaKey || event.ctrlKey) &&
    event.key === "Enter" &&
    !reviewingRunCode.value
  ) {
    event.preventDefault();
    void launchRun();
    return;
  }
  if (event.key === "Escape") {
    closeViewerFullscreen();
    closeConditionPanel();
    closeSidePanels();
    return;
  }
  if (
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    conditionPanelOpen.value ||
    isShortcutInput(event.target)
  ) {
    return;
  }
  if (event.code === "Space") {
    event.preventDefault();
    toggleReplay();
    return;
  }
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    stepReplay(-1);
    return;
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    stepReplay(1);
    return;
  }
  if (event.key === "1") {
    setViewMode("viewer");
    return;
  }
  if (event.key === "2") {
    setViewMode("split");
    return;
  }
  if (event.key === "3") {
    setViewMode("code");
  }
}

function clampSplitRatio(nextValue: number): number {
  return Math.min(70, Math.max(32, Math.round(nextValue)));
}

function loadSplitRatio(): number {
  try {
    const stored = Number(localStorage.getItem(SPLIT_RATIO_STORAGE_KEY));
    if (stored >= 32 && stored <= 70) return stored;
  } catch {
    // localStorage may be unavailable in tests or restricted contexts
  }
  return 52;
}

function loadViewMode(): WorkspaceViewMode {
  try {
    const stored = String(localStorage.getItem(VIEW_MODE_STORAGE_KEY) ?? "");
    if (stored === "viewer" || stored === "split" || stored === "code")
      return stored;
  } catch {
    // localStorage may be unavailable in tests or restricted contexts
  }
  return "split";
}

function setViewMode(nextMode: WorkspaceViewMode): void {
  viewMode.value = nextMode;
}

function updateSplitRatioByPointer(clientX: number): void {
  const host = mainColumnsRef.value;
  if (!host) return;
  const rect = host.getBoundingClientRect();
  if (rect.width < 860) return;
  const nextRatio = ((clientX - rect.left) / rect.width) * 100;
  splitRatio.value = clampSplitRatio(nextRatio);
}

function startSplitResize(event: PointerEvent): void {
  if (window.matchMedia("(max-width: 900px)").matches) return;
  event.preventDefault();
  isSplitResizing.value = true;
  updateSplitRatioByPointer(event.clientX);
}

function handleSplitPointerMove(event: PointerEvent): void {
  if (!isSplitResizing.value) return;
  updateSplitRatioByPointer(event.clientX);
}

function stopSplitResize(): void {
  isSplitResizing.value = false;
}

async function ensurePersonalTeam(gameId: string): Promise<string> {
  const teams = await listTeamsByGame(gameId);
  teamsByGame.value = teams;
  const mapped = loadTeamMapping(gameId, sessionStore.nickname);
  if (
    mapped &&
    teams.some(
      (team) =>
        team.team_id === mapped &&
        team.captain_user_id === sessionStore.nickname,
    )
  ) {
    return mapped;
  }

  const existing = teams.find(
    (team) => team.captain_user_id === sessionStore.nickname,
  );
  if (existing) {
    saveTeamMapping(gameId, sessionStore.nickname, existing.team_id);
    return existing.team_id;
  }

  const created = await createTeam({
    game_id: gameId,
    name: `${game.value?.title ?? "Task"} / ${sessionStore.nickname}`,
    captain_user_id: sessionStore.nickname,
  });
  teamsByGame.value = [...teams, created];
  saveTeamMapping(gameId, sessionStore.nickname, created.team_id);
  return created.team_id;
}

function taskDraftKey(): string {
  return `agp_task_code_draft:${sessionStore.nickname}:${gameIdFromRoute()}:${selectedSlotKey.value}`;
}

function syncEditorFromWorkspace(payload: TeamWorkspaceDto): void {
  selectedSlotKey.value = payload.slot_states[0]?.slot_key ?? "";
  const selectedSlot = payload.slot_states.find(
    (slot) => slot.slot_key === selectedSlotKey.value,
  );
  const initialCode =
    selectedSlot?.code ??
    selectedTemplateCode.value ??
    firstDemoCode.value ??
    "";
  savedCode.value = selectedSlot?.code ?? "";
  let restoredCode = initialCode;
  try {
    const draft = JSON.parse(localStorage.getItem(taskDraftKey()) ?? "null");
    if (
      draft &&
      draft.base === savedCode.value &&
      typeof draft.code === "string"
    )
      restoredCode = draft.code;
    if (draft?.savedAt)
      draftSavedAt.value = new Date(draft.savedAt).toLocaleTimeString("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
      });
  } catch {
    draftStorageFailed.value = true;
  }
  editorCode.value = restoredCode;
}

function undoReplacement(): void {
  if (replacementUndo.value === null) return;
  editorCode.value = replacementUndo.value;
  replacementUndo.value = null;
}
function seekReplay(frame: number): void {
  stopReplayPlayback();
  replayFrameIndex.value = Math.max(
    0,
    Math.min(frame, replayFrames.value.length - 1),
  );
}
function seekProblem(frame: number): void {
  analysisOpen.value = true;
  closeConditionPanel();
  seekReplay(frame);
  if (isMobile.value) mobilePanel.value = "analysis";
}
async function inspectRunLine(
  location: { line: number; role?: string },
  runId = currentRun.value?.run_id,
): Promise<void> {
  if (!runId) return;
  const token = ++inspectionToken;
  isInspecting.value = true;
  stopRunPolling();
  stopReplayPlayback();
  if (!reviewingRunCode.value && !route.query.inspect_run) reviewReturnToEditor.value = true;
  try {
    const inspectedRun = await getRun(runId);
    if (inspectedRun.game_id !== game.value?.game_id)
      throw new Error("Попытка относится к другой задаче");
    const snapshot = await getRunCode(runId);
    if (token !== inspectionToken) return;
    if (currentRun.value?.run_id !== runId) {
      currentRun.value = inspectedRun;
      await loadReplay(runId);
    }
    if (token !== inspectionToken) return;
    const slot = location.role || selectedSlotKey.value;
    reviewCode.value =
      snapshot.codes_by_slot[slot] ??
      Object.values(snapshot.codes_by_slot)[0] ??
      "";
    reviewCapturedAt.value = snapshot.captured_at;
    reviewLine.value = location.line;
    reviewingRunCode.value = true;
    const relatedAttempts = await listSingleTaskAttempts({
      game_id: inspectedRun.game_id,
      requested_by:
        typeof route.query.attempt_user === "string"
          ? route.query.attempt_user
          : undefined,
      limit: 100,
      offset: Math.max(0, Number(route.query.attempt_offset) || 0),
    });
    if (token !== inspectionToken) return;
    inspectionAttempts.value = relatedAttempts;
    if (route.query.inspect_run !== runId)
      await router.replace({ query: { ...route.query, inspect_run: runId } });
    if (token !== inspectionToken) return;
    if (isActiveRun(inspectedRun)) startRunPolling(runId);
    if (isMobile.value) mobilePanel.value = "code";
    else if (viewMode.value === "viewer") viewMode.value = "split";
  } catch (error) {
    if (token !== inspectionToken) return;
    errorMessage.value =
      error instanceof Error ? error.message : "Не удалось открыть код запуска";
  } finally {
    if (token === inspectionToken) isInspecting.value = false;
  }
}

async function loadPage(): Promise<void> {
  const gameId = gameIdFromRoute();
  if (!gameId) {
    errorMessage.value = "Не найдена задача для запуска";
    return;
  }

  isBootstrapping.value = true;

  errorMessage.value = "";
  replay.value = null;
  rendererPreview.value = null;
  replayError.value = "";
  try {
    game.value = await getGame(gameId);
    if (game.value.mode !== "single_task") {
      throw new Error("Этот экран предназначен для задач");
    }
    const [freshTemplates, freshDocs, freshPreview] = await Promise.all([
      getGameTemplates(gameId),
      getGameDocs(gameId),
      loadRendererPreview(game.value.slug),
    ]);
    templates.value = freshTemplates;
    docs.value = freshDocs;
    rendererPreview.value = freshPreview;
    teamId.value = await ensurePersonalTeam(gameId);
    workspace.value = await getWorkspace(teamId.value);
    syncEditorFromWorkspace(workspace.value);
    await refreshStats();
    const active = attempts.value.find(
      (run) =>
        run.requested_by === sessionStore.nickname &&
        ["created", "queued", "running"].includes(run.status),
    );
    if (active && !route.query.inspect_run) {
      currentRun.value = active;
      startRunPolling(active.run_id);
    }
    sendRendererInit();
    if (typeof route.query.inspect_run === "string")
      await inspectRunLine(
        {
          line: Number(route.query.line) || 1,
          role:
            typeof route.query.role === "string" ? route.query.role : undefined,
        },
        route.query.inspect_run,
      );
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Не удалось подготовить задачу";
  } finally {
    isBootstrapping.value = false;
  }
}

async function loadRendererPreview(
  gameSlug: string,
): Promise<RendererPreviewDto | null> {
  try {
    return await getRendererPreview(gameSlug);
  } catch {
    return null;
  }
}

function applyTemplate(): void {
  if (!selectedTemplateCode.value) return;
  replacementUndo.value = editorCode.value;
  editorCode.value = selectedTemplateCode.value;
}

function applyDemo(): void {
  if (!canUseDemoStrategy.value) return;
  if (!firstDemoCode.value) return;
  replacementUndo.value = editorCode.value;
  editorCode.value = firstDemoCode.value;
}

async function saveCode(): Promise<void> {
  if (!teamId.value || !selectedSlotKey.value || !editorCode.value.trim())
    return;
  const code = editorCode.value;
  isSaving.value = true;
  errorMessage.value = "";
  try {
    await updateSlotCode({
      team_id: teamId.value,
      slot_key: selectedSlotKey.value,
      actor_user_id: sessionStore.nickname,
      code,
    });
    savedCode.value = code;
    workspace.value = await getWorkspace(teamId.value);
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Не удалось сохранить код";
    throw error;
  } finally {
    isSaving.value = false;
  }
}

async function launchRun(repeatRunId?: string): Promise<void> {
  if (!game.value || !teamId.value || isRunActive.value) return;
  previousRun.value =
    repeatRunId && currentRun.value
      ? {
          ...currentRun.value,
          result_payload:
            currentRun.value.result_payload ?? replay.value?.summary ?? null,
        }
      : null;
  const initialFrame = replayFrames.value[0];
  repeatPreview.value =
    repeatRunId && initialFrame
      ? { tick: initialFrame.tick, phase: "preview", frame: initialFrame.frame }
      : null;
  isLaunching.value = true;
  errorMessage.value = "";
  launchNotice.value = "";
  replay.value = null;
  replayError.value = "";
  try {
    await saveCode();
    currentRun.value = await startSingleTaskRun({
      game_id: game.value.game_id,
      team_id: teamId.value,
      requested_by: sessionStore.nickname,
      repeat_run_id: repeatRunId,
      debug: debugEnabled.value,
    });
    reviewingRunCode.value = false;
    closeConditionPanel();
    startRunPolling(currentRun.value.run_id);
    await refreshStats();
  } catch (error) {
    await refreshStats();
    if (isRunActive.value) {
      launchNotice.value =
        "У вас уже есть активный запуск. Можно дождаться результата или остановить его кнопкой ■.";
    } else {
      errorMessage.value =
        error instanceof Error
          ? humanizeLaunchError(error.message)
          : "Не удалось запустить попытку";
    }
  } finally {
    isLaunching.value = false;
  }
}

async function stopRun(): Promise<void> {
  if (!game.value || !currentRun.value) return;
  isCancelling.value = true;
  launchNotice.value = "";
  try {
    currentRun.value = await stopSingleTaskRun({
      game_id: game.value.game_id,
      run_id: currentRun.value.run_id,
    });
    stopRunPolling();
    await loadReplay(currentRun.value.run_id);
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Не удалось остановить попытку";
  } finally {
    isCancelling.value = false;
  }
}

async function restartRun(): Promise<void> {
  if (!game.value || !currentRun.value || !isRunActive.value) return;
  isRestarting.value = true;
  errorMessage.value = "";
  launchNotice.value = "";
  replay.value = null;
  replayError.value = "";
  try {
    const activeRunId = currentRun.value.run_id;
    currentRun.value = await stopSingleTaskRun({
      game_id: game.value.game_id,
      run_id: activeRunId,
    });
    stopRunPolling();
    await refreshStats();
    currentRun.value = null;
    launchNotice.value = "Старый запуск отменен. Создаем новую попытку.";
    await launchRun();
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Не удалось перезапустить попытку";
  } finally {
    isRestarting.value = false;
  }
}

function startRunPolling(runId: string): void {
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
        currentRun.value = nextRun;
        sendRendererState();
      } while (pendingRunPoll);
      if (token !== runPollingToken) return;
      if (
        currentRun.value &&
        currentRun.value.run_id === runId &&
        !isRunActive.value
      ) {
        stopRunPolling();
        await loadReplay(runId);
        await refreshStats();
      }
    } catch {
      // keep latest state
    } finally {
      isPollingRun = false;
    }
  };
  void poll();
  pollingHandle = setInterval(() => {
    void poll();
  }, 1200);
}

function stopRunPolling(): void {
  runPollingToken += 1;
  pendingRunPoll = false;
  if (!pollingHandle) return;
  clearInterval(pollingHandle);
  pollingHandle = null;
}

async function loadReplay(runId: string): Promise<void> {
  if (
    currentRun.value?.run_id === runId &&
    currentRun.value.status !== "finished"
  ) {
    stopReplayPlayback();
    replay.value = null;
    replayError.value = "";
    return;
  }
  isReplayLoading.value = true;
  replayError.value = "";
  try {
    replay.value = await getRunReplay(runId);
    replayFrameIndex.value = 0;
    sendRendererState();
    if (replayFrames.value.length > 1) {
      startReplayPlayback();
    } else {
    }
  } catch (error) {
    replayError.value =
      error instanceof Error ? error.message : "Повтор пока недоступен";
  } finally {
    isReplayLoading.value = false;
  }
}

async function refreshStats(): Promise<void> {
  if (!game.value) return;
  isRefreshingStats.value = true;
  try {
    const freshAttempts = await listSingleTaskAttempts({
      game_id: game.value.game_id,
      requested_by: sessionStore.nickname,
      limit: 12,
    });
    attempts.value = freshAttempts;
    if (reviewingRunCode.value || typeof route.query.inspect_run === 'string') return;
    const currentRunId = currentRun.value?.run_id ?? "";
    const currentAttempt: RunDto | null = currentRunId
      ? (freshAttempts.find((attempt) => attempt.run_id === currentRunId) ??
        null)
      : null;
    const activeAttempt = freshAttempts.find(isActiveRun) ?? null;
    const latestCompletedAttempt =
      freshAttempts.find(
        (attempt) => !["created", "queued", "running"].includes(attempt.status),
      ) ?? null;
    if (currentAttempt) {
      const wasActive = isRunActive.value;
      currentRun.value = currentAttempt;
      if (
        wasActive &&
        !["created", "queued", "running"].includes(currentAttempt.status)
      ) {
        stopRunPolling();
        await loadReplay(currentAttempt.run_id);
      }
    }
    if (activeAttempt) {
      currentRun.value = activeAttempt;
      startRunPolling(activeAttempt.run_id);
      launchNotice.value =
        "Найден активный запуск. Можно дождаться результата или остановить его кнопкой ■.";
    } else if (!isRunActive.value && launchNotice.value.includes("актив")) {
      launchNotice.value = "";
    }
    if (!currentRun.value && latestCompletedAttempt) {
      currentRun.value = latestCompletedAttempt;
      if (replay.value?.run_id !== latestCompletedAttempt.run_id) {
        await loadReplay(latestCompletedAttempt.run_id);
      }
    }
    const repeatId = currentRun.value?.execution_options?.repeat_run_id;
    if (repeatId && previousRun.value?.run_id !== repeatId)
      previousRun.value = await getRun(repeatId, { compactPayload: true });
  } finally {
    isRefreshingStats.value = false;
  }
}

function sendToRenderer(message: Record<string, unknown>): void {
  const frame = rendererFrameRef.value;
  if (!frame?.contentWindow) return;
  frame.contentWindow.postMessage(sanitizeForPostMessage(message), "*");
}

function sendRendererInit(): void {
  if (!game.value) return;
  sendToRenderer({
    type: "agp.renderer.init",
    payload: {
      gameId: game.value.game_id,
      gameSlug: game.value.slug,
      mode: "single_task",
      runId: currentRun.value?.run_id ?? null,
    },
  });
  sendRendererState();
}

function sendRendererState(): void {
  const activeFrame = currentReplayFrame.value;
  const preview = repeatPreview.value ?? rendererPreview.value;
  sendToRenderer({
    type: "agp.renderer.state",
    payload: {
      motion: {
        duration_ms: replayIsPlaying.value
          ? Math.min(180, replayPlaybackDelayMs.value / 2)
          : 0,
      },
      tick: activeFrame?.tick ?? preview?.tick ?? 0,
      phase:
        activeFrame?.phase ??
        currentRun.value?.status ??
        preview?.phase ??
        "preview",
      frame: activeFrame?.frame ?? preview?.frame ?? {},
    },
  });
  const canSendTerminalResult =
    replayFrames.value.length === 0 ||
    replayFrameIndex.value >= replayFrames.value.length - 1;
  if (currentRun.value && !isRunActive.value && canSendTerminalResult) {
    sendToRenderer({
      type: "agp.renderer.result",
      payload: currentRun.value.result_payload ?? {
        status: currentRun.value.status,
      },
    });
  }
}

function toggleReplay(): void {
  if (replayIsPlaying.value) {
    stopReplayPlayback();
    return;
  }
  startReplayPlayback();
}

function stepReplay(direction: -1 | 1): void {
  if (replayFrames.value.length <= 1) return;
  stopReplayPlayback();
  const limit = replayFrames.value.length - 1;
  const nextIndex = replayFrameIndex.value + direction;
  replayFrameIndex.value = Math.min(limit, Math.max(0, nextIndex));
}

function startReplayPlayback(): void {
  clearReplayPlaybackTimer();
  if (replayFrames.value.length <= 1) return;
  if (replayFrameIndex.value >= replayFrames.value.length - 1) {
    replayFrameIndex.value = 0;
  }
  replayIsPlaying.value = true;
  replayPlaybackClock.start();
}

function clearReplayPlaybackTimer(): void {
  replayPlaybackClock.stop();
}

function stopReplayPlayback(options: { completed?: boolean } = {}): void {
  clearReplayPlaybackTimer();
  replayIsPlaying.value = false;
  if (options.completed) {
  }
}

function humanizeLaunchError(message: string): string {
  if (
    message.includes("409") &&
    message.includes("активный single_task запуск")
  ) {
    return "У вас уже есть активный запуск. Дождитесь результата или остановите его кнопкой ■.";
  }
  return message;
}

function attemptStatusLabel(status: RunDto["status"]): string {
  const labels: Record<RunDto["status"], string> = {
    created: "создано",
    queued: "в очереди",
    running: "выполняется",
    finished: "завершено",
    failed: "ошибка",
    timeout: "слишком долго",
    canceled: "остановлено",
  };
  return labels[status];
}

watch([editorCode, savedCode], () => {
  if (isBootstrapping.value || !selectedSlotKey.value) return;
  try {
    if (editorCode.value === savedCode.value)
      localStorage.removeItem(taskDraftKey());
    else
      localStorage.setItem(
        taskDraftKey(),
        JSON.stringify({
          code: editorCode.value,
          base: savedCode.value,
          savedAt: new Date().toISOString(),
        }),
      );
    draftStorageFailed.value = false;
    draftSavedAt.value = new Date().toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    draftStorageFailed.value = true;
  }
});

watch(replayFrameIndex, () => {
  sendRendererState();
});

watch(replayPlaybackDelayMs, (nextDelay) => {
  saveReplayDelay(nextDelay);
  if (replayIsPlaying.value) {
    startReplayPlayback();
  }
});

watch(splitRatio, (nextRatio) => {
  try {
    localStorage.setItem(
      SPLIT_RATIO_STORAGE_KEY,
      String(clampSplitRatio(nextRatio)),
    );
  } catch {
    // ignore storage failures; the ratio still works for this session
  }
});

watch(viewMode, (nextMode) => {
  try {
    localStorage.setItem(VIEW_MODE_STORAGE_KEY, nextMode);
  } catch {
    // ignore storage failures; selected mode still works for this session
  }
  if (nextMode === "code") {
    closeViewerFullscreen();
  }
});

onMounted(async () => {
  window.addEventListener("keydown", handlePageKeydown);
  window.addEventListener("message", onRendererMessage);
  window.addEventListener("pointermove", handleSplitPointerMove);
  window.addEventListener("pointerup", stopSplitResize);
  window.addEventListener("pointercancel", stopSplitResize);
  mobileMedia.addEventListener("change", updateMobileMode);
  updateHeaderCondensed();
  await loadPage();
});

onUnmounted(() => {
  inspectionToken += 1;
  clearInterval(statusTimer);
  mobileMedia.removeEventListener("change", updateMobileMode);
  window.removeEventListener("keydown", handlePageKeydown);
  window.removeEventListener("message", onRendererMessage);
  window.removeEventListener("pointermove", handleSplitPointerMove);
  window.removeEventListener("pointerup", stopSplitResize);
  window.removeEventListener("pointercancel", stopSplitResize);
  stopRunPolling();
  stopReplayPlayback();
  stopSplitResize();
  closeViewerFullscreen();
  closeSidePanels();
});
</script>

<style scoped>
.arena-workspace {
  height: calc(100dvh - 24px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}
.arena-workbar {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
}
.arena-workbar h1 {
  font-size: 16px;
  line-height: 24px;
  margin: 0;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.arena-save-time {
  font-size: 11px;
  color: var(--agp-text-muted);
  margin-left: auto;
}
.arena-workpanes {
  display: grid;
  min-height: 0;
  flex: 1;
}
.arena-code-pane,
.arena-field-pane {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.arena-pane-head {
  min-height: 44px;
  padding: 6px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--agp-border);
  font-size: 12px;
}
.arena-pane-head strong {
  font-weight: 500;
}
.arena-pane-head > :last-child {
  margin-left: auto;
}
.arena-code-pane > .agp-code-editor {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.arena-code-pane :deep(.cm-editor) {
  height: 100%;
  min-height: 0 !important;
  border: 0 !important;
  border-radius: 0 !important;
}
.arena-code-pane :deep(.cm-scroller) {
  overflow: auto;
}
.arena-field-canvas {
  position: relative;
  min-height: 80px;
  flex: 1;
  overflow: hidden;
}
.arena-field-canvas iframe {
  display: block;
  border: 0;
  width: 100%;
  height: 100%;
}
.arena-field-loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  margin: 0;
  padding: 16px;
  background: var(--agp-surface);
  text-align: center;
}
.arena-field-pane > .arena-diagnostic {
  margin: 8px 8px 0;
  max-height: 30%;
  overflow: auto;
}
.arena-field-pane > .agp-game-reference {
  height: 100%;
  overflow: auto;
}
.arena-file-menu {
  position: relative;
}
.arena-file-menu summary {
  cursor: pointer;
  list-style: none;
  font-size: 22px;
  padding: 0 8px;
}
.arena-file-menu > div {
  position: absolute;
  right: 0;
  top: 100%;
  width: 220px;
  background: var(--agp-surface);
  border: 1px solid var(--agp-border);
  border-radius: 8px;
  padding: 8px;
  z-index: 30;
  box-shadow: 0 8px 24px #0002;
  display: grid;
  gap: 4px;
}
.arena-file-menu button,
.arena-file-menu label {
  font-size: 13px;
  text-align: left;
  background: none;
  color: var(--agp-text);
  border: 0;
  padding: 8px;
  display: flex;
  gap: 8px;
}
.arena-file-menu button:hover {
  background: var(--agp-surface-soft);
}
.arena-mobile-panes {
  display: none;
}
.arena-workpanes--resizing iframe {
  pointer-events: none;
}
@media (max-width: 900px) {
  .arena-workspace {
    height: calc(100dvh - 16px);
  }
  .arena-workbar {
    flex-wrap: wrap;
  }
  .arena-workbar h1 {
    flex: 1;
  }
  .arena-save-time {
    display: none;
  }
  .arena-workbar > .arena-loading {
    display: none;
  }
  .arena-workbar .btn {
    padding: 5px 10px;
  }
  .arena-mobile-panes {
    display: flex;
    gap: 8px;
  }
  .arena-mobile-panes button {
    flex: 1;
    min-height: 44px;
    border: 1px solid var(--agp-border);
    background: var(--agp-surface);
    color: var(--agp-text);
    border-radius: 6px;
  }
  .arena-mobile-panes button[aria-pressed="true"] {
    background: var(--agp-primary-soft);
    color: var(--agp-primary);
  }
  .arena-field-pane {
    display: none;
  }
  .arena-workspace--field .arena-code-pane {
    display: none;
  }
  .arena-workspace--field .arena-field-pane {
    display: flex;
  }
}

.arena-review-navigation { display: flex; align-items: center; gap: 8px; }
.arena-review-code-meta { display: flex; gap: 8px; font-size: 11px; color: var(--agp-text-muted); white-space: nowrap; margin-left: auto; }
.arena-review-action-compact { display: none; }
.arena-review-file-error { display: inline-grid; place-items: center; width: 18px; height: 18px; margin-left: 8px; border-radius: 4px; color: var(--agp-danger); background: var(--arena-error-soft); font-weight: 600; }
.arena-review-outcome--error { color: var(--agp-danger); }
.arena-review-outcome--success { color: var(--agp-success); }
.arena-review-error-details { margin: 0; white-space: pre-wrap; color: var(--agp-danger); font: inherit; }
.arena-workspace--fullscreen .arena-field-pane { display: flex; position: fixed; inset: 8px; z-index: 150; height: auto; }
@media (max-width: 900px) { .arena-review-navigation span { display: none; } .arena-review-code-meta { flex-direction: column; align-items: flex-end; gap: 0; font-size: 10px; line-height: 14px; } .arena-review-action-wide { display: none; } .arena-review-action-compact { display: inline; } }
</style>
