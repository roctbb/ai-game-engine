<template>
  <section class="agp-grid agp-task-workspace" :class="`agp-task-workspace--mobile-${mobilePanel}`">
    <header class="agp-task-header" :class="{ 'agp-task-header--condensed': isHeaderCondensed }">
      <div class="agp-task-header-main">
        <RouterLink :to="taskBackTarget" class="agp-back-link" title="К задачам" aria-label="К задачам"><AppIcon name="back" /></RouterLink>
        <h1>{{ game?.title || 'Задача' }}</h1>
      </div>
      <div class="agp-task-reference-actions"><button class="agp-panel-toggle" :class="{ 'agp-panel-toggle--active': conditionPanelOpen }" :aria-pressed="conditionPanelOpen" @click="toggleConditionPanel">Условие и API</button><button class="agp-panel-toggle" :aria-pressed="competitionPanelOpen" @click="toggleCompetitionPanel">{{ competitionButtonLabel }}</button></div>
      <div class="agp-task-header-actions">
        <div class="agp-view-mode-toggle" role="group" aria-label="Режим экрана">
          <button
            class="agp-icon-button agp-icon-button--ghost"
            :class="{ 'agp-icon-button--active': viewMode === 'viewer' }"
            :aria-pressed="viewMode === 'viewer'"
            title="Только просмотр (1)"
            aria-label="Только просмотр"
            @click="setViewMode('viewer')"
          >
            <AppIcon name="viewer" /><span>Игра</span>
          </button>
          <button
            class="agp-icon-button agp-icon-button--ghost"
            :class="{ 'agp-icon-button--active': viewMode === 'split' }"
            :aria-pressed="viewMode === 'split'"
            title="Две колонки (2)"
            aria-label="Две колонки"
            @click="setViewMode('split')"
          >
            <AppIcon name="split" /><span>Вместе</span>
          </button>
          <button
            class="agp-icon-button agp-icon-button--ghost"
            :class="{ 'agp-icon-button--active': viewMode === 'code' }"
            :aria-pressed="viewMode === 'code'"
            title="Только код (3)"
            aria-label="Только код"
            @click="setViewMode('code')"
          >
            <AppIcon name="code" /><span>Код</span>
          </button>
        </div>
        <div class="agp-run-status">
          <span class="agp-run-state-badge" :class="`agp-run-state-badge--${runStatusTone}`"></span>
          <span class="small text-muted">Запуск</span>
          <strong>{{ runStatusLabel }}</strong>
        </div>
        <div class="agp-launch-hint">
          {{ launchHint }}
        </div>
        <div class="agp-run-action-cluster" :class="{ 'agp-run-action-cluster--active': isRunActive }">
          <button
            class="agp-launch-button"
            :disabled="isRunActive || !canLaunch || isLaunching || isRestarting || isSaving"
            title="Запустить код (⌘/Ctrl+Enter)"
            aria-label="Запустить код"
            @click="launchRun()"
          >
            <AppIcon name="play" /> <span>{{ isLaunching || isSaving ? 'Запускаем…' : 'Запустить' }}</span>
          </button>
          <button
            v-if="isRunActive"
            class="agp-icon-button agp-icon-button--stop"
            :disabled="!isRunActive || !canStop || isCancelling || isRestarting"
            title="Остановить запуск"
            aria-label="Остановить запуск"
            @click="stopRun"
          >
            <AppIcon name="stop" />
          </button>
          <button
            v-if="isRunActive"
            class="agp-icon-button agp-icon-button--restart"
            :disabled="!isRunActive || !canRestart || isRestarting || isCancelling"
            title="Перезапустить зависший запуск"
            aria-label="Перезапустить запуск"
            @click="restartRun"
          >
            <AppIcon name="refresh" />
          </button>
        </div>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <LoadingSkeleton v-if="isBootstrapping" :count="2" layout="workspace" label="Готовим рабочее место…" />

    <transition name="agp-victory-pop">
      <div v-if="victoryCelebrationVisible" class="agp-victory-celebration" aria-live="polite">
        <div class="agp-victory-card">
          <AppIcon name="check" />
          <strong>Задача решена!</strong>
          <small>Результат сохранён</small>
        </div>
      </div>
    </transition>

    <nav v-if="game && !isBootstrapping" class="agp-workspace-tabs" aria-label="Рабочая панель">
      <button v-for="tab in mobilePanels" :key="tab.id" type="button" :class="{ active: mobilePanel === tab.id }" :aria-pressed="mobilePanel === tab.id" @click="mobilePanel = tab.id"><AppIcon :name="tab.icon" />{{ tab.label }}</button>
    </nav>

    <RunOutcome v-if="currentRun && !isRunActive && !isBootstrapping" :run="currentRun" :replay="replay" :revision="runRevision" :best-score="myLeaderboardEntry?.best_score" :previous="previousRun ?? attempts.find(a => a.run_id === currentRun?.execution_options?.repeat_run_id) ?? null" @problem="seekProblem">
      <button class="agp-panel-toggle" :disabled="!canLaunch" @click="launchRun(currentRun?.run_id)">Повторить это поле</button>
      <RouterLink v-if="isSolvedRun(currentRun) && nextTask" :to="{ name: 'task-run', params: { gameId: nextTask.game_id }, query: { from: taskBackTarget } }" class="agp-next-task">Следующая задача <AppIcon name="next" /></RouterLink>
    </RunOutcome>
    <template v-if="game && !isBootstrapping">
      <button
        v-if="isViewerFullscreen"
        type="button"
        class="agp-fullscreen-backdrop"
        aria-label="Свернуть полноэкранный просмотр"
        @click="closeViewerFullscreen"
      ></button>

      <div
        ref="mainColumnsRef"
        class="agp-main-columns"
        :class="{
          'agp-main-columns--resizing': isSplitResizing,
          'agp-main-columns--viewer-only': viewMode === 'viewer',
          'agp-main-columns--code-only': viewMode === 'code',
          [`agp-main-columns--mobile-${mobilePanel}`]: true,
        }"
        :style="mainColumnsStyle"
      >
        <article
          v-show="viewMode !== 'code' || isMobile"
          :class="['agp-card p-3 agp-viewer-card', { 'agp-viewer-card--fullscreen': isViewerFullscreen }]"
        >
          <GameReference v-if="conditionPanelOpen" :title="game.title" :description="game.description" :instruction="docs?.player_instruction" :template="selectedTemplateCode" :docs="docs" :frame="referenceFrame" :arguments="currentDebugArguments" :is-actual="!!currentReplayFrame" @close="closeConditionPanel" />
          <div v-if="!conditionPanelOpen && !replayFrames.length" class="agp-viewer-overlay agp-viewer-overlay--status">{{ isRunActive ? repeatPreview ? 'То же поле · рассчитываем запуск' : 'Пример поля · рассчитываем запуск' : 'Пример поля · запустите стратегию' }}</div>
          <button
            type="button"
            v-show="!conditionPanelOpen" class="agp-viewer-overlay agp-viewer-fullscreen"
            :title="isViewerFullscreen ? 'Свернуть' : 'Во весь экран'"
            :aria-label="isViewerFullscreen ? 'Свернуть' : 'Во весь экран'"
            @click.stop="isViewerFullscreen ? closeViewerFullscreen() : openViewerFullscreen()"
          >
            <AppIcon :name="isViewerFullscreen ? 'restore' : 'expand'" />
          </button>
          <div v-if="rendererUrl" v-show="!conditionPanelOpen" class="agp-viewer-frame">
            <iframe
              ref="rendererFrameRef"
              :key="rendererKey"
              :src="rendererUrl"
              title="Визуализация задачи"
              sandbox="allow-scripts"
              @load="sendRendererInit"
            ></iframe>
          </div>
          <div v-else class="agp-card-soft p-3 small text-muted">
            У этой задачи нет отдельной визуализации.
          </div>
          <div v-if="isReplayLoading" class="agp-viewer-overlay agp-viewer-overlay--message">Загружаем повтор...</div>
          <div v-else-if="replayError" class="agp-viewer-overlay agp-viewer-overlay--message agp-viewer-overlay--danger">{{ replayError }}</div>
          <ReplayControls v-if="replayFrames.length && !conditionPanelOpen" v-model:frame-index="replayFrameIndex" v-model:delay="replayPlaybackDelayMs" :frame-count="replayFrames.length" :playing="replayIsPlaying" :can-play="replayFrames.length > 1" :can-step-backward="replayFrameIndex > 0" :can-step-forward="replayFrameIndex < replayFrames.length - 1" :markers="moments" @toggle="toggleReplay" @step="stepReplay" />
          <details v-if="replayFrames.length && !conditionPanelOpen" class="agp-analysis-disclosure" :open="analysisOpen || (isMobile && mobilePanel === 'analysis')" @toggle="analysisOpen = ($event.target as HTMLDetailsElement).open"><summary>Разбор хода · события и переменные</summary><ReplayInsights @pause="stopReplayPlayback()" :frames="replay?.frames ?? []" :events="replay?.events ?? []" :frame-index="replayFrameIndex" @seek="seekReplay" @line="inspectRunLine" /></details>
          <BotConsole initially-collapsed :reveal="currentConsoleLines.some(l => l.tone === 'error')" v-show="!conditionPanelOpen" :expanded="isMobile && mobilePanel === 'console'" :position="replayFrames.length ? `${replayFrameIndex + 1} / ${replayFrames.length}` : ''">
              <div v-if="currentConsoleLines.length === 0" class="agp-bot-console-empty">
                print и ошибки появятся здесь
              </div>
              <div
                v-for="line in currentConsoleLines"
                :key="line.id"
                class="agp-bot-console-line"
                :class="{ 'agp-bot-console-line--error': line.tone === 'error' }"
              >
                <span v-if="line.role" class="agp-bot-console-role">{{ line.role }}</span>
                <span class="mono agp-bot-console-message">{{ line.message }}</span><button v-if="line.line" class="agp-error-line" @click="inspectRunLine({ line: line.line, role: line.role })">Строка {{ line.line }}</button>
              </div>
          </BotConsole>
        </article>
        <button
          v-show="viewMode === 'split'"
          type="button"
          class="agp-main-splitter"
          role="separator"
          aria-orientation="vertical"
          :aria-valuenow="splitRatio"
          aria-valuemin="32"
          aria-valuemax="70"
          title="Перетащите, чтобы изменить ширину колонок"
          aria-label="Изменить ширину колонок"
          @pointerdown="startSplitResize"
          @keydown.left.prevent="splitRatio = clampSplitRatio(splitRatio - 2)"
          @keydown.right.prevent="splitRatio = clampSplitRatio(splitRatio + 2)"
        ></button>

        <article v-show="viewMode !== 'viewer' || isMobile" class="agp-card p-3 agp-code-card">
          <div class="agp-code-toolbar">
            <span class="agp-code-state" role="status">{{ reviewingRunCode ? `Код запуска v${reviewRevision}` : draftStateLabel }}</span>
            <button v-if="reviewingRunCode" class="agp-panel-toggle" @click="reviewingRunCode = false">К черновику</button>
            <button v-else-if="currentRun?.snapshot_id" class="agp-panel-toggle" @click="inspectRunLine({ line: 1 })">Код запуска v{{ runRevision }}</button>
            <template v-if="!reviewingRunCode">
              <button v-if="replacementUndo !== null" class="agp-panel-toggle" @click="undoReplacement">Отменить замену</button>
              <button class="agp-panel-toggle" :disabled="!selectedSlotKey || isSaving" @click="applyTemplate">Шаблон</button>
              <button v-if="canUseDemoStrategy" class="agp-panel-toggle" :disabled="!firstDemoCode || isSaving" @click="applyDemo">Пример</button>
              <button v-if="isDirty || isSaving" class="agp-panel-toggle" :disabled="!isDirty || isSaving" @click="saveCode">Сохранить</button>
            </template>
          </div>
          <div v-if="!reviewingRunCode" class="agp-code-options"><label><input v-model="debugEnabled" type="checkbox" /> Записать отладку</label><span v-if="isRunActive">Выполняется v{{ runRevision }} · можно готовить следующий черновик</span><span v-else>⌘/Ctrl+Enter — запуск</span></div>
          <CodeEditor v-if="reviewingRunCode" :model-value="reviewCode" readonly :focus-line="reviewLine" language="python" />
          <CodeEditor v-show="!reviewingRunCode" ref="codeEditorRef" v-model="editorCode" :readonly="!selectedSlotKey || isSaving" language="python" @run="launchRun()" />
        </article>
      </div>
    </template>

    <transition name="agp-drawer-fade">
      <button
        v-if="competitionPanelOpen"
        type="button"
        class="agp-drawer-backdrop"
        aria-label="Закрыть выезжаемую панель"
        @click="closeSidePanels"
      ></button>
    </transition>

    <transition name="agp-drawer-slide">
      <aside v-if="competitionPanelOpen" class="agp-competition-drawer" v-dialog-focus="closeCompetitionPanel" role="dialog" aria-label="Результаты и попытки">
        <header class="agp-cockpit-panel-head">
          <div>
            <h2 class="h6 mb-0">Результаты и попытки</h2>
            <div class="small">
              {{ isRefreshingStats ? 'Обновляем данные...' : 'Сравнение результатов и прошлые попытки' }}
            </div>
          </div>
          <button type="button" class="agp-cockpit-close" aria-label="Закрыть лидерборд" @click="closeCompetitionPanel">×</button>
        </header>

        <article class="agp-cockpit-panel-section agp-launch-panel">
          <div class="agp-cockpit-muted">{{ runSummary }}</div>
          <div class="agp-score-grid mt-2">
            <div class="agp-cockpit-stat">
              <div>Решение</div>
              <div class="fw-semibold">{{ solvedLabel }}</div>
            </div>
            <div class="agp-cockpit-stat">
              <div>Счет</div>
              <div class="mono">{{ currentScore ?? myLeaderboardEntry?.best_score ?? '—' }}</div>
            </div>
            <div class="agp-cockpit-stat">
              <div>Место</div>
              <div class="mono">{{ myLeaderboardEntry?.place ?? '—' }}</div>
            </div>
          </div>
          <div v-if="currentRun" class="agp-cockpit-callout mt-3">
            <div class="d-flex justify-content-between gap-2 flex-wrap">
              <span class="small">Последний запуск: <strong>{{ runStatusLabel }}</strong></span>
              <RouterLink class="small" :to="`/runs/${currentRun.run_id}/watch`">Смотреть подробно</RouterLink>
            </div>
            <div v-if="friendlyRunProblem" class="small text-danger mt-2">{{ friendlyRunProblem }}</div>
          </div>
        </article>

        <article class="agp-cockpit-panel-section">
          <h3 class="h6 mb-2">Лидерборд</h3>
          <div v-if="leaderboard?.entries.length" class="d-flex flex-column gap-2">
            <div
              v-for="entry in leaderboard.entries.slice(0, 8)"
              :key="`${entry.user_id}-${entry.place}`"
              class="agp-cockpit-row d-flex justify-content-between align-items-center gap-2"
            >
              <span class="mono small">#{{ entry.place }} {{ entry.user_id }}</span>
              <span class="d-flex align-items-center gap-2">
                <span class="mono small">{{ entry.best_score ?? (entry.solved ? 'решено' : '—') }}</span>
                <RouterLink
                  v-if="canInspectLeaderboardCode && teamIdForLeaderboardEntry(entry)"
                  class="small"
                  :to="`/players/${teamIdForLeaderboardEntry(entry)}/code`"
                >
                  Код
                </RouterLink>
              </span>
            </div>
          </div>
          <div v-else class="small text-muted">Лидерборд пока пуст.</div>
        </article>

        <article class="agp-cockpit-panel-section">
          <h3 class="h6 mb-2">Прошлые попытки</h3>
          <div class="agp-grid">
            <div
              v-for="attempt in attempts.slice(0, 10)"
              :key="attempt.run_id"
              class="agp-cockpit-row d-flex justify-content-between gap-2 align-items-center"
            >
              <div>
                <div class="small fw-semibold">{{ attemptStatusLabel(attempt.status) }}</div>
                <div class="small text-muted">счет {{ attemptScore(attempt) }}</div>
              </div>
              <RouterLink class="small" :to="`/runs/${attempt.run_id}/watch`">Открыть</RouterLink>
            </div>
            <div v-if="attempts.length === 0" class="small text-muted">Попыток пока нет.</div>
          </div>
        </article>
      </aside>
    </transition>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import CodeEditor from '../components/CodeEditor.vue';
import GameReference from '../components/GameReference.vue';
import ReplayInsights from '../components/ReplayInsights.vue';
import RunOutcome from '../components/RunOutcome.vue';
import { record, replayMoments } from '../lib/replayInsights';
import AppIcon from '../components/AppIcon.vue';
import BotConsole from '../components/BotConsole.vue';
import ReplayControls from '../components/ReplayControls.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import { createReplayClock, loadReplayDelay, saveReplayDelay } from '../lib/replayPlayback';
import { isShortcutInput } from '../lib/keyboard';
import { difficultyOrder, sectionOrder } from '../lib/taskCatalog';
import {
  createTeam,
  getGame,
  getGameDocs,
  getGameTemplates,
  getRendererPreview,
  getRun,
  getRunReplay,
  getRunCode,
  getSingleTaskLeaderboard,
  getWorkspace,
  listSingleTaskAttempts,
  listSingleTaskCatalog,
  type SingleTaskCatalogItemDto,
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
  type SingleTaskLeaderboardEntryDto,
  type SingleTaskLeaderboardDto,
  type TeamDto,
  type TeamWorkspaceDto,
} from '../lib/api';
import { sanitizeForPostMessage } from '../lib/postMessage';
import { loadTeamMapping, saveTeamMapping } from '../lib/teamMapping';
import { useSessionStore } from '../stores/session';

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
  tone?: 'error';
  line?: number;
}
type WorkspaceViewMode = 'viewer' | 'split' | 'code';

const route = useRoute();
const sessionStore = useSessionStore();
const SPLIT_RATIO_STORAGE_KEY = 'agp_task_workspace_split_ratio';
const VIEW_MODE_STORAGE_KEY = 'agp_task_workspace_view_mode';

const catalogTasks = ref<SingleTaskCatalogItemDto[]>([]);
const game = ref<GameDto | null>(null);
const taskBackTarget = computed(() => {
  const from = route.query.from;
  if (typeof from === 'string' && from.startsWith('/tasks/sections/')) return from;
  return game.value?.learning_section ? `/tasks/sections/${encodeURIComponent(game.value.learning_section)}` : '/tasks';
});
const nextTask = computed(() => {
  const ordered = [...catalogTasks.value].sort((a, b) => sectionOrder(a.learning_section || '') - sectionOrder(b.learning_section || '') || difficultyOrder(a.difficulty || '') - difficultyOrder(b.difficulty || '') || a.title.localeCompare(b.title, 'ru'));
  const index = ordered.findIndex(task => task.game_id === game.value?.game_id);
  return index >= 0 ? ordered[index + 1] ?? null : null;
});
const templates = ref<GameTemplatesDto | null>(null);
const docs = ref<GameDocumentationDto | null>(null);
const workspace = ref<TeamWorkspaceDto | null>(null);
const teamsByGame = ref<TeamDto[]>([]);
const teamId = ref('');
const selectedSlotKey = ref('');
const editorCode = ref('');
const savedCode = ref('');
const currentRun = ref<RunDto | null>(null);
const replay = ref<ReplayDto | null>(null);
const rendererPreview = ref<RendererPreviewDto | null>(null);
const repeatPreview = ref<RendererPreviewDto | null>(null);
const leaderboard = ref<SingleTaskLeaderboardDto | null>(null);
const attempts = ref<RunDto[]>([]);
const competitionPanelOpen = ref(false);
const conditionPanelOpen = ref(false);
const debugEnabled = ref(false);
const previousRun = ref<RunDto | null>(null);
const analysisOpen = ref(false);
const replacementUndo = ref<string | null>(null);
const draftSavedAt = ref('');
const draftStorageFailed = ref(false);
const reviewingRunCode = ref(false);
const reviewCode = ref('');
const reviewLine = ref(1);
const reviewRevision = ref(0);
const runRevision = computed(() => currentRun.value?.revisions_by_slot[selectedSlotKey.value] ?? 0);
const draftStateLabel = computed(() => {
  if (isSaving.value) return 'Сохраняем…';
  if (!savedCode.value && editorCode.value === selectedTemplateCode.value) return 'Стартовый шаблон';
  if (!isDirty.value) return `Сохранено на сервере · v${workspace.value?.slot_states.find(s => s.slot_key === selectedSlotKey.value)?.revision ?? '—'}`;
  if (draftStorageFailed.value) return 'Черновик не сохранён на устройстве';
  return draftSavedAt.value ? `Черновик на устройстве · ${draftSavedAt.value}` : 'Черновик';
});
const moments = computed(() => replayMoments(replay.value?.events ?? [], replay.value?.frames ?? []));
const referenceFrame = computed(() => currentReplayFrame.value?.frame ?? repeatPreview.value?.frame ?? rendererPreview.value?.frame ?? {});
const currentDebugArguments = computed(() => replay.value?.events.find(e => e.type === 'debug_snapshot' && e.tick === currentReplayFrame.value?.tick)?.arguments);

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
const statusTimer = setInterval(() => { if (isRunActive.value) statusNow.value = Date.now(); }, 1000);
const victoryCelebrationVisible = ref(false);
const errorMessage = ref('');
const replayError = ref('');
const launchNotice = ref('');
const rendererFrameRef = ref<HTMLIFrameElement | null>(null);
const mainColumnsRef = ref<HTMLElement | null>(null);
const rendererKey = ref(0);
const splitRatio = ref(loadSplitRatio());
const isSplitResizing = ref(false);
const viewMode = ref<WorkspaceViewMode>(loadViewMode());
const isHeaderCondensed = ref(false);
let pollingHandle: ReturnType<typeof setInterval> | null = null;
const replayPlaybackClock = createReplayClock(() => {
  const last = replayFrames.value.length - 1;
  if (replayFrameIndex.value < last) replayFrameIndex.value += 1;
  if (replayFrameIndex.value >= last) stopReplayPlayback({ completed: true });
}, () => replayPlaybackDelayMs.value);
const isMobile = ref(window.matchMedia('(max-width: 900px)').matches);
const mobilePanel = ref<'code' | 'viewer' | 'console' | 'analysis' | 'reference'>('code');
const mobilePanels = [
  { id: 'code' as const, label: 'Код', icon: 'code' },
  { id: 'viewer' as const, label: 'Игра', icon: 'viewer' },
  { id: 'console' as const, label: 'Консоль', icon: 'console' },
  { id: 'analysis' as const, label: 'Разбор', icon: 'history' },
  { id: 'reference' as const, label: 'Задание', icon: 'tasks' },
];
const mobileMedia = window.matchMedia('(max-width: 900px)');
watch(mobilePanel, panel => { conditionPanelOpen.value = panel === 'reference'; });
function updateMobileMode(): void { isMobile.value = mobileMedia.matches; }
let victoryCelebrationHandle: ReturnType<typeof setTimeout> | null = null;
let isPollingRun = false;
let pendingRunPoll = false;
let runPollingToken = 0;
const celebratedRunIds = new Set<string>();

const rendererUrl = computed(() => (game.value ? `/api/v1/renderers/${game.value.slug}/renderer/index.html` : ''));
const selectedTemplateCode = computed(
  () => templates.value?.templates.find((item) => item.slot_key === selectedSlotKey.value)?.code ?? ''
);
const firstDemoCode = computed(
  () => templates.value?.demo_strategies.find((item) => item.slot_key === selectedSlotKey.value)?.code ?? ''
);
const isDirty = computed(() => editorCode.value !== savedCode.value);
const isRunActive = computed(() =>
  currentRun.value ? ['created', 'queued', 'running'].includes(currentRun.value.status) : false
);
const canLaunch = computed(
  () =>
    Boolean(game.value && teamId.value && selectedSlotKey.value && editorCode.value.trim()) &&
    !isLaunching.value &&
    !isRestarting.value &&
    !isRunActive.value
);
const canStop = computed(() => Boolean(game.value && currentRun.value && isRunActive.value) && !isCancelling.value && !isRestarting.value);
const canRestart = computed(
  () =>
    Boolean(game.value && currentRun.value && isRunActive.value && selectedSlotKey.value && editorCode.value.trim()) &&
    !isCancelling.value &&
    !isLaunching.value &&
    !isRestarting.value
);
const runSummary = computed(() => {
  if (launchNotice.value) return launchNotice.value;
  if (isRestarting.value) return 'Отменяем старый запуск и ставим новый в очередь.';
  if (isLaunching.value) return 'Сохраняем код и ставим запуск в очередь.';
  if (isCancelling.value) return 'Останавливаем текущий запуск.';
  if (!currentRun.value) return `${draftStateLabel.value}. При запуске код сохранится на сервере.`;
  if (isRunActive.value) return `Выполняется код v${runRevision.value}. Изменения черновика попадут в следующую попытку.`;
  return 'Последняя попытка завершена.';
});
const launchHint = computed(() => {
  if (isRestarting.value) return 'Перезапускаем попытку';
  if (isLaunching.value) return 'Сохраняем и запускаем';
  if (isCancelling.value) return 'Останавливаем запуск';
  if (isRunActive.value) return 'Готовьте следующий черновик, пока идёт запуск';
  if (!selectedSlotKey.value) return 'Роль для кода еще не выбрана';
  if (!editorCode.value.trim()) return 'Добавьте код, чтобы запустить';
  if (isDirty.value) return 'При запуске изменения сохранятся';
  if (currentRun.value && !isRunActive.value) return 'Можно запустить новую попытку';
  return 'Готово к запуску';
});
const replayFrames = computed<ReplayFrameView[]>(() =>
  (replay.value?.frames ?? []).map((item, index) => {
    const tick = typeof item.tick === 'number' ? item.tick : index;
    const phase = typeof item.phase === 'string' ? item.phase : replay.value?.status ?? 'unknown';
    const frame = isRecord(item.frame) ? item.frame : {};
    return { tick, phase, frame };
  })
);
const currentReplayFrame = computed(() => replayFrames.value[replayFrameIndex.value] ?? null);
const botConsoleLines = computed<BotConsoleLine[]>(() => {
  const lines: BotConsoleLine[] = [];
  const replayEvents = replay.value?.events ?? [];
  replayEvents.forEach((event, index) => appendConsoleLine(lines, event, `event-${index}`));
  (replay.value?.frames ?? []).forEach((frame, index) => {
    if (!isRecord(frame)) return;
    const tick = normalizeTick(frame.tick, index);
    const framePayload = isRecord(frame.frame) ? frame.frame : frame;
    appendConsoleCollection(lines, framePayload.prints, tick, '', `frame-${index}-prints`);
    appendConsoleCollection(lines, framePayload.logs, tick, '', `frame-${index}-logs`);
    appendConsoleCollection(lines, framePayload.console, tick, '', `frame-${index}-console`);
    appendConsoleCollection(lines, framePayload.stdout, tick, '', `frame-${index}-stdout`);
  });
  if (replayEvents.length === 0 && currentRun.value?.result_payload) {
    appendConsoleCollection(lines, currentRun.value.result_payload.prints, 0, '', 'result-prints');
    appendConsoleCollection(lines, currentRun.value.result_payload.logs, 0, '', 'result-logs');
    appendConsoleCollection(lines, currentRun.value.result_payload.stdout, 0, '', 'result-stdout');
  }
  appendRunDiagnosticLines(lines, currentRun.value, replay.value);
  return lines.sort((left, right) => left.tick - right.tick || left.id.localeCompare(right.id));
});
const currentConsoleLines = computed(() => {
  if (replayFrames.value.length === 0) return botConsoleLines.value;
  const tick = currentReplayFrame.value?.tick ?? 0;
  return botConsoleLines.value.filter((line) => line.tick <= tick);
});
const currentScore = computed(() => attemptScoreValue(currentRun.value));
const myLeaderboardEntry = computed(() =>
  leaderboard.value?.entries.find((entry) => entry.user_id === sessionStore.nickname) ?? null
);
const canInspectLeaderboardCode = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const canUseDemoStrategy = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const competitionButtonLabel = computed(() => {
  const place = myLeaderboardEntry.value?.place;
  if (canInspectLeaderboardCode.value) return 'Решения и попытки';
  return typeof place === 'number' ? `Результат #${place}` : 'Результаты';
});
const mainColumnsStyle = computed(() => ({
  '--agp-viewer-col': `${splitRatio.value}fr`,
  '--agp-code-col': `${100 - splitRatio.value}fr`,
}));
const sidePanelOpen = computed(() => competitionPanelOpen.value);
const hasBotError = computed(() => {
  const metrics = record(currentRun.value?.result_payload?.metrics ?? (replay.value?.run_id === currentRun.value?.run_id ? replay.value?.summary.metrics : undefined));
  return Number(metrics.bot_errors) > 0 || Boolean(metrics.compile_error);
});
const runStatusLabel = computed(() => {
  if (hasBotError.value) return 'Ошибка в коде';
  if (!currentRun.value) return 'Готов к запуску';
  const label = attemptStatusLabel(currentRun.value.status);
  if (!isRunActive.value) return label;
  const started = Date.parse(currentRun.value.started_at || currentRun.value.queued_at || currentRun.value.created_at);
  const seconds = Math.max(0, Math.floor((statusNow.value - started) / 1000));
  return `${label} · ${seconds} с`;
});
const runStatusTone = computed<'idle' | 'active' | 'success' | 'danger'>(() => {
  if (!currentRun.value) return 'idle';
  if (['created', 'queued', 'running'].includes(currentRun.value.status)) return 'active';
  if (hasBotError.value) return 'danger';
  if (currentRun.value.status === 'finished') return 'success';
  if (['failed', 'timeout', 'canceled'].includes(currentRun.value.status)) return 'danger';
  return 'idle';
});
const solvedLabel = computed(() => (myLeaderboardEntry.value?.solved ? 'решено' : 'еще нет'));
const codeStateLabel = computed(() => {
  if (!selectedSlotKey.value) return 'Сейчас подготовим файл для решения';
  if (isRunActive.value) return `Выполняется v${runRevision.value}. Черновик можно редактировать.`;
  if (isDirty.value) return 'Есть изменения, при запуске они сохранятся';
  return 'Код сохранен';
});
const friendlyRunProblem = computed(() => {
  if (!currentRun.value) return '';
  if (currentRun.value.status === 'failed') return currentRun.value.error_message || 'Код не запустился. Детали можно посмотреть в подробном просмотре.';
  if (currentRun.value.status === 'timeout') return 'Решение работало слишком долго и было остановлено.';
  if (currentRun.value.status === 'canceled') return 'Запуск остановлен.';
  return '';
});

function gameIdFromRoute(): string {
  return String(route.params.gameId || '').trim();
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
    type === 'compile_error' ||
    type === 'runtime_error' ||
    type === 'bot_error' ||
    type === 'run_error' ||
    type === 'timeout' ||
    'stdout' in raw;
  if (!hasConsoleShape) return;

  const messageRaw = raw.message ?? raw.text ?? raw.line ?? raw.stdout ?? raw.value;
  const message = typeof messageRaw === 'string' ? messageRaw : String(messageRaw ?? '');
  if (!message) return;
  const tick = normalizeTick(raw.tick ?? raw.turn ?? raw.step ?? raw.frame, fallbackTick);
  const roleRaw = raw.role ?? raw.slot ?? raw.slot_key ?? raw.team_id ?? raw.bot;
  const role = typeof roleRaw === 'string' || typeof roleRaw === 'number' ? String(roleRaw) : diagnosticRoleForEvent(type);
  appendConsoleMessage(lines, message, tick, role, id, isDiagnosticConsoleEvent(type) ? 'error' : undefined);
  if (type === 'bot_error' && typeof raw.line === 'number' && lines.length) lines[lines.length - 1].line = raw.line;
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
  tone?: BotConsoleLine['tone'],
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

function appendRunDiagnosticLines(lines: BotConsoleLine[], run: RunDto | null, currentReplay: ReplayDto | null): void {
  if (!run || isRunActive.value) return;
  const diagnostics: string[] = [];
  if (run.error_message) {
    diagnostics.push(run.error_message);
  }
  appendResultPayloadDiagnostics(diagnostics, run.result_payload);
  const summaryError = currentReplay?.summary?.error_message;
  if (typeof summaryError === 'string' && summaryError.trim() && !diagnostics.includes(summaryError)) {
    diagnostics.push(summaryError);
  }
  if (run.status === 'timeout' && diagnostics.length === 0) {
    diagnostics.push('Решение работало слишком долго и было остановлено.');
  } else if (run.status === 'failed' && diagnostics.length === 0) {
    diagnostics.push('Код не запустился.');
  }
  diagnostics
    .filter((message) => !lines.some((line) => line.message === message))
    .forEach((message, index) => {
      appendConsoleMessage(lines, message, 0, diagnosticRoleForStatus(run.status, message), `run-diagnostic-${index}`, 'error');
    });
}

function appendResultPayloadDiagnostics(diagnostics: string[], payload: Record<string, unknown> | null): void {
  const error = payload?.error;
  if (typeof error === 'string' && error.trim()) diagnostics.push(error);
  const metrics = isRecord(payload?.metrics) ? payload.metrics : {};
  const compileError = metrics.compile_error;
  if (typeof compileError === 'string' && compileError.trim()) diagnostics.push(compileError);
  const compileErrors = metrics.compile_errors;
  if (isRecord(compileErrors)) {
    Object.entries(compileErrors).forEach(([slot, message]) => {
      if (typeof message === 'string' && message.trim()) {
        diagnostics.push(`${slot}: ${message}`);
      }
    });
  }
}

function diagnosticRoleForStatus(status: RunDto['status'], message = ''): string {
  const normalized = message.toLowerCase();
  if (status === 'timeout' || normalized.includes('timed out') || normalized.includes('timeout')) return 'таймаут';
  if (status === 'canceled') return 'остановлено';
  return 'ошибка запуска';
}

function diagnosticRoleForEvent(type: string): string {
  if (type === 'timeout') return 'таймаут';
  if (type === 'compile_error') return 'ошибка кода';
  if (type === 'runtime_error') return 'ошибка выполнения';
  if (type === 'run_error') return 'ошибка запуска';
  return '';
}

function isDiagnosticConsoleEvent(type: string): boolean {
  return ['compile_error', 'runtime_error', 'bot_error', 'run_error', 'timeout'].includes(type);
}

function isActiveRun(run: RunDto | null): run is RunDto {
  return Boolean(run && ['created', 'queued', 'running'].includes(run.status));
}

function toggleCompetitionPanel(): void {
  conditionPanelOpen.value = false;
  competitionPanelOpen.value = !competitionPanelOpen.value;
  if (competitionPanelOpen.value && !isRefreshingStats.value) {
    void refreshStats();
  }
}

function closeCompetitionPanel(): void {
  competitionPanelOpen.value = false;
}

function toggleConditionPanel(): void {
  competitionPanelOpen.value = false;
  conditionPanelOpen.value = !conditionPanelOpen.value;
  if (conditionPanelOpen.value) { viewMode.value = 'split'; if (isMobile.value) mobilePanel.value = 'reference'; }
}

function closeConditionPanel(): void {
  conditionPanelOpen.value = false;
  if (mobilePanel.value === 'reference') mobilePanel.value = 'viewer';
}

function closeSidePanels(): void {
  closeCompetitionPanel();
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
  if (data?.type === 'agp.renderer.ready') { sendRendererInit(); return; }
  if (data?.type !== 'agp.renderer.shortcut' || !['Space', 'ArrowLeft', 'ArrowRight', 'Digit1', 'Digit2', 'Digit3'].includes(data.payload?.code)) return;
  handlePageKeydown(new KeyboardEvent('keydown', { key: String(data.payload.key), code: data.payload.code }));
}
function handlePageKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    closeViewerFullscreen();
    closeSidePanels();
    return;
  }
  if (event.ctrlKey || event.metaKey || event.altKey || sidePanelOpen.value || isShortcutInput(event.target)) {
    return;
  }
  if (event.code === 'Space') {
    event.preventDefault();
    toggleReplay();
    return;
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault();
    stepReplay(-1);
    return;
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault();
    stepReplay(1);
    return;
  }
  if (event.key === '1') {
    setViewMode('viewer');
    return;
  }
  if (event.key === '2') {
    setViewMode('split');
    return;
  }
  if (event.key === '3') {
    setViewMode('code');
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
  return 46;
}

function loadViewMode(): WorkspaceViewMode {
  try {
    const stored = String(localStorage.getItem(VIEW_MODE_STORAGE_KEY) ?? '');
    if (stored === 'viewer' || stored === 'split' || stored === 'code') return stored;
  } catch {
    // localStorage may be unavailable in tests or restricted contexts
  }
  return 'split';
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
  if (window.matchMedia('(max-width: 900px)').matches) return;
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
  if (mapped && teams.some((team) => team.team_id === mapped && team.captain_user_id === sessionStore.nickname)) {
    return mapped;
  }

  const existing = teams.find((team) => team.captain_user_id === sessionStore.nickname);
  if (existing) {
    saveTeamMapping(gameId, sessionStore.nickname, existing.team_id);
    return existing.team_id;
  }

  const created = await createTeam({
    game_id: gameId,
    name: `${game.value?.title ?? 'Task'} / ${sessionStore.nickname}`,
    captain_user_id: sessionStore.nickname,
  });
  teamsByGame.value = [...teams, created];
  saveTeamMapping(gameId, sessionStore.nickname, created.team_id);
  return created.team_id;
}

function teamIdForLeaderboardEntry(entry: SingleTaskLeaderboardEntryDto): string {
  return teamsByGame.value.find((team) => team.captain_user_id === entry.user_id)?.team_id ?? '';
}

function taskDraftKey(): string {
  return `agp_task_code_draft:${sessionStore.nickname}:${gameIdFromRoute()}:${selectedSlotKey.value}`;
}

function syncEditorFromWorkspace(payload: TeamWorkspaceDto): void {
  selectedSlotKey.value = payload.slot_states[0]?.slot_key ?? '';
  const selectedSlot = payload.slot_states.find((slot) => slot.slot_key === selectedSlotKey.value);
  const initialCode = selectedSlot?.code ?? selectedTemplateCode.value ?? firstDemoCode.value ?? '';
  savedCode.value = selectedSlot?.code ?? '';
  let restoredCode = initialCode;
  try {
    const draft = JSON.parse(localStorage.getItem(taskDraftKey()) ?? 'null');
    if (draft && draft.base === savedCode.value && typeof draft.code === 'string') restoredCode = draft.code;
    if (draft?.savedAt) draftSavedAt.value = new Date(draft.savedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  } catch { draftStorageFailed.value = true; }
  editorCode.value = restoredCode;
}

function undoReplacement(): void {
  if (replacementUndo.value === null) return;
  editorCode.value = replacementUndo.value;
  replacementUndo.value = null;
}
function seekReplay(frame: number): void {
  stopReplayPlayback();
  replayFrameIndex.value = Math.max(0, Math.min(frame, replayFrames.value.length - 1));
}
function seekProblem(frame: number): void {
  analysisOpen.value = true;
  closeConditionPanel();
  seekReplay(frame);
  if (isMobile.value) mobilePanel.value = 'analysis';
}
async function inspectRunLine(location: { line: number; role?: string }, runId = currentRun.value?.run_id): Promise<void> {
  if (!runId) return;
  try {
    const snapshot = await getRunCode(runId);
    const slot = location.role || selectedSlotKey.value;
    reviewCode.value = snapshot.codes_by_slot[slot] ?? Object.values(snapshot.codes_by_slot)[0] ?? '';
    reviewRevision.value = snapshot.revisions_by_slot[slot] ?? Object.values(snapshot.revisions_by_slot)[0] ?? 0;
    reviewLine.value = location.line;
    reviewingRunCode.value = true;
    if (isMobile.value) mobilePanel.value = 'code';
    else if (viewMode.value === 'viewer') viewMode.value = 'split';
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : 'Не удалось открыть код запуска'; }
}

async function loadPage(): Promise<void> {
  const gameId = gameIdFromRoute();
  if (!gameId) {
    errorMessage.value = 'Не найдена задача для запуска';
    return;
  }

  isBootstrapping.value = true;
  void listSingleTaskCatalog().then(items => { catalogTasks.value = items; }).catch(() => { /* Optional next-task navigation must not block the editor. */ });
  errorMessage.value = '';
  replay.value = null;
  rendererPreview.value = null;
  replayError.value = '';
  try {
    game.value = await getGame(gameId);
    if (game.value.mode !== 'single_task') {
      throw new Error('Этот экран предназначен для задач');
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
    sendRendererInit();
    if (typeof route.query.inspect_run === 'string') await inspectRunLine({ line: Number(route.query.line) || 1, role: typeof route.query.role === 'string' ? route.query.role : undefined }, route.query.inspect_run);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось подготовить задачу';
  } finally {
    isBootstrapping.value = false;
  }
}

async function loadRendererPreview(gameSlug: string): Promise<RendererPreviewDto | null> {
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
  if (!teamId.value || !selectedSlotKey.value || !editorCode.value.trim()) return;
  isSaving.value = true;
  errorMessage.value = '';
  try {
    await updateSlotCode({
      team_id: teamId.value,
      slot_key: selectedSlotKey.value,
      actor_user_id: sessionStore.nickname,
      code: editorCode.value,
    });
    savedCode.value = editorCode.value;
    workspace.value = await getWorkspace(teamId.value);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось сохранить код';
    throw error;
  } finally {
    isSaving.value = false;
  }
}

async function launchRun(repeatRunId?: string): Promise<void> {
  if (!game.value || !teamId.value || isRunActive.value) return;
  previousRun.value = repeatRunId && currentRun.value ? { ...currentRun.value, result_payload: currentRun.value.result_payload ?? replay.value?.summary ?? null } : null;
  const initialFrame = replayFrames.value[0];
  repeatPreview.value = repeatRunId && initialFrame ? { tick: initialFrame.tick, phase: 'preview', frame: initialFrame.frame } : null;
  isLaunching.value = true;
  errorMessage.value = '';
  launchNotice.value = '';
  replay.value = null;
  replayError.value = '';
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
      launchNotice.value = 'У вас уже есть активный запуск. Можно дождаться результата или остановить его кнопкой ■.';
    } else {
      errorMessage.value = error instanceof Error ? humanizeLaunchError(error.message) : 'Не удалось запустить попытку';
    }
  } finally {
    isLaunching.value = false;
  }
}

async function stopRun(): Promise<void> {
  if (!game.value || !currentRun.value) return;
  isCancelling.value = true;
  launchNotice.value = '';
  try {
    currentRun.value = await stopSingleTaskRun({
      game_id: game.value.game_id,
      run_id: currentRun.value.run_id,
    });
    stopRunPolling();
    await loadReplay(currentRun.value.run_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось остановить попытку';
  } finally {
    isCancelling.value = false;
  }
}

async function restartRun(): Promise<void> {
  if (!game.value || !currentRun.value || !isRunActive.value) return;
  isRestarting.value = true;
  errorMessage.value = '';
  launchNotice.value = '';
  replay.value = null;
  replayError.value = '';
  try {
    const activeRunId = currentRun.value.run_id;
    currentRun.value = await stopSingleTaskRun({
      game_id: game.value.game_id,
      run_id: activeRunId,
    });
    stopRunPolling();
    await refreshStats();
    currentRun.value = null;
    launchNotice.value = 'Старый запуск отменен. Создаем новую попытку.';
    await launchRun();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось перезапустить попытку';
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
      if (currentRun.value && currentRun.value.run_id === runId && !isRunActive.value) {
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
  isReplayLoading.value = true;
  replayError.value = '';
  try {
    replay.value = await getRunReplay(runId);
    replayFrameIndex.value = 0;
    sendRendererState();
    if (replayFrames.value.length > 1) {
      startReplayPlayback();
    } else {
      maybeShowVictoryCelebration();
    }
  } catch (error) {
    replayError.value = error instanceof Error ? error.message : 'Повтор пока недоступен';
  } finally {
    isReplayLoading.value = false;
  }
}

async function refreshStats(): Promise<void> {
  if (!game.value) return;
  isRefreshingStats.value = true;
  try {
    const [freshLeaderboard, freshAttempts] = await Promise.all([
      getSingleTaskLeaderboard(game.value.game_id, 10),
      listSingleTaskAttempts({
        game_id: game.value.game_id,
        requested_by: sessionStore.nickname,
        limit: 12,
      }),
    ]);
    leaderboard.value = freshLeaderboard;
    attempts.value = freshAttempts;
    const currentRunId = currentRun.value?.run_id ?? '';
    const currentAttempt: RunDto | null = currentRunId
      ? freshAttempts.find((attempt) => attempt.run_id === currentRunId) ?? null
      : null;
    const activeAttempt = freshAttempts.find(isActiveRun) ?? null;
    const latestCompletedAttempt =
      freshAttempts.find((attempt) => !['created', 'queued', 'running'].includes(attempt.status)) ?? null;
    if (currentAttempt) {
      const wasActive = isRunActive.value;
      currentRun.value = currentAttempt;
      if (wasActive && !['created', 'queued', 'running'].includes(currentAttempt.status)) {
        stopRunPolling();
        await loadReplay(currentAttempt.run_id);
      }
    }
    if (activeAttempt) {
      currentRun.value = activeAttempt;
      startRunPolling(activeAttempt.run_id);
      launchNotice.value = 'Найден активный запуск. Можно дождаться результата или остановить его кнопкой ■.';
    } else if (!isRunActive.value && launchNotice.value.includes('актив')) {
      launchNotice.value = '';
    }
    if (!currentRun.value && latestCompletedAttempt) {
      currentRun.value = latestCompletedAttempt;
      if (replay.value?.run_id !== latestCompletedAttempt.run_id) {
        await loadReplay(latestCompletedAttempt.run_id);
      }
    }
    const repeatId = currentRun.value?.execution_options?.repeat_run_id;
    if (repeatId && previousRun.value?.run_id !== repeatId) previousRun.value = await getRun(repeatId, { compactPayload: true });
  } finally {
    isRefreshingStats.value = false;
  }
}

function sendToRenderer(message: Record<string, unknown>): void {
  const frame = rendererFrameRef.value;
  if (!frame?.contentWindow) return;
  frame.contentWindow.postMessage(sanitizeForPostMessage(message), '*');
}

function sendRendererInit(): void {
  if (!game.value) return;
  sendToRenderer({
    type: 'agp.renderer.init',
    payload: {
      gameId: game.value.game_id,
      gameSlug: game.value.slug,
      mode: 'single_task',
      runId: currentRun.value?.run_id ?? null,
    },
  });
  sendRendererState();
}

function sendRendererState(): void {
  const activeFrame = currentReplayFrame.value;
  const preview = repeatPreview.value ?? rendererPreview.value;
  sendToRenderer({
    type: 'agp.renderer.state',
    payload: {
      motion: { duration_ms: replayIsPlaying.value ? Math.min(180, replayPlaybackDelayMs.value / 2) : 0 },
      tick: activeFrame?.tick ?? preview?.tick ?? 0,
      phase: activeFrame?.phase ?? currentRun.value?.status ?? preview?.phase ?? 'preview',
      frame: activeFrame?.frame ?? preview?.frame ?? {},
    },
  });
  const canSendTerminalResult = replayFrames.value.length === 0 || replayFrameIndex.value >= replayFrames.value.length - 1;
  if (currentRun.value && !isRunActive.value && canSendTerminalResult) {
    sendToRenderer({
      type: 'agp.renderer.result',
      payload: currentRun.value.result_payload ?? { status: currentRun.value.status },
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
    maybeShowVictoryCelebration();
  }
}

function maybeShowVictoryCelebration(): void {
  const run = currentRun.value;
  if (!run || run.status !== 'finished' || !isSolvedRun(run)) return;
  if (!replay.value || replay.value.run_id !== run.run_id) return;
  if (replayFrames.value.length > 1 && replayFrameIndex.value < replayFrames.value.length - 1) return;
  if (celebratedRunIds.has(run.run_id)) return;
  celebratedRunIds.add(run.run_id);
  victoryCelebrationVisible.value = true;
  if (victoryCelebrationHandle) {
    clearTimeout(victoryCelebrationHandle);
  }
  victoryCelebrationHandle = setTimeout(() => {
    victoryCelebrationVisible.value = false;
    victoryCelebrationHandle = null;
  }, 2400);
}

function attemptScoreValue(attempt: RunDto | null): number | null {
  const metrics = attempt?.result_payload?.metrics;
  if (isRecord(metrics) && typeof metrics.score === 'number') return metrics.score;
  const score = attempt?.result_payload?.score;
  return typeof score === 'number' ? score : null;
}

function isSolvedRun(run: RunDto): boolean {
  const payload = run.result_payload;
  const metrics = isRecord(payload?.metrics) ? payload.metrics : {};
  if (typeof metrics.compile_error === 'string' && metrics.compile_error.trim()) return false;
  if (typeof metrics.solved === 'boolean') return metrics.solved;
  if (typeof payload?.solved === 'boolean') return payload.solved;
  if (typeof payload?.status === 'string') {
    return ['success', 'solved', 'passed', 'win', 'won'].includes(payload.status.trim().toLowerCase());
  }
  for (const key of ['solved', 'success', 'passed', 'win', 'won', 'escaped', 'reached_exit', 'reached_goal', 'completed']) {
    if (typeof metrics[key] === 'boolean' && metrics[key]) return true;
  }
  return false;
}

function attemptScore(attempt: RunDto): string {
  return String(attemptScoreValue(attempt) ?? '—');
}

function humanizeLaunchError(message: string): string {
  if (message.includes('409') && message.includes('активный single_task запуск')) {
    return 'У вас уже есть активный запуск. Дождитесь результата или остановите его кнопкой ■.';
  }
  return message;
}

function attemptStatusLabel(status: RunDto['status']): string {
  const labels: Record<RunDto['status'], string> = {
    created: 'создано',
    queued: 'в очереди',
    running: 'выполняется',
    finished: 'завершено',
    failed: 'ошибка',
    timeout: 'слишком долго',
    canceled: 'остановлено',
  };
  return labels[status];
}

watch([editorCode, savedCode], () => {
  if (isBootstrapping.value || !selectedSlotKey.value) return;
  try {
    if (editorCode.value === savedCode.value) localStorage.removeItem(taskDraftKey());
    else localStorage.setItem(taskDraftKey(), JSON.stringify({ code: editorCode.value, base: savedCode.value, savedAt: new Date().toISOString() }));
    draftStorageFailed.value = false;
    draftSavedAt.value = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  } catch { draftStorageFailed.value = true; }
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
    localStorage.setItem(SPLIT_RATIO_STORAGE_KEY, String(clampSplitRatio(nextRatio)));
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
  if (nextMode === 'code') {
    closeViewerFullscreen();
  }
});

onMounted(async () => {
  window.addEventListener('keydown', handlePageKeydown);
  window.addEventListener('message', onRendererMessage);
  window.addEventListener('pointermove', handleSplitPointerMove);
  window.addEventListener('pointerup', stopSplitResize);
  window.addEventListener('pointercancel', stopSplitResize);
  mobileMedia.addEventListener('change', updateMobileMode);
  updateHeaderCondensed();
  await loadPage();
});

onUnmounted(() => {
  clearInterval(statusTimer);
  mobileMedia.removeEventListener('change', updateMobileMode);
  window.removeEventListener('keydown', handlePageKeydown);
  window.removeEventListener('message', onRendererMessage);
  window.removeEventListener('pointermove', handleSplitPointerMove);
  window.removeEventListener('pointerup', stopSplitResize);
  window.removeEventListener('pointercancel', stopSplitResize);
  stopRunPolling();
  stopReplayPlayback();
  if (victoryCelebrationHandle) {
    clearTimeout(victoryCelebrationHandle);
    victoryCelebrationHandle = null;
  }
  stopSplitResize();
  closeViewerFullscreen();
  closeSidePanels();
});
</script>
