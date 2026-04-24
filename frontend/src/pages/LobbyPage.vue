<template>
  <section class="agp-grid lobby-page">
    <header class="agp-card p-3 lobby-head">
      <div>
        <RouterLink class="agp-back-link" to="/lobbies">←</RouterLink>
        <h1 class="h4 mb-1">{{ lobby?.title || 'Лобби' }}</h1>
        <div v-if="lobby" class="d-flex gap-2 flex-wrap">
          <span class="agp-pill" :class="statusPillClass(lobby.status)">{{ statusLabel(lobby.status) }}</span>
          <span class="agp-pill agp-pill--neutral">{{ game?.title || lobby.game_id }}</span>
          <span class="agp-pill agp-pill--neutral">{{ lobby.teams.length }}/{{ lobby.max_teams }} игроков</span>
        </div>
      </div>
      <div v-if="lobby" class="lobby-head-actions">
        <button class="btn btn-dark" :disabled="!canPlay || isBusy" @click="play">
          {{ isBusy ? '...' : 'Play' }}
        </button>
        <button class="btn btn-outline-secondary" :disabled="!canStop || isBusy" @click="stop">Stop</button>
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
      <nav class="agp-card p-2 lobby-tabs" aria-label="Разделы лобби">
        <button :class="{ active: activeTab === 'code' }" @click="activeTab = 'code'">Код</button>
        <button :class="{ active: activeTab === 'lobby' }" @click="activeTab = 'lobby'">Лобби</button>
        <button :class="{ active: activeTab === 'game' }" @click="activeTab = 'game'">Игра</button>
        <button v-if="activeCompetition" :class="{ active: activeTab === 'competition' }" @click="activeTab = 'competition'">
          Соревнование
        </button>
        <button v-if="competitionArchive.length" :class="{ active: activeTab === 'archive' }" @click="activeTab = 'archive'">
          Архив
        </button>
      </nav>

      <article v-if="activeCompetition" class="agp-card p-3 lobby-competition-banner">
        <div>
          <strong>{{ activeCompetition.status === 'completed' ? 'Победитель определен' : 'Идет соревнование' }}</strong>
          <div class="small text-muted">
            {{ activeCompetition.status === 'completed'
              ? 'Лобби заблокировано, сетка доступна до ручного завершения учителем.'
              : 'Лобби заблокировано для входа и выхода. Текущая игра остается во вкладке “Игра”.' }}
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
              <button class="btn btn-sm btn-dark" :disabled="!canSaveCode" @click="saveCode">
                {{ isSavingCode ? 'Сохранение...' : 'Сохранить' }}
              </button>
            </div>
          </div>
          <CodeEditor v-model="editorCode" :readonly="!activeSlotKey || codeLockedByCompetition" />
        </article>
      </section>

      <section v-else-if="activeTab === 'lobby'" class="lobby-state-grid">
        <article class="agp-card p-3">
          <h2 class="h6 mb-3">Участники</h2>
          <div class="lobby-participant-columns">
            <ParticipantColumn title="Играют" :team-ids="lobby.playing_team_ids" :stats="statsByTeam" empty="Сейчас никто не играет" />
            <ParticipantColumn title="В очереди" :team-ids="lobby.queued_team_ids" :stats="statsByTeam" empty="Очередь пуста" />
            <ParticipantColumn title="Готовятся" :team-ids="preparingTeamIds" :stats="statsByTeam" empty="Все уже готовы" />
          </div>
        </article>

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
      </section>

      <section v-else-if="activeTab === 'game'" class="lobby-game-layout">
        <article class="agp-card p-3 lobby-game-view">
          <iframe
            v-if="currentGameRunId"
            :src="`/runs/${currentGameRunId}/watch?embed=1&autoplay=1`"
            title="Текущая игра"
          ></iframe>
          <div v-else class="lobby-empty">
            <h2 class="h6">Текущей игры пока нет</h2>
            <p class="small text-muted mb-0">Заполните код и нажмите Play. Изменения попадут в следующую игру.</p>
          </div>
        </article>
        <aside class="agp-card p-3">
          <h2 class="h6 mb-3">Статистика игроков</h2>
          <div class="lobby-stats-list">
            <div v-for="stat in lobby.participant_stats" :key="stat.team_id" class="lobby-stat-row">
              <strong>{{ stat.display_name }}</strong>
              <span>победы {{ stat.wins }} · игр {{ stat.matches_total }} · средний счет {{ scoreLabel(stat.average_score) }}</span>
            </div>
          </div>
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
          <button
            v-if="canManage"
            class="btn btn-sm btn-outline-secondary"
            :disabled="!canFinishActiveCompetition || isBusy"
            @click="finishCompetitionFromLobby"
          >
            Завершить
          </button>
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
            <strong>{{ item.status }}</strong>
          </RouterLink>
        </div>
      </section>

      <section v-if="canManage && activeTab === 'lobby'" class="agp-card p-3 lobby-teacher-row">
        <div>
          <h2 class="h6 mb-1">Соревнование</h2>
          <p class="small text-muted mb-0">Старт блокирует обычную подготовку в лобби.</p>
        </div>
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
        <label class="lobby-competition-setting">
          <span>Тай-брейк</span>
          <select v-model="competitionTieBreakPolicy" class="form-select form-select-sm">
            <option value="manual">Ручное решение</option>
            <option value="shared_advancement">Пропустить всех на границе</option>
          </select>
        </label>
        <label class="lobby-competition-setting">
          <span>Код</span>
          <select v-model="competitionCodePolicy" class="form-select form-select-sm">
            <option value="locked_on_start">Заблокировать на старте</option>
            <option value="allowed_between_matches">Разрешить между матчами</option>
            <option value="locked_on_registration">Заблокировать при регистрации</option>
          </select>
        </label>
        <button class="btn btn-sm btn-outline-secondary" :disabled="isBusy || Boolean(activeCompetition)" @click="startCompetitionFromLobby">
          Начать соревнование
        </button>
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
  type LobbyStatus,
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
                h('span', `победы ${stat?.wins ?? 0} · игр ${stat?.matches_total ?? 0}`),
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
let lobbyEventSource: EventSource | null = null;
let pollingHandle: ReturnType<typeof setInterval> | null = null;
let competitionPollingHandle: ReturnType<typeof setInterval> | null = null;

const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const slotStates = computed(() => workspace.value?.slot_states ?? []);
const activeSlot = computed(() => slotStates.value.find((slot) => slot.slot_key === activeSlotKey.value) ?? null);
const requiredSlotStates = computed(() => slotStates.value.filter((slot) => slot.required));
const requiredSlotCount = computed(() => requiredSlotStates.value.length);
const filledRequiredSlots = computed(() => requiredSlotStates.value.filter((slot) => Boolean(slot.code?.trim())).length);
const isDirty = computed(() => editorCode.value !== savedCode.value);
const activeTemplate = computed(() => templates.value?.templates.find((item) => item.slot_key === activeSlotKey.value)?.code ?? '');
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
      requiredSlotCount.value > 0 &&
      filledRequiredSlots.value === requiredSlotCount.value &&
      !isDirty.value,
  ),
);
const canStop = computed(
  () => canUseTrainingQueue.value && (lobby.value?.my_status === 'queued' || lobby.value?.my_status === 'playing'),
);
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
const canFinishActiveCompetition = computed(
  () => canManage.value && activeCompetition.value?.status === 'completed',
);
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

function statusLabel(status: LobbyStatus): string {
  const labels: Record<LobbyStatus, string> = {
    draft: 'готовится',
    open: 'открыто',
    running: 'игра идет',
    paused: 'соревнование',
    updating: 'обновляется',
    closed: 'закрыто',
  };
  return labels[status];
}

function statusPillClass(status: LobbyStatus): string {
  if (status === 'open') return 'agp-pill--primary';
  if (status === 'running' || status === 'paused') return 'agp-pill--warning';
  if (status === 'closed') return 'agp-pill--danger';
  return 'agp-pill--neutral';
}

function scoreLabel(value: number | null): string {
  return value === null ? 'нет данных' : value.toFixed(1);
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

function competitionStatusLabel(status: CompetitionStatus): string {
  const labels: Record<CompetitionStatus, string> = {
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
  const legacyPrefix = `[lobby:${lobbyIdValue}] `;
  const competitions = await listCompetitions();
  activeCompetition.value =
    competitions.find(
      (item) => (item.lobby_id === lobbyIdValue || item.title.startsWith(legacyPrefix)) && item.status !== 'finished',
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
    if (!lobby.value.my_team_id) {
      try {
        lobby.value = await joinLobbyAsUser({ lobby_id: id, access_code: null });
      } catch {
        // Teacher can still view lobby without joining
      }
    }
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
  if (canManage.value && !lobby.value.my_team_id && activeTab.value === 'code') {
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
      activeTab.value = 'game';
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
  gap: 0.75rem;
}

.lobby-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.lobby-head-actions,
.lobby-tabs,
.lobby-editor-toolbar,
.lobby-teacher-row,
.lobby-access-card,
.lobby-access-form {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.lobby-head-actions,
.lobby-teacher-row {
  justify-content: flex-end;
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
  padding: 0.45rem 0.75rem;
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
  grid-template-columns: minmax(0, 1fr) minmax(20rem, 24rem);
}

.lobby-roles,
.lobby-editor,
.lobby-participant-column,
.lobby-match-list,
.lobby-stats-list {
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
  gap: 0.75rem;
}

.lobby-participant-column {
  align-content: start;
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
  min-height: 31rem;
}

.lobby-game-view iframe {
  width: 100%;
  height: 31rem;
  border: 0;
  border-radius: 0.45rem;
  background: #0f172a;
}

.lobby-empty {
  min-height: 28rem;
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
  .lobby-teacher-row {
    justify-content: flex-start;
  }
}
</style>
