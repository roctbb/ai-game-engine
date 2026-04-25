<template>
  <section class="agp-grid lobby-page">
    <header class="agp-card p-2 lobby-head">
      <div class="lobby-title-block">
        <div class="lobby-title-line">
          <RouterLink class="agp-back-link" to="/lobbies">←</RouterLink>
          <h1 class="h4 mb-0">{{ lobby?.title || 'Лобби' }}</h1>
        </div>
      </div>
      <nav v-if="lobby" class="lobby-tabs" aria-label="Разделы лобби">
        <button v-if="hasPlayerInLobby" :class="{ active: activeTab === 'code' }" @click="activeTab = 'code'">Код</button>
        <button :class="{ active: activeTab === 'lobby' }" @click="activeTab = 'lobby'">Лобби</button>
        <button v-if="hasPlayerInLobby" :class="{ active: activeTab === 'game' }" @click="activeTab = 'game'">Игра</button>
        <button v-if="activeCompetition" :class="{ active: activeTab === 'competition' }" @click="activeTab = 'competition'">
          Соревнование
        </button>
        <button v-if="competitionArchive.length" :class="{ active: activeTab === 'archive' }" @click="activeTab = 'archive'">
          Архив
        </button>
      </nav>
      <div v-if="lobby && hasPlayerInLobby" class="lobby-head-actions">
        <div class="lobby-ready-summary">
          <strong>{{ readyStatusLabel }}</strong>
          <span>{{ readyStatusHint }}</span>
        </div>
        <button
          v-if="showPlayAction"
          class="lobby-ready-icon lobby-ready-icon--play"
          :disabled="!canPlay || isBusy"
          :title="isBusy ? 'Обновляем статус' : 'Готов играть'"
          aria-label="Готов играть"
          @click="play"
        >
          {{ isBusy ? '…' : '▶' }}
        </button>
        <button
          v-if="showStopAction"
          class="lobby-ready-icon lobby-ready-icon--stop"
          :disabled="!canStop || isBusy"
          title="Не готов"
          aria-label="Не готов"
          @click="stop"
        >
          ■
        </button>
      </div>
      <div v-else-if="lobby && canManage" class="lobby-head-actions">
        <button class="btn btn-outline-secondary" :disabled="!canJoinAsPlayer || isBusy" @click="joinAsPlayer">
          {{ isBusy ? '...' : 'Участвовать как игрок' }}
        </button>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка лобби...</article>

    <article v-else-if="joinRequired" class="agp-card p-4 lobby-access-card">
      <div>
        <h2 class="h6 mb-1">Нужен код входа</h2>
        <p class="small text-muted mb-0">Введите код, который дал преподаватель.</p>
      </div>
      <div class="lobby-access-form">
        <input
          v-model.trim="lobbyAccessCode"
          class="form-control"
          autocomplete="off"
          autofocus
          @keyup.enter="submitLobbyAccessCode"
        />
        <button class="btn btn-dark" :disabled="!lobbyAccessCode || isBusy" @click="submitLobbyAccessCode">
          {{ isBusy ? 'Проверяем...' : 'Войти' }}
        </button>
      </div>
    </article>

    <template v-else-if="lobby">
      <article v-if="activeCompetition" class="agp-card p-3 lobby-competition-banner">
        <div>
          <strong>{{ activeCompetition.status === 'completed' ? 'Победитель определен' : 'Идет соревнование' }}</strong>
          <div class="small text-muted">
            {{ competitionBannerText }}
          </div>
        </div>
        <button class="btn btn-sm btn-outline-secondary" @click="activeTab = 'competition'">Открыть сетку</button>
      </article>

      <section v-if="activeTab === 'code'" class="lobby-code-layout">
        <aside class="agp-card p-3 lobby-roles">
          <div class="d-flex justify-content-between align-items-center gap-2 mb-3">
            <strong>Роли</strong>
            <span class="small text-muted">{{ filledRequiredSlots }}/{{ requiredSlotCount }} обязательных</span>
          </div>
          <button
            v-for="slot in slotStates"
            :key="slot.slot_key"
            class="lobby-role-button"
            :class="{ active: activeSlotKey === slot.slot_key }"
            @click="selectSlot(slot.slot_key)"
          >
            <span>{{ slot.slot_key }}</span>
            <small>{{ slot.code?.trim() ? 'заполнено' : slot.required ? 'пусто' : 'необязательная' }}</small>
          </button>
          <RouterLink
            v-if="docs?.links.length"
            class="btn btn-sm btn-outline-secondary mt-3 w-100"
            :to="{
              name: 'game-docs',
              params: { gameId: lobby.game_id },
              query: { from: 'lobby', lobby_id: lobby.lobby_id },
            }"
            target="_blank"
            rel="noopener noreferrer"
          >
            Документация
          </RouterLink>
        </aside>

        <article class="agp-card p-3 lobby-editor">
          <div class="lobby-editor-toolbar">
            <div>
              <h2 class="h6 mb-1">{{ activeSlotKey || 'Код' }}</h2>
              <p class="small text-muted mb-0">{{ codeStateLabel }}</p>
            </div>
            <div class="d-flex gap-2 flex-wrap">
              <button class="btn btn-sm btn-outline-secondary" :disabled="!activeTemplate || codeLockedByCompetition" @click="applyTemplate">
                Шаблон
              </button>
              <button
                v-if="canUseDemoStrategy"
                class="btn btn-sm btn-outline-secondary"
                :disabled="!activeDemoStrategy || codeLockedByCompetition"
                @click="applyDemoStrategy"
              >
                Пример
              </button>
              <button class="btn btn-sm btn-dark" :disabled="!canSaveCode" @click="saveCode">
                {{ isSavingCode ? 'Сохранение...' : 'Сохранить' }}
              </button>
            </div>
          </div>
          <CodeEditor v-model="editorCode" :readonly="!activeSlotKey || codeLockedByCompetition" />
        </article>
      </section>

      <section v-else-if="activeTab === 'lobby'" class="lobby-state-grid">
        <article class="agp-card p-3 lobby-overview-strip">
          <div>
            <span class="small text-muted">Играют</span>
            <strong class="mono">{{ lobby.playing_team_ids.length }}</strong>
          </div>
          <div>
            <span class="small text-muted">В очереди</span>
            <strong class="mono">{{ lobby.queued_team_ids.length }}</strong>
          </div>
          <div>
            <span class="small text-muted">Готовятся</span>
            <strong class="mono">{{ preparingTeamIds.length }}</strong>
          </div>
          <div>
            <span class="small text-muted">Матчей</span>
            <strong class="mono">{{ currentTrainingMatchGroups.length + archivedTrainingMatchGroups.length }}</strong>
          </div>
        </article>
        <article class="agp-card p-3 lobby-participants-card">
          <h2 class="h6 mb-3">Участники</h2>
          <div class="lobby-participant-columns">
            <ParticipantColumn title="Играют" :team-ids="lobby.playing_team_ids" :stats="statsByTeam" empty="Сейчас никто не играет" />
            <ParticipantColumn title="В очереди" :team-ids="lobby.queued_team_ids" :stats="statsByTeam" empty="Очередь пуста" />
            <ParticipantColumn title="Готовятся" :team-ids="preparingTeamIds" :stats="statsByTeam" empty="Все уже готовы" />
          </div>
        </article>

        <aside class="lobby-side-stack">
          <article class="agp-card p-3">
            <h2 class="h6 mb-3">Матчи</h2>
            <div class="lobby-match-list">
              <article
                v-for="group in currentTrainingMatchGroups"
                :key="group.group_id"
                class="lobby-match-group"
              >
                <header>
                  <span>Текущий матч</span>
                  <strong>{{ group.runs.length }} {{ pluralizePlayers(group.runs.length) }}</strong>
                </header>
                <div class="lobby-run-links">
                  <RouterLink
                    v-for="run in group.runs"
                    :key="run.run_id"
                    class="btn btn-sm btn-outline-secondary"
                    :to="`/runs/${run.run_id}/watch`"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click.stop
                  >
                    {{ run.team_id ? teamLabel(run.team_id) : 'Смотреть' }}
                  </RouterLink>
                </div>
              </article>
              <article
                v-for="group in archivedTrainingMatchGroups"
                :key="group.group_id"
                class="lobby-match-group muted"
              >
                <header>
                  <span>Архивный матч</span>
                  <strong>{{ group.runs.length }} {{ pluralizePlayers(group.runs.length) }}</strong>
                </header>
                <div class="lobby-run-links">
                  <RouterLink
                    v-for="run in group.runs"
                    :key="run.run_id"
                    class="btn btn-sm btn-outline-secondary"
                    :to="`/runs/${run.run_id}/watch`"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click.stop
                  >
                    {{ run.team_id ? teamLabel(run.team_id) : 'Смотреть' }}
                  </RouterLink>
                </div>
              </article>
              <div v-if="!currentTrainingMatchGroups.length && !archivedTrainingMatchGroups.length" class="small text-muted">
                Матчей пока нет.
              </div>
            </div>
          </article>

          <article v-if="canManage" class="agp-card p-3 lobby-teacher-card">
            <div>
              <h2 class="h6 mb-1">Соревнование</h2>
              <p class="small text-muted mb-0">Старт блокирует обычную подготовку в лобби.</p>
            </div>
            <div class="lobby-competition-settings-grid">
              <label class="lobby-competition-setting">
                <span>Размер матча</span>
                <input v-model.number="competitionMatchSize" class="form-control form-control-sm" type="number" min="2" max="64" />
              </label>
              <label class="lobby-competition-setting">
                <span>Проходят</span>
                <input
                  v-model.number="competitionAdvanceTopK"
                  class="form-control form-control-sm"
                  type="number"
                  min="1"
                  :max="competitionMatchSize"
                />
              </label>
              <label class="lobby-competition-setting lobby-competition-setting--wide">
                <span>Тай-брейк</span>
                <select v-model="competitionTieBreakPolicy" class="form-select form-select-sm">
                  <option value="manual">Ручное решение</option>
                  <option value="shared_advancement">Пропустить всех на границе</option>
                </select>
              </label>
              <label class="lobby-competition-setting lobby-competition-setting--wide">
                <span>Код</span>
                <select v-model="competitionCodePolicy" class="form-select form-select-sm">
                  <option value="locked_on_start">Заблокировать на старте</option>
                  <option value="allowed_between_matches">Разрешить между матчами</option>
                  <option value="locked_on_registration">Заблокировать при регистрации</option>
                </select>
              </label>
            </div>
            <button class="btn btn-sm btn-outline-secondary w-100" :disabled="isBusy || Boolean(activeCompetition)" @click="startCompetitionFromLobby">
              Начать соревнование
            </button>
          </article>
        </aside>
      </section>

      <section v-else-if="activeTab === 'game'" class="lobby-game-layout">
        <article class="agp-card p-3 lobby-game-view">
          <iframe
            v-if="displayedGameRunId"
            :src="`/runs/${displayedGameRunId}/watch?embed=1&autoplay=1&speed_ms=700`"
            title="Текущая игра"
          ></iframe>
          <div v-else class="lobby-empty">
            <h2 class="h6">Текущей игры пока нет</h2>
            <p class="small text-muted mb-0">Заполните код и нажмите Play. Изменения попадут в следующую игру.</p>
          </div>
        </article>
        <aside class="agp-card p-3 lobby-game-stats">
          <h2 class="h6 mb-3">Текущая игра</h2>
          <div v-if="currentGameStats.length" class="lobby-stats-list">
            <div v-for="stat in currentGameStats" :key="`${stat.run_id}-${stat.team_id}`" class="lobby-stat-row">
              <strong>{{ stat.display_name }}</strong>
              <span>{{ stat.status }} · счет {{ stat.score }}</span>
            </div>
          </div>
          <div v-else class="small text-muted">Статистика появится, когда начнется матч.</div>
        </aside>
      </section>

      <section v-else-if="activeTab === 'competition' && activeCompetition" class="agp-card p-3 lobby-competition-panel">
        <div class="d-flex justify-content-between gap-3 flex-wrap">
          <div>
            <h2 class="h6 mb-1">{{ cleanCompetitionTitle(activeCompetition.title) }}</h2>
            <p class="small text-muted mb-0">
              {{ competitionStatusLabel(activeCompetition.status) }} · матч {{ activeCompetition.match_size }} игроков · проходят {{ activeCompetition.advancement_top_k }}
            </p>
          </div>
          <div v-if="canManage" class="d-flex gap-2 flex-wrap">
            <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/competitions/${activeCompetition.competition_id}`">
              Управление
            </RouterLink>
            <button
              class="btn btn-sm btn-outline-secondary"
              :disabled="!canFinishActiveCompetition || isBusy"
              @click="finishCompetitionFromLobby"
            >
              Завершить
            </button>
          </div>
        </div>
        <div v-if="activeCompetition.pending_reason" class="alert alert-warning py-2 mt-3 mb-0">
          {{ activeCompetition.pending_reason }}
        </div>
        <div v-if="activeCompetition.winner_team_ids.length" class="lobby-winners mt-3">
          <span class="small text-muted">Победитель</span>
          <strong>{{ activeCompetition.winner_team_ids.map(teamLabel).join(', ') }}</strong>
        </div>
        <div v-if="activeCompetition.rounds.length" class="lobby-rounds mt-3">
          <section v-for="round in activeCompetition.rounds" :key="round.round_index" class="lobby-round">
            <header>
              <strong>Раунд {{ round.round_index }}</strong>
              <span class="small text-muted">{{ competitionRoundStatusLabel(round.status) }}</span>
            </header>
            <article v-for="(match, matchIndex) in round.matches" :key="match.match_id" class="lobby-competition-match">
              <div class="d-flex justify-content-between gap-2 flex-wrap">
                <strong>Матч {{ matchIndex + 1 }}</strong>
                <span class="small text-muted">{{ competitionMatchStatusLabel(match.status) }}</span>
              </div>
              <div class="lobby-match-team-list">
                <span v-for="teamId in match.team_ids" :key="teamId" class="agp-topic-chip">
                  {{ teamLabel(teamId) }}
                </span>
              </div>
              <div v-if="Object.keys(match.scores_by_team).length" class="small text-muted">
                <span v-for="teamId in match.team_ids" :key="`${match.match_id}-${teamId}-score`">
                  {{ teamLabel(teamId) }}: <span class="mono">{{ scoreLabel(match.scores_by_team[teamId] ?? null) }}</span>
                </span>
              </div>
              <div v-if="match.advanced_team_ids.length" class="small">
                Прошли дальше: <strong>{{ match.advanced_team_ids.map(teamLabel).join(', ') }}</strong>
              </div>
              <div v-if="match.tie_break_reason" class="small text-warning">{{ match.tie_break_reason }}</div>
              <div v-if="Object.keys(match.run_ids_by_team).length" class="d-flex gap-2 flex-wrap">
                <RouterLink
                  v-for="[teamId, runId] in Object.entries(match.run_ids_by_team)"
                  :key="`${match.match_id}-${teamId}-${runId}`"
                  class="btn btn-sm btn-outline-secondary"
                  :to="`/runs/${runId}/watch`"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ teamLabel(teamId) }}
                </RouterLink>
              </div>
            </article>
          </section>
        </div>
        <div v-else class="small text-muted mt-3">Сетка появится после старта первого раунда.</div>
      </section>

      <section v-else-if="activeTab === 'archive'" class="agp-card p-3">
        <h2 class="h6 mb-3">Архив соревнований</h2>
        <div class="lobby-match-list">
          <RouterLink
            v-for="item in competitionArchive"
            :key="item.competition_id"
            class="lobby-match-row"
            :to="`/competitions/${item.competition_id}`"
          >
            <span>{{ cleanCompetitionTitle(item.title) }}</span>
            <strong>{{ competitionStatusLabel(item.status) }}</strong>
          </RouterLink>
        </div>
      </section>

    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, onUnmounted, ref, watch, type PropType } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import CodeEditor from '../components/CodeEditor.vue';
import {
  finishLobbyCompetition,
  getGame,
  getGameDocs,
  getGameTemplates,
  getLobby,
  getWorkspace,
  joinLobbyAsUser,
  listCompetitions,
  listCompetitionRuns,
  listLobbyCompetitionArchive,
  listRuns,
  playLobby,
  startLobbyCompetition,
  stopLobby,
  updateSlotCode,
  type CompetitionCodePolicy,
  type CompetitionDto,
  type CompetitionMatchStatus,
  type CompetitionRoundStatus,
  type CompetitionRunItemDto,
  type CompetitionStatus,
  type GameDocumentationDto,
  type GameDto,
  type GameTemplatesDto,
  type LobbyCompetitionDto,
  type LobbyDto,
  type LobbyParticipantStatsDto,
  type RunDto,
  type SlotStateDto,
  type StreamEnvelopeDto,
  type TeamWorkspaceDto,
  type TieBreakPolicy,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

const ParticipantColumn = defineComponent({
  props: {
    title: { type: String, required: true },
    teamIds: { type: Array as PropType<string[]>, required: true },
    stats: { type: Object as PropType<Record<string, LobbyParticipantStatsDto>>, required: true },
    empty: { type: String, required: true },
  },
  setup(props) {
    return () =>
      h('section', { class: 'lobby-participant-column' }, [
        h('h3', props.title),
        props.teamIds.length
          ? props.teamIds.map((teamId) => {
              const stat = props.stats[teamId];
              return h('div', { class: 'lobby-player-row', key: teamId }, [
                h('strong', stat?.display_name ?? teamId),
                h(
                  'span',
                  `победы ${stat?.wins ?? 0} · игр ${stat?.matches_total ?? 0} · средний счет ${
                    stat?.average_score === null || stat?.average_score === undefined
                      ? 'нет данных'
                      : stat.average_score.toFixed(1)
                  }`,
                ),
              ]);
            })
          : h('div', { class: 'small text-muted' }, props.empty),
      ]);
  },
});

interface TrainingRunLink {
  run_id: string;
  team_id: string;
}

interface TrainingMatchGroup {
  group_id: string;
  runs: TrainingRunLink[];
}

interface CurrentGameStatRow {
  run_id: string;
  team_id: string;
  display_name: string;
  status: string;
  score: string;
}

const route = useRoute();
const sessionStore = useSessionStore();

const lobby = ref<LobbyDto | null>(null);
const game = ref<GameDto | null>(null);
const workspace = ref<TeamWorkspaceDto | null>(null);
const templates = ref<GameTemplatesDto | null>(null);
const docs = ref<GameDocumentationDto | null>(null);
const activeCompetition = ref<CompetitionDto | null>(null);
const competitionRuns = ref<CompetitionRunItemDto[]>([]);
const trainingRuns = ref<RunDto[]>([]);
const competitionArchive = ref<LobbyCompetitionDto[]>([]);
const activeTab = ref<'code' | 'lobby' | 'game' | 'competition' | 'archive'>('code');
const activeSlotKey = ref('');
const editorCode = ref('');
const savedCode = ref('');
const isLoading = ref(false);
const isBusy = ref(false);
const isSavingCode = ref(false);
const errorMessage = ref('');
const joinRequired = ref(false);
const lobbyAccessCode = ref('');
const competitionMatchSize = ref(2);
const competitionAdvanceTopK = ref(1);
const competitionTieBreakPolicy = ref<TieBreakPolicy>('manual');
const competitionCodePolicy = ref<CompetitionCodePolicy>('locked_on_start');
const lastGameRunId = ref('');
let lobbyEventSource: EventSource | null = null;
let pollingHandle: ReturnType<typeof setInterval> | null = null;
let competitionPollingHandle: ReturnType<typeof setInterval> | null = null;

const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const canUseDemoStrategy = computed(() => canManage.value);
const hasPlayerInLobby = computed(() => Boolean(lobby.value?.my_team_id));
const slotStates = computed(() => workspace.value?.slot_states ?? []);
const activeSlot = computed(() => slotStates.value.find((slot) => slot.slot_key === activeSlotKey.value) ?? null);
const requiredSlotStates = computed(() => slotStates.value.filter((slot) => slot.required));
const requiredSlotCount = computed(() => requiredSlotStates.value.length);
const filledRequiredSlots = computed(() => requiredSlotStates.value.filter((slot) => Boolean(slot.code?.trim())).length);
const isDirty = computed(() => editorCode.value !== savedCode.value);
const activeTemplate = computed(() => templates.value?.templates.find((item) => item.slot_key === activeSlotKey.value)?.code ?? '');
const activeDemoStrategy = computed(
  () => templates.value?.demo_strategies.find((item) => item.slot_key === activeSlotKey.value) ?? null,
);
const canSaveCode = computed(() =>
  Boolean(
    lobby.value?.my_team_id &&
      activeSlotKey.value &&
      isDirty.value &&
      !isSavingCode.value &&
      !codeLockedByCompetition.value,
  ),
);
const canUseTrainingQueue = computed(() =>
  Boolean(lobby.value && ['draft', 'open', 'running'].includes(lobby.value.status) && !activeCompetition.value),
);
const canPlay = computed(() =>
  Boolean(
    lobby.value?.my_team_id &&
      canUseTrainingQueue.value &&
      lobby.value.my_status !== 'queued' &&
      lobby.value.my_status !== 'playing' &&
      requiredSlotCount.value > 0 &&
      filledRequiredSlots.value === requiredSlotCount.value &&
      !isDirty.value,
  ),
);
const canStop = computed(
  () => canUseTrainingQueue.value && (lobby.value?.my_status === 'queued' || lobby.value?.my_status === 'playing'),
);
const showPlayAction = computed(() => lobby.value?.my_status !== 'queued' && lobby.value?.my_status !== 'playing');
const showStopAction = computed(() => lobby.value?.my_status === 'queued' || lobby.value?.my_status === 'playing');
const readyStatusLabel = computed(() => {
  if (lobby.value?.my_status === 'playing') return 'Вы играете';
  if (lobby.value?.my_status === 'queued') return 'Вы в очереди';
  if (codeLockedByCompetition.value) return 'Код заблокирован';
  if (isDirty.value) return 'Есть изменения';
  if (requiredSlotCount.value === 0) return 'Нет ролей';
  if (filledRequiredSlots.value < requiredSlotCount.value) return 'Код не готов';
  return 'Можно играть';
});
const readyStatusHint = computed(() => {
  if (!canUseTrainingQueue.value && activeCompetition.value) return 'Во время соревнования обычная очередь отключена.';
  if (!canUseTrainingQueue.value) return 'Очередь сейчас недоступна.';
  if (lobby.value?.my_status === 'playing') return 'Кнопка “Не готов” остановит участие после текущего состояния.';
  if (lobby.value?.my_status === 'queued') return 'Матч начнется автоматически, когда найдутся соперники.';
  if (codeLockedByCompetition.value) return 'Политика соревнования запрещает менять код.';
  if (isDirty.value) return 'Сохраните код, чтобы встать в очередь.';
  if (requiredSlotCount.value === 0) return 'Игра не описала обязательные роли.';
  if (filledRequiredSlots.value < requiredSlotCount.value) {
    return `Заполнено ${filledRequiredSlots.value} из ${requiredSlotCount.value} обязательных ролей.`;
  }
  return 'Нажмите “Готов”, чтобы встать в очередь.';
});
const currentCompetitionRun = computed(() => {
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!activeCompetition.value || !myTeamId) return null;
  const activeStatuses = new Set(['created', 'queued', 'running']);
  return competitionRuns.value.find((item) => item.team_id === myTeamId && activeStatuses.has(item.status)) ?? null;
});
const currentCompetitionRunId = computed(() => {
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!activeCompetition.value || !myTeamId) return '';
  if (currentCompetitionRun.value) return currentCompetitionRun.value.run_id;

  const currentRoundIndex = activeCompetition.value.current_round_index;
  const currentRound = activeCompetition.value.rounds.find((round) => round.round_index === currentRoundIndex);
  if (!currentRound) return '';
  const myMatch = currentRound.matches.find((match) => match.team_ids.includes(myTeamId));
  return myMatch?.run_ids_by_team[myTeamId] ?? '';
});
const currentGameRunId = computed(() => currentCompetitionRunId.value || lobby.value?.current_run_id || '');
const displayedGameRunId = computed(() => currentGameRunId.value || lastGameRunId.value);
const canFinishActiveCompetition = computed(
  () => canManage.value && activeCompetition.value?.status === 'completed',
);
const competitionBannerText = computed(() => {
  if (activeCompetition.value?.status === 'completed') {
    return 'Лобби заблокировано, сетка доступна до ручного завершения учителем.';
  }
  if (!hasPlayerInLobby.value) {
    return 'Лобби заблокировано для входа и выхода. Матчи доступны из сетки соревнования.';
  }
  return 'Лобби заблокировано для входа и выхода. Текущая игра остается во вкладке "Игра".';
});
const codeLockedByCompetition = computed(() => {
  const competition = activeCompetition.value;
  if (!competition || competition.status === 'finished') return false;
  if (competition.code_policy === 'locked_on_registration') return true;
  if (competition.code_policy === 'locked_on_start') {
    return ['running', 'paused', 'completed'].includes(competition.status);
  }
  if (competition.code_policy === 'allowed_between_matches') return Boolean(currentCompetitionRun.value);
  return false;
});
const trainingRunsById = computed(() => {
  const result: Record<string, RunDto> = {};
  for (const run of trainingRuns.value) result[run.run_id] = run;
  return result;
});
const currentTrainingMatchGroups = computed(() =>
  buildTrainingMatchGroups(lobby.value?.current_run_ids ?? [], false)
);
const archivedTrainingMatchGroups = computed(() =>
  buildTrainingMatchGroups((lobby.value?.archived_run_ids ?? []).slice(0, 8), true)
);
const displayedTrainingRunIds = computed(() => {
  if (!displayedGameRunId.value) return [];
  const group = [...currentTrainingMatchGroups.value, ...archivedTrainingMatchGroups.value]
    .find((item) => item.runs.some((run) => run.run_id === displayedGameRunId.value));
  if (group) return group.runs.map((run) => run.run_id);
  return [displayedGameRunId.value];
});
const currentGameStats = computed<CurrentGameStatRow[]>(() =>
  displayedTrainingRunIds.value
    .map((runId) => trainingRunsById.value[runId])
    .filter((run): run is RunDto => Boolean(run))
    .map((run) => ({
      run_id: run.run_id,
      team_id: run.team_id,
      display_name: teamLabel(run.team_id),
      status: runStatusLabel(run.status),
      score: runScoreLabel(run),
    })),
);
const statsByTeam = computed(() => {
  const result: Record<string, LobbyParticipantStatsDto> = {};
  for (const stat of lobby.value?.participant_stats ?? []) result[stat.team_id] = stat;
  return result;
});
const preparingTeamIds = computed(() => {
  const listed = new Set([...(lobby.value?.playing_team_ids ?? []), ...(lobby.value?.queued_team_ids ?? [])]);
  return (lobby.value?.teams ?? []).map((team) => team.team_id).filter((teamId) => !listed.has(teamId));
});
const codeStateLabel = computed(() => {
  if (!activeSlotKey.value) return 'Выберите роль';
  if (codeLockedByCompetition.value) {
    if (activeCompetition.value?.code_policy === 'allowed_between_matches') {
      return 'Код заблокирован на время матча соревнования.';
    }
    if (activeCompetition.value?.code_policy === 'locked_on_registration') {
      return 'Код заблокирован политикой соревнования с момента регистрации.';
    }
    return 'Код заблокирован политикой соревнования до завершения соревнования.';
  }
  if (lobby.value?.my_status === 'playing') {
    return isDirty.value
      ? 'Есть несохраненные изменения. Текущая игра уже использует зафиксированный код.'
      : 'Сохранено. Текущая игра использует зафиксированный код, новые сохранения пойдут в следующую игру.';
  }
  if (lobby.value?.my_status === 'queued') {
    return isDirty.value
      ? 'Есть несохраненные изменения. Сохраните их до следующего запуска.'
      : 'Сохранено. При старте матча система зафиксирует этот код.';
  }
  if (isDirty.value) return 'Есть несохраненные изменения';
  return activeSlot.value?.code?.trim() ? 'Сохранено' : 'Пусто';
});

function lobbyId(): string {
  return String(route.params.lobbyId || '');
}

function scoreLabel(value: number | null): string {
  return value === null ? 'нет данных' : value.toFixed(1);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function runStatusLabel(status: RunDto['status']): string {
  const labels: Record<RunDto['status'], string> = {
    created: 'создан',
    queued: 'в очереди',
    running: 'идет',
    finished: 'завершен',
    failed: 'ошибка',
    timeout: 'таймаут',
    canceled: 'остановлен',
  };
  return labels[status];
}

function runScoreLabel(run: RunDto): string {
  const payload = isRecord(run.result_payload) ? run.result_payload : {};
  const metrics = isRecord(payload.metrics) ? payload.metrics : {};
  const score = extractRunScore(payload, run.team_id) ?? extractRunScore(metrics, run.team_id);
  return score === null ? 'пока нет' : score.toFixed(1);
}

function extractRunScore(source: Record<string, unknown>, teamId: string): number | null {
  for (const key of ['score', 'points']) {
    const raw = source[key];
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  }
  const scores = source.scores;
  if (!isRecord(scores)) return null;
  const ownScore = scores[teamId];
  if (typeof ownScore === 'number' && Number.isFinite(ownScore)) return ownScore;
  const values = Object.values(scores).filter((item): item is number => typeof item === 'number' && Number.isFinite(item));
  return values.length === 1 ? values[0] : null;
}

function pluralizePlayers(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return 'игрок';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'игрока';
  return 'игроков';
}

function buildTrainingMatchGroups(runIds: string[], archived: boolean): TrainingMatchGroup[] {
  const runs = runIds.map((runId) => ({
    run_id: runId,
    team_id: trainingRunsById.value[runId]?.team_id ?? '',
  }));
  const groupSize = game.value?.mode === 'small_match' ? 2 : Math.max(1, runs.length);
  const groups: TrainingMatchGroup[] = [];
  for (let index = 0; index < runs.length; index += groupSize) {
    const groupRuns = runs.slice(index, index + groupSize);
    groups.push({
      group_id: `${archived ? 'archive' : 'current'}-${index}-${groupRuns.map((run) => run.run_id).join('-')}`,
      runs: groupRuns,
    });
  }
  return groups;
}

function cleanCompetitionTitle(title: string): string {
  return title.replace(/^\[lobby:[^\]]+\]\s*/, '');
}

function teamLabel(teamId: string): string {
  return statsByTeam.value[teamId]?.display_name ?? teamId;
}

function competitionMatchStatusLabel(status: CompetitionMatchStatus): string {
  const labels: Record<CompetitionMatchStatus, string> = {
    pending: 'ожидает',
    running: 'играют',
    finished: 'завершен',
    awaiting_tiebreak: 'нужен тай-брейк',
    auto_advanced: 'автопроход',
  };
  return labels[status];
}

function competitionRoundStatusLabel(status: CompetitionRoundStatus): string {
  const labels: Record<CompetitionRoundStatus, string> = {
    running: 'идет',
    finished: 'завершен',
  };
  return labels[status];
}

function competitionStatusLabel(status: CompetitionStatus | string): string {
  const labels: Record<string, string> = {
    draft: 'черновик',
    running: 'идет',
    paused: 'пауза',
    completed: 'победитель определен',
    finished: 'завершено',
  };
  return labels[status];
}

function selectSlot(slotKey: string): void {
  const slot = slotStates.value.find((item) => item.slot_key === slotKey);
  activeSlotKey.value = slotKey;
  editorCode.value = slot?.code ?? '';
  savedCode.value = slot?.code ?? '';
}

function applyTemplate(): void {
  if (!activeTemplate.value) return;
  editorCode.value = activeTemplate.value;
}

function applyDemoStrategy(): void {
  if (!canUseDemoStrategy.value) return;
  if (!activeDemoStrategy.value) return;
  editorCode.value = activeDemoStrategy.value.code;
}

async function refreshWorkspace(): Promise<void> {
  if (!lobby.value?.my_team_id) {
    workspace.value = null;
    activeSlotKey.value = '';
    editorCode.value = '';
    savedCode.value = '';
    return;
  }
  workspace.value = await getWorkspace(lobby.value.my_team_id);
  if (!activeSlotKey.value && workspace.value.slot_states[0]) {
    selectSlot(workspace.value.slot_states[0].slot_key);
  } else if (activeSlotKey.value) {
    const slot = workspace.value.slot_states.find((item) => item.slot_key === activeSlotKey.value);
    savedCode.value = slot?.code ?? '';
    if (!isDirty.value) editorCode.value = savedCode.value;
  }
}

async function refreshCompetitions(): Promise<void> {
  if (!lobby.value) return;
  const lobbyIdValue = lobby.value.lobby_id;
  const competitions = await listCompetitions();
  activeCompetition.value =
    competitions.find(
      (item) => item.lobby_id === lobbyIdValue && item.status !== 'finished',
    ) ?? null;
  competitionRuns.value = activeCompetition.value
    ? await listCompetitionRuns(activeCompetition.value.competition_id)
    : [];
  const archive = await listLobbyCompetitionArchive(lobby.value.lobby_id);
  competitionArchive.value = archive.items;
  if (activeCompetition.value && activeTab.value === 'archive') activeTab.value = 'competition';
  if (!activeCompetition.value && activeTab.value === 'competition') {
    activeTab.value = competitionArchive.value.length ? 'archive' : 'lobby';
  }
  if (!competitionArchive.value.length && activeTab.value === 'archive') {
    activeTab.value = 'lobby';
  }
}

async function refreshTrainingRuns(): Promise<void> {
  if (!lobby.value) return;
  try {
    trainingRuns.value = await listRuns({
      lobby_id: lobby.value.lobby_id,
      run_kind: 'training_match',
    });
  } catch {
    // Keep the latest known run details; lobby state itself is still useful.
  }
}

async function loadLobby(): Promise<void> {
  const id = lobbyId();
  joinRequired.value = false;
  if (canManage.value) {
    lobby.value = await getLobby(id);
  } else {
    try {
      lobby.value = await joinLobbyAsUser({
        lobby_id: id,
        access_code: lobbyAccessCode.value.trim() || null,
      });
      lobbyAccessCode.value = '';
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      if (message.includes('код доступа')) {
        joinRequired.value = true;
        lobby.value = null;
        return;
      }
      throw error;
    }
  }
  game.value = await getGame(lobby.value.game_id);
  templates.value = await getGameTemplates(lobby.value.game_id);
  docs.value = await getGameDocs(lobby.value.game_id);
  await refreshWorkspace();
  await refreshTrainingRuns();
  await refreshCompetitions();
  if (!lobby.value.my_team_id && (activeTab.value === 'code' || activeTab.value === 'game')) {
    activeTab.value = 'lobby';
  }
}

async function refreshLobbyOnly(): Promise<void> {
  if (!lobby.value) return;
  lobby.value = await getLobby(lobby.value.lobby_id);
  await refreshTrainingRuns();
  await refreshCompetitions();
}

async function submitLobbyAccessCode(): Promise<void> {
  if (!lobbyAccessCode.value || isBusy.value) return;
  isBusy.value = true;
  isLoading.value = true;
  errorMessage.value = '';
  try {
    await loadLobby();
    if (lobby.value) {
      startLiveUpdates();
      startCompetitionPolling();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось войти в лобби';
  } finally {
    isBusy.value = false;
    isLoading.value = false;
  }
}

async function saveCode(): Promise<void> {
  if (!lobby.value?.my_team_id || !activeSlotKey.value) return;
  isSavingCode.value = true;
  errorMessage.value = '';
  try {
    await updateSlotCode({
      team_id: lobby.value.my_team_id,
      slot_key: activeSlotKey.value,
      actor_user_id: sessionStore.nickname,
      code: editorCode.value,
    });
    await refreshWorkspace();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось сохранить код';
  } finally {
    isSavingCode.value = false;
  }
}

const canJoinAsPlayer = computed(() =>
  Boolean(
    lobby.value &&
      canManage.value &&
      !lobby.value.my_team_id &&
      ['draft', 'open', 'running'].includes(lobby.value.status) &&
      lobby.value.teams.length < lobby.value.max_teams &&
      !activeCompetition.value,
  ),
);

async function joinAsPlayer(): Promise<void> {
  if (!lobby.value || !canJoinAsPlayer.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await joinLobbyAsUser({ lobby_id: lobby.value.lobby_id, access_code: null });
    await refreshWorkspace();
    activeTab.value = 'code';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось присоединиться как игрок';
  } finally {
    isBusy.value = false;
  }
}

async function play(): Promise<void> {
  if (!lobby.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await playLobby({ lobby_id: lobby.value.lobby_id });
    activeTab.value = 'game';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось встать в очередь';
  } finally {
    isBusy.value = false;
  }
}

async function stop(): Promise<void> {
  if (!lobby.value) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await stopLobby(lobby.value.lobby_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось остановить участие';
  } finally {
    isBusy.value = false;
  }
}

async function startCompetitionFromLobby(): Promise<void> {
  if (!lobby.value) return;
  isBusy.value = true;
  try {
    await startLobbyCompetition({
      lobby_id: lobby.value.lobby_id,
      title: `${lobby.value.title} / соревнование`,
      tie_break_policy: competitionTieBreakPolicy.value,
      code_policy: competitionCodePolicy.value,
      advancement_top_k: Math.max(1, Math.min(competitionAdvanceTopK.value, competitionMatchSize.value)),
      match_size: Math.max(2, competitionMatchSize.value),
    });
    await refreshLobbyOnly();
    activeTab.value = 'competition';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось начать соревнование';
  } finally {
    isBusy.value = false;
  }
}

async function finishCompetitionFromLobby(): Promise<void> {
  if (!lobby.value || !activeCompetition.value) return;
  isBusy.value = true;
  try {
    await finishLobbyCompetition({
      lobby_id: lobby.value.lobby_id,
      competition_id: activeCompetition.value.competition_id,
    });
    await refreshLobbyOnly();
    activeTab.value = 'archive';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось завершить соревнование';
  } finally {
    isBusy.value = false;
  }
}

function startLiveUpdates(): void {
  stopLiveUpdates();
  if (!lobby.value || typeof EventSource === 'undefined') {
    startPolling();
    return;
  }
  const source = new EventSource(
    `/api/v1/lobbies/${encodeURIComponent(lobby.value.lobby_id)}/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`
  );
  lobbyEventSource = source;
  source.addEventListener('agp.update', (event: MessageEvent) => {
    try {
      const envelope = JSON.parse(event.data) as StreamEnvelopeDto<LobbyDto>;
      if (envelope.channel !== 'lobby' || !envelope.payload) return;
      lobby.value = envelope.payload;
      void refreshTrainingRuns();
    } catch {
      // Keep last valid snapshot.
    }
  });
  source.onerror = () => {
    stopLiveUpdates();
    startPolling();
  };
}

function startCompetitionPolling(): void {
  stopCompetitionPolling();
  competitionPollingHandle = setInterval(() => {
    void refreshCompetitions();
  }, 3000);
}

function stopCompetitionPolling(): void {
  if (!competitionPollingHandle) return;
  clearInterval(competitionPollingHandle);
  competitionPollingHandle = null;
}

function startPolling(): void {
  if (pollingHandle) return;
  pollingHandle = setInterval(() => {
    void refreshLobbyOnly();
  }, 5000);
}

function stopLiveUpdates(): void {
  if (lobbyEventSource) {
    lobbyEventSource.close();
    lobbyEventSource = null;
  }
  if (pollingHandle) {
    clearInterval(pollingHandle);
    pollingHandle = null;
  }
}

watch(
  () => lobby.value?.my_team_id,
  () => {
    void refreshWorkspace();
  }
);

watch(
  () => currentGameRunId.value,
  (runId) => {
    if (runId) {
      lastGameRunId.value = runId;
      activeTab.value = 'game';
    }
  }
);

watch(
  () => hasPlayerInLobby.value,
  (hasPlayer) => {
    if (!hasPlayer && (activeTab.value === 'code' || activeTab.value === 'game')) {
      activeTab.value = 'lobby';
    }
  }
);

onMounted(async () => {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    await loadLobby();
    if (lobby.value) {
      startLiveUpdates();
      startCompetitionPolling();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось открыть лобби';
  } finally {
    isLoading.value = false;
  }
});

onUnmounted(() => {
  stopLiveUpdates();
  stopCompetitionPolling();
});
</script>

<style scoped>
.lobby-page {
  min-height: 100dvh;
  gap: 0.6rem;
  align-content: start;
  grid-auto-rows: max-content;
  padding: 0;
  background: #f2f5f9;
}

.lobby-head {
  position: sticky;
  top: 0;
  z-index: 12;
  display: grid;
  grid-template-columns: minmax(13rem, 0.7fr) minmax(16rem, 1fr) auto;
  gap: 0.65rem;
  align-items: center;
  min-height: 3.35rem;
  border-radius: 0;
  border-left: 0;
  border-right: 0;
}

.lobby-page > :not(.lobby-head) {
  margin-inline: 0.6rem;
}

.lobby-title-block {
  min-width: 0;
}

.lobby-title-line {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.lobby-title-line h1 {
  min-width: 0;
  overflow: hidden;
  font-size: 1rem;
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-head-actions,
.lobby-tabs,
.lobby-editor-toolbar,
.lobby-access-card,
.lobby-access-form {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.lobby-head-actions {
  justify-content: flex-end;
  flex-wrap: nowrap;
}

.lobby-ready-summary {
  display: grid;
  gap: 0.05rem;
  max-width: 14rem;
  text-align: right;
}

.lobby-ready-summary strong {
  font-size: 0.86rem;
}

.lobby-ready-summary span {
  color: var(--agp-text-muted);
  font-size: 0.72rem;
  line-height: 1.25;
}

.lobby-ready-icon {
  width: 2.45rem;
  height: 2.45rem;
  border: 1px solid transparent;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 1rem;
  font-weight: 900;
  line-height: 1;
}

.lobby-ready-icon:disabled {
  opacity: 0.38;
}

.lobby-ready-icon--play {
  background: #0f9f8e;
  box-shadow: 0 8px 18px rgba(15, 159, 142, 0.22);
  color: #fff;
}

.lobby-ready-icon--stop {
  border-color: #d4dde7;
  background: #fff;
  color: #8b98a8;
}

.lobby-access-card {
  justify-content: space-between;
  background: #f8fafc;
}

.lobby-access-form {
  min-width: min(100%, 24rem);
}

.lobby-access-form input {
  max-width: 14rem;
}

.lobby-competition-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-color: rgba(217, 119, 6, 0.35);
  background: #fff7ed;
}

.lobby-tabs button {
  border: 0;
  border-radius: 0.45rem;
  background: transparent;
  color: var(--agp-text-muted);
  padding: 0.4rem 0.7rem;
  font-weight: 800;
}

.lobby-tabs button.active {
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
}

.lobby-code-layout,
.lobby-game-layout,
.lobby-state-grid {
  display: grid;
  grid-template-columns: minmax(13rem, 17rem) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: start;
}

.lobby-state-grid {
  grid-template-columns: minmax(0, 1.4fr) minmax(20rem, 0.6fr);
}

.lobby-overview-strip {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.55rem;
  background: #f8fafc;
}

.lobby-overview-strip > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 0.45rem;
  background: #fff;
  padding: 0.45rem 0.6rem;
}

.lobby-game-layout {
  grid-template-columns: minmax(0, 1fr) minmax(17rem, 21rem);
  gap: 0.6rem;
  align-items: stretch;
  height: calc(100dvh - 4.7rem);
  min-height: 34rem;
}

.lobby-roles,
.lobby-editor,
.lobby-participant-column,
.lobby-match-list,
.lobby-stats-list,
.lobby-side-stack,
.lobby-teacher-card {
  display: grid;
  gap: 0.5rem;
}

.lobby-role-button {
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  background: #fff;
  padding: 0.55rem 0.65rem;
  display: grid;
  gap: 0.1rem;
  text-align: left;
}

.lobby-role-button.active {
  border-color: rgba(15, 118, 110, 0.45);
  background: #edf8f6;
}

.lobby-role-button span,
.lobby-participant-column h3 {
  font-weight: 850;
}

.lobby-role-button small,
.lobby-player-row span,
.lobby-stat-row span {
  color: var(--agp-text-muted);
}

.lobby-competition-panel,
.lobby-rounds,
.lobby-round,
.lobby-competition-match {
  display: grid;
  gap: 0.75rem;
}

.lobby-winners {
  display: grid;
  gap: 0.15rem;
  width: fit-content;
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: 0.45rem;
  background: #edf8f6;
  padding: 0.55rem 0.65rem;
}

.lobby-round {
  border-top: 1px solid var(--agp-border);
  padding-top: 0.75rem;
}

.lobby-round header,
.lobby-match-team-list {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.lobby-round header {
  justify-content: space-between;
}

.lobby-competition-match {
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  padding: 0.65rem;
  background: #f8fafc;
}

.lobby-competition-setting {
  display: grid;
  gap: 0.15rem;
  min-width: 7.2rem;
  font-size: 0.78rem;
  color: var(--agp-text-muted);
}

.lobby-editor-toolbar {
  justify-content: space-between;
  margin-bottom: 0.65rem;
}

.lobby-participant-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
}

.lobby-participant-column {
  align-content: start;
}

.lobby-participants-card {
  min-height: 10rem;
}

.lobby-side-stack {
  align-content: start;
}

.lobby-teacher-card {
  align-content: start;
}

.lobby-competition-settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.45rem;
}

.lobby-competition-setting--wide {
  grid-column: 1 / -1;
}

.lobby-participant-column h3 {
  font-size: 0.82rem;
  margin: 0;
}

.lobby-player-row,
.lobby-match-row,
.lobby-match-group,
.lobby-stat-row {
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  padding: 0.55rem 0.65rem;
  display: grid;
  gap: 0.1rem;
  text-decoration: none;
  color: inherit;
}

.lobby-game-layout .lobby-stat-row {
  padding: 0.45rem 0.55rem;
  font-size: 0.86rem;
}

.lobby-game-layout .lobby-stat-row span {
  font-size: 0.78rem;
}

.lobby-match-row {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.lobby-match-row.muted {
  background: #f8fafc;
}

.lobby-match-group {
  gap: 0.5rem;
}

.lobby-match-group.muted {
  background: #f8fafc;
}

.lobby-match-group header,
.lobby-run-links {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.lobby-match-group header {
  justify-content: space-between;
}

.lobby-game-view {
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

.lobby-game-view iframe {
  width: 100%;
  height: 100%;
  min-height: 0;
  border: 0;
  border-radius: 0;
  background: #0f172a;
}

.lobby-game-stats {
  min-height: 0;
  overflow: auto;
}

.lobby-empty {
  height: 100%;
  min-height: 24rem;
  display: grid;
  place-content: center;
  text-align: center;
}

@media (max-width: 980px) {
  .lobby-head,
  .lobby-code-layout,
  .lobby-game-layout,
  .lobby-state-grid,
  .lobby-participant-columns {
    grid-template-columns: 1fr;
    display: grid;
  }

  .lobby-head-actions,
  .lobby-teacher-card {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .lobby-ready-summary {
    max-width: 100%;
    text-align: left;
  }

  .lobby-overview-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .lobby-game-layout {
    height: auto;
    min-height: 0;
  }

  .lobby-game-view iframe {
    height: 70dvh;
    min-height: 28rem;
  }

  .lobby-competition-settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
