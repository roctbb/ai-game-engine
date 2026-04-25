<template>
  <section class="agp-grid agp-task-workspace">
    <header class="agp-task-header" :class="{ 'agp-task-header--condensed': isHeaderCondensed }">
      <div class="agp-task-header-main">
        <RouterLink to="/tasks" class="agp-back-link" title="К задачам" aria-label="К задачам">←</RouterLink>
        <h1>{{ game?.title || 'Задача' }}</h1>
      </div>
      <div v-if="!isBootstrapping" class="agp-task-header-player">
        <button
          class="agp-icon-button agp-icon-button--replay"
          :disabled="replayFrames.length <= 1"
          :title="replayIsPlaying ? 'Пауза (Space)' : 'Воспроизвести (Space)'"
          :aria-label="replayIsPlaying ? 'Пауза' : 'Воспроизвести'"
          @click="toggleReplay"
        >
          {{ replayIsPlaying ? '❚❚' : '▶' }}
        </button>
        <button
          class="agp-icon-button agp-icon-button--ghost"
          :disabled="replayFrames.length <= 1"
          title="Предыдущий кадр (←)"
          aria-label="Предыдущий кадр"
          @click="stepReplay(-1)"
        >
          ‹
        </button>
        <button
          class="agp-icon-button agp-icon-button--ghost"
          :disabled="replayFrames.length <= 1"
          title="Следующий кадр (→)"
          aria-label="Следующий кадр"
          @click="stepReplay(1)"
        >
          ›
        </button>
        <span class="small text-muted agp-player-frame-label">
          <template v-if="replayFrames.length">кадр {{ replayFrameIndex + 1 }}/{{ replayFrames.length }}</template>
          <template v-else>повтор после запуска</template>
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
          <select v-model.number="replayPlaybackDelayMs" class="form-select form-select-sm agp-speed-select">
            <option :value="1800">очень медленно</option>
            <option :value="1200">медленно</option>
            <option :value="700">обычно</option>
            <option :value="350">быстро</option>
          </select>
        </label>
        <div class="agp-player-side-buttons">
          <button
            class="agp-panel-toggle"
            :class="{ 'agp-panel-toggle--active': conditionPanelOpen }"
            :aria-pressed="conditionPanelOpen ? 'true' : 'false'"
            @click="toggleConditionPanel"
          >
            Условие
          </button>
          <button
            class="agp-panel-toggle"
            :class="{ 'agp-panel-toggle--active': competitionPanelOpen }"
            :aria-pressed="competitionPanelOpen ? 'true' : 'false'"
            @click="toggleCompetitionPanel"
          >
            {{ competitionButtonLabel }}
          </button>
        </div>
      </div>
      <div class="agp-task-header-actions">
        <div class="agp-view-mode-toggle" role="group" aria-label="Режим экрана">
          <button
            class="agp-icon-button agp-icon-button--ghost"
            :class="{ 'agp-icon-button--active': viewMode === 'viewer' }"
            title="Только просмотр (1)"
            aria-label="Только просмотр"
            @click="setViewMode('viewer')"
          >
            ◧
          </button>
          <button
            class="agp-icon-button agp-icon-button--ghost"
            :class="{ 'agp-icon-button--active': viewMode === 'split' }"
            title="Две колонки (2)"
            aria-label="Две колонки"
            @click="setViewMode('split')"
          >
            ◫
          </button>
          <button
            class="agp-icon-button agp-icon-button--ghost"
            :class="{ 'agp-icon-button--active': viewMode === 'code' }"
            title="Только код (3)"
            aria-label="Только код"
            @click="setViewMode('code')"
          >
            ≡
          </button>
        </div>
        <label
          v-if="viewMode === 'split'"
          class="agp-column-size-control"
          title="Размер колонок"
          aria-label="Размер колонок"
        >
          <span aria-hidden="true">◧</span>
          <input
            v-model.number="splitRatio"
            type="range"
            min="32"
            max="70"
            step="1"
            aria-label="Ширина просмотра"
          />
          <span class="mono">{{ splitRatio }}%</span>
        </label>
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
            class="agp-icon-button agp-icon-button--play"
            :disabled="isRunActive || !canLaunch || isLaunching || isRestarting || isSaving"
            title="Запустить код"
            aria-label="Запустить код"
            @click="launchRun"
          >
            ▶
          </button>
          <button
            v-if="isRunActive"
            class="agp-icon-button agp-icon-button--stop"
            :disabled="!isRunActive || !canStop || isCancelling || isRestarting"
            title="Остановить запуск"
            aria-label="Остановить запуск"
            @click="stopRun"
          >
            ■
          </button>
          <button
            v-if="isRunActive"
            class="agp-icon-button agp-icon-button--restart"
            :disabled="!isRunActive || !canRestart || isRestarting || isCancelling"
            title="Перезапустить зависший запуск"
            aria-label="Перезапустить запуск"
            @click="restartRun"
          >
            ↻
          </button>
        </div>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <article v-if="isBootstrapping" class="agp-card p-4 text-muted">Готовим рабочее место...</article>

    <transition name="agp-victory-pop">
      <div v-if="victoryCelebrationVisible" class="agp-victory-celebration" aria-live="polite">
        <div class="agp-victory-burst" aria-hidden="true">
          <span v-for="index in 18" :key="index"></span>
        </div>
        <div class="agp-victory-card">
          <span class="agp-victory-kicker">Победа</span>
          <strong>Задача решена!</strong>
          <small>Реплей досмотрен до конца</small>
        </div>
      </div>
    </transition>

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
        }"
        :style="mainColumnsStyle"
      >
        <article
          v-if="viewMode !== 'code'"
          :class="['agp-card p-3 agp-viewer-card', { 'agp-viewer-card--fullscreen': isViewerFullscreen }]"
        >
          <div class="agp-viewer-overlay agp-viewer-overlay--status">
            <span class="agp-run-state-badge" :class="`agp-run-state-badge--${runStatusTone}`"></span>
            {{ runStatusLabel }}
          </div>
          <button
            type="button"
            class="agp-viewer-overlay agp-viewer-fullscreen"
            :title="isViewerFullscreen ? 'Свернуть' : 'Во весь экран'"
            :aria-label="isViewerFullscreen ? 'Свернуть' : 'Во весь экран'"
            @click.stop="isViewerFullscreen ? closeViewerFullscreen() : openViewerFullscreen()"
          >
            {{ isViewerFullscreen ? '×' : '⛶' }}
          </button>
          <div v-if="rendererUrl" class="agp-viewer-frame">
            <iframe
              ref="rendererFrameRef"
              :key="rendererKey"
              :src="rendererUrl"
              title="Визуализация задачи"
              sandbox="allow-scripts allow-same-origin"
              @load="sendRendererInit"
            ></iframe>
          </div>
          <div v-else class="agp-card-soft p-3 small text-muted">
            У этой задачи нет отдельной визуализации.
          </div>
          <div v-if="isReplayLoading" class="agp-viewer-overlay agp-viewer-overlay--message">Загружаем повтор...</div>
          <div v-else-if="replayError" class="agp-viewer-overlay agp-viewer-overlay--message agp-viewer-overlay--danger">{{ replayError }}</div>
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
        <button
          v-if="viewMode === 'split'"
          type="button"
          class="agp-main-splitter"
          title="Перетащите, чтобы изменить ширину колонок"
          aria-label="Изменить ширину колонок"
          @pointerdown="startSplitResize"
        ></button>

        <article v-if="viewMode !== 'viewer'" class="agp-card p-3 agp-code-card">
          <div class="agp-code-toolbar">
            <span class="agp-pill" :class="isDirty ? 'agp-pill--warning' : 'agp-pill--neutral'">
              {{ isDirty ? 'изменен' : 'синхронизирован' }}
            </span>
            <button class="agp-panel-toggle" :disabled="!selectedSlotKey" @click="applyTemplate">Шаблон</button>
            <button
              v-if="canUseDemoStrategy"
              class="agp-panel-toggle"
              :disabled="!selectedSlotKey || !firstDemoCode"
              @click="applyDemo"
            >
              Пример
            </button>
          </div>
          <CodeEditor v-model="editorCode" :readonly="!selectedSlotKey || isSaving || isRunActive" language="python" />
        </article>
      </div>
    </template>

    <transition name="agp-drawer-fade">
      <button
        v-if="sidePanelOpen"
        type="button"
        class="agp-drawer-backdrop"
        aria-label="Закрыть выезжаемую панель"
        @click="closeSidePanels"
      ></button>
    </transition>

    <transition name="agp-modal-pop">
      <aside v-if="conditionPanelOpen" class="agp-cockpit-modal agp-condition-modal" role="dialog" aria-label="Условие задачи">
        <header class="agp-cockpit-panel-head">
          <div>
            <h2 class="h6 mb-0">Условие задачи</h2>
            <div class="small">Брифинг перед запуском</div>
          </div>
          <button type="button" class="agp-cockpit-close" aria-label="Закрыть условие" @click="closeConditionPanel">×</button>
        </header>

        <article class="agp-cockpit-panel-body">
          <p class="agp-condition-lead">{{ game?.description || 'Описание задачи пока не заполнено.' }}</p>
          <div v-if="templates?.player_instruction" class="agp-cockpit-callout">
            {{ templates.player_instruction }}
          </div>
          <div v-else class="agp-cockpit-muted">Инструкция пока не задана.</div>
          <RouterLink
            v-if="docs?.links.length && game"
            class="btn btn-sm btn-outline-secondary mt-3"
            :to="{ name: 'game-docs', params: { gameId: game.game_id }, query: { from: 'task' } }"
            target="_blank"
            rel="noopener noreferrer"
          >
            Открыть документацию
          </RouterLink>
        </article>
      </aside>
    </transition>

    <transition name="agp-drawer-slide">
      <aside v-if="competitionPanelOpen" class="agp-competition-drawer" role="dialog" aria-label="Лидерборд и попытки">
        <header class="agp-cockpit-panel-head">
          <div>
            <h2 class="h6 mb-0">Лидерборд</h2>
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
import {
  createTeam,
  getGame,
  getGameDocs,
  getGameTemplates,
  getRun,
  getRunReplay,
  getSingleTaskLeaderboard,
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
  type RunDto,
  type SingleTaskLeaderboardEntryDto,
  type SingleTaskLeaderboardDto,
  type TeamDto,
  type TeamWorkspaceDto,
} from '../lib/api';
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
}
type WorkspaceViewMode = 'viewer' | 'split' | 'code';

const route = useRoute();
const sessionStore = useSessionStore();
const REPLAY_SPEED_STORAGE_KEY = 'agp_replay_speed_ms';
const SPLIT_RATIO_STORAGE_KEY = 'agp_task_workspace_split_ratio';
const VIEW_MODE_STORAGE_KEY = 'agp_task_workspace_view_mode';

const game = ref<GameDto | null>(null);
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
const leaderboard = ref<SingleTaskLeaderboardDto | null>(null);
const attempts = ref<RunDto[]>([]);
const competitionPanelOpen = ref(false);
const conditionPanelOpen = ref(false);
const isViewerFullscreen = ref(false);
const replayFrameIndex = ref(0);
const replayIsPlaying = ref(false);
const replayPlaybackDelayMs = ref(loadReplayPlaybackDelay());
const isBootstrapping = ref(false);
const isSaving = ref(false);
const isLaunching = ref(false);
const isCancelling = ref(false);
const isRestarting = ref(false);
const isReplayLoading = ref(false);
const isRefreshingStats = ref(false);
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
let replayPlaybackHandle: ReturnType<typeof setInterval> | null = null;
let victoryCelebrationHandle: ReturnType<typeof setTimeout> | null = null;
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
  if (!currentRun.value) return isDirty.value ? 'Есть несохраненные изменения. При запуске они сохранятся.' : 'Готово к запуску.';
  if (isRunActive.value) return 'Запуск уже идет. Его можно остановить кнопкой ■ сверху.';
  return 'Последняя попытка завершена.';
});
const launchHint = computed(() => {
  if (isRestarting.value) return 'Перезапускаем попытку';
  if (isLaunching.value) return 'Сохраняем и запускаем';
  if (isCancelling.value) return 'Останавливаем запуск';
  if (isRunActive.value) return 'Дождитесь результата или остановите запуск';
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
  return typeof place === 'number' ? `Лидерборд #${place}` : 'Лидерборд';
});
const mainColumnsStyle = computed(() => ({
  '--agp-viewer-col': `${splitRatio.value}%`,
  '--agp-code-col': `${100 - splitRatio.value}%`,
}));
const sidePanelOpen = computed(() => competitionPanelOpen.value || conditionPanelOpen.value);
const runStatusLabel = computed(() => (currentRun.value ? attemptStatusLabel(currentRun.value.status) : 'готово'));
const runStatusTone = computed<'idle' | 'active' | 'success' | 'danger'>(() => {
  if (!currentRun.value) return 'idle';
  if (['created', 'queued', 'running'].includes(currentRun.value.status)) return 'active';
  if (currentRun.value.status === 'finished') return 'success';
  if (['failed', 'timeout', 'canceled'].includes(currentRun.value.status)) return 'danger';
  return 'idle';
});
const solvedLabel = computed(() => (myLeaderboardEntry.value?.solved ? 'решено' : 'еще нет'));
const codeStateLabel = computed(() => {
  if (!selectedSlotKey.value) return 'Сейчас подготовим файл для решения';
  if (isRunActive.value) return 'Запуск идет, код временно нельзя менять';
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

function isActiveRun(run: RunDto | null): run is RunDto {
  return Boolean(run && ['created', 'queued', 'running'].includes(run.status));
}

function sanitizeForPostMessage(value: unknown): unknown {
  try {
    return JSON.parse(JSON.stringify(value ?? {}));
  } catch {
    return {};
  }
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
}

function closeConditionPanel(): void {
  conditionPanelOpen.value = false;
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

function isTypingContext(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.closest('.cm-editor')) return true;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  return target.isContentEditable;
}

function handlePageKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    closeViewerFullscreen();
    closeSidePanels();
    return;
  }
  if (isTypingContext(event.target)) {
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

function loadReplayPlaybackDelay(): number {
  try {
    const stored = Number(localStorage.getItem(REPLAY_SPEED_STORAGE_KEY));
    if ([350, 700, 1200, 1800].includes(stored)) return stored;
  } catch {
    // localStorage may be unavailable in tests or restricted contexts
  }
  return 1200;
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

function syncEditorFromWorkspace(payload: TeamWorkspaceDto): void {
  selectedSlotKey.value = payload.slot_states[0]?.slot_key ?? '';
  const selectedSlot = payload.slot_states.find((slot) => slot.slot_key === selectedSlotKey.value);
  const initialCode = selectedSlot?.code ?? selectedTemplateCode.value ?? firstDemoCode.value ?? '';
  editorCode.value = initialCode;
  savedCode.value = selectedSlot?.code ?? '';
}

async function loadPage(): Promise<void> {
  const gameId = gameIdFromRoute();
  if (!gameId) {
    errorMessage.value = 'Не найдена задача для запуска';
    return;
  }

  isBootstrapping.value = true;
  errorMessage.value = '';
  replay.value = null;
  replayError.value = '';
  try {
    game.value = await getGame(gameId);
    if (game.value.mode !== 'single_task') {
      throw new Error('Этот экран предназначен для задач');
    }
    const [freshTemplates, freshDocs] = await Promise.all([getGameTemplates(gameId), getGameDocs(gameId)]);
    templates.value = freshTemplates;
    docs.value = freshDocs;
    teamId.value = await ensurePersonalTeam(gameId);
    workspace.value = await getWorkspace(teamId.value);
    syncEditorFromWorkspace(workspace.value);
    await refreshStats();
    sendRendererInit();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось подготовить задачу';
  } finally {
    isBootstrapping.value = false;
  }
}

function applyTemplate(): void {
  if (!selectedTemplateCode.value) return;
  editorCode.value = selectedTemplateCode.value;
}

function applyDemo(): void {
  if (!canUseDemoStrategy.value) return;
  if (!firstDemoCode.value) return;
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
  } finally {
    isSaving.value = false;
  }
}

async function launchRun(): Promise<void> {
  if (!game.value || !teamId.value || isRunActive.value) return;
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
    });
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
  pollingHandle = setInterval(async () => {
    try {
      currentRun.value = await getRun(runId);
      sendRendererState();
      if (currentRun.value && !isRunActive.value) {
        stopRunPolling();
        await loadReplay(runId);
        await refreshStats();
      }
    } catch {
      // keep latest state
    }
  }, 1200);
}

function stopRunPolling(): void {
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
  } finally {
    isRefreshingStats.value = false;
  }
}

function sendToRenderer(message: Record<string, unknown>): void {
  const frame = rendererFrameRef.value;
  if (!frame?.contentWindow) return;
  frame.contentWindow.postMessage(sanitizeForPostMessage(message), window.location.origin);
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
  sendToRenderer({
    type: 'agp.renderer.state',
    payload: {
      tick: activeFrame?.tick ?? 0,
      phase: activeFrame?.phase ?? currentRun.value?.status ?? 'idle',
      frame: activeFrame?.frame ?? currentRun.value?.result_payload ?? {},
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
  replayPlaybackHandle = setInterval(() => {
    const lastFrameIndex = replayFrames.value.length - 1;
    if (replayFrameIndex.value >= lastFrameIndex) {
      stopReplayPlayback({ completed: true });
      return;
    }
    replayFrameIndex.value += 1;
    if (replayFrameIndex.value >= lastFrameIndex) {
      stopReplayPlayback({ completed: true });
    }
  }, replayPlaybackDelayMs.value);
}

function clearReplayPlaybackTimer(): void {
  if (!replayPlaybackHandle) return;
  clearInterval(replayPlaybackHandle);
  replayPlaybackHandle = null;
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
  if (!replay.value || replay.value.run_id !== run.run_id || replayFrames.value.length <= 1) return;
  if (replayFrameIndex.value < replayFrames.value.length - 1) return;
  if (celebratedRunIds.has(run.run_id)) return;
  celebratedRunIds.add(run.run_id);
  victoryCelebrationVisible.value = true;
  if (victoryCelebrationHandle) {
    clearTimeout(victoryCelebrationHandle);
  }
  victoryCelebrationHandle = setTimeout(() => {
    victoryCelebrationVisible.value = false;
    victoryCelebrationHandle = null;
  }, 3200);
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
  for (const key of ['solved', 'success', 'passed', 'win', 'won']) {
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
    finished: 'готово',
    failed: 'ошибка',
    timeout: 'слишком долго',
    canceled: 'остановлено',
  };
  return labels[status];
}

watch(replayFrameIndex, () => {
  sendRendererState();
});

watch(replayPlaybackDelayMs, (nextDelay) => {
  try {
    localStorage.setItem(REPLAY_SPEED_STORAGE_KEY, String(nextDelay));
  } catch {
    // ignore storage failures; the selected speed still works for this session
  }
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
  window.addEventListener('pointermove', handleSplitPointerMove);
  window.addEventListener('pointerup', stopSplitResize);
  window.addEventListener('pointercancel', stopSplitResize);
  updateHeaderCondensed();
  await loadPage();
});

onUnmounted(() => {
  window.removeEventListener('keydown', handlePageKeydown);
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
