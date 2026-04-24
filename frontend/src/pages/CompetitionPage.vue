<template>
  <section class="agp-grid competition-page">
    <header class="agp-card p-4 competition-hero">
      <div>
        <div class="small text-muted text-uppercase fw-semibold">Competition event</div>
        <h1 class="h3 mb-1">{{ competition?.title || 'Соревнование' }}</h1>
        <p class="text-muted mb-0">
          Турнирный экран: регистрация команд, раунды, продвижение, replay и модерация в одном месте.
        </p>
      </div>
      <div class="btn-group competition-view-toggle">
        <button class="btn btn-outline-dark btn-sm" :class="{ active: view === 'rounds' }" @click="view = 'rounds'">
          Раунды
        </button>
        <button class="btn btn-outline-dark btn-sm" :class="{ active: view === 'bracket' }" @click="view = 'bracket'">
          Сетка
        </button>
      </div>
    </header>

    <article v-if="isLoading" class="agp-card p-4 text-muted">Загрузка соревнования...</article>
    <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>

    <template v-else-if="competition">
      <article class="agp-card p-3 competition-command-center">
        <div class="competition-command-main">
          <div class="competition-status-line">
            <span class="agp-pill" :class="competitionStatusToneClass">{{ competitionStatusLabel }}</span>
            <span class="agp-pill agp-pill--neutral">{{ competition.format }}</span>
            <span class="agp-pill agp-pill--neutral">live: {{ competitionLiveLabel }}</span>
          </div>
          <div class="small text-muted mt-2">
            id <span class="mono">{{ competition.competition_id }}</span> · версия <span class="mono">{{ shortVersionId }}</span>
          </div>
          <div v-if="competition.pending_reason" class="competition-warning mt-2">
            <span class="fw-semibold">Ожидает решения:</span> {{ competition.pending_reason }}
          </div>
          <div class="competition-stat-grid mt-3">
            <div class="competition-stat">
              <span>участники</span>
              <strong>{{ competition.entrants.length }}</strong>
            </div>
            <div class="competition-stat">
              <span>готовы</span>
              <strong>{{ readyEntrantsCount }}</strong>
            </div>
            <div class="competition-stat">
              <span>забанены</span>
              <strong>{{ bannedEntrantsCount }}</strong>
            </div>
            <div class="competition-stat">
              <span>матч</span>
              <strong>{{ competition.match_size }} → top-{{ competition.advancement_top_k }}</strong>
            </div>
          </div>
          <div class="small mt-2" v-if="competition.winner_team_ids.length">
            Победители:
            <span class="mono">{{ competition.winner_team_ids.map((teamId) => teamName(teamId)).join(', ') }}</span>
          </div>
        </div>
        <div class="competition-actions">
          <div class="d-flex gap-2">
            <RouterLink
              v-if="competition"
              class="btn btn-sm btn-outline-secondary"
              :to="`/replays?game_id=${competition.game_id}&run_kind=competition_match`"
            >
              Реплеи игры
            </RouterLink>
            <button class="btn btn-sm btn-outline-secondary" :disabled="isCreatingTeam" @click="createTeamForCompetitionGame">
              {{ isCreatingTeam ? 'Создание...' : 'Создать команду' }}
            </button>
            <button class="btn btn-sm btn-dark" :disabled="!canRegister" @click="registerSelectedTeam">
              Зарегистрировать
            </button>
            <button class="btn btn-sm btn-outline-primary" :disabled="!canStart" @click="startCurrentCompetition">
              {{ isStarting ? 'Старт...' : 'Старт' }}
            </button>
            <button class="btn btn-sm btn-outline-success" :disabled="!canAdvance" @click="advanceCurrentCompetition">
              {{ isAdvancing ? 'Обработка...' : 'Следующий раунд' }}
            </button>
            <button class="btn btn-sm btn-outline-warning" :disabled="!canPause" @click="pauseCurrentCompetition">
              Пауза
            </button>
            <button class="btn btn-sm btn-outline-danger" :disabled="!canFinish" @click="finishCurrentCompetition">
              Завершить
            </button>
          </div>
        </div>
        <div v-if="!canModerate" class="small text-warning-emphasis mt-2">
          Управление соревнованием и анти-плагиатом доступно только teacher/admin.
        </div>
      </article>

      <article class="agp-card p-3" v-if="competition.status === 'draft' && canModerate">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Настройки Draft-соревнования</h2>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-secondary" :disabled="isSavingDraftSettings" @click="resetDraftSettings">
              Сбросить
            </button>
            <button class="btn btn-sm btn-dark" :disabled="!canSaveDraftSettings || isSavingDraftSettings" @click="saveDraftSettings">
              {{ isSavingDraftSettings ? 'Сохранение...' : 'Сохранить' }}
            </button>
          </div>
        </div>
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label small">Title</label>
            <input v-model.trim="draftTitle" class="form-control" />
          </div>
          <div class="col-md-3">
            <label class="form-label small">Tie-break policy</label>
            <select v-model="draftTieBreakPolicy" class="form-select mono">
              <option value="manual">manual</option>
              <option value="shared_advancement">shared_advancement</option>
              <option value="tiebreak_match">tiebreak_match</option>
              <option value="game_defined">game_defined</option>
            </select>
          </div>
          <div class="col-md-1">
            <label class="form-label small">match_size</label>
            <input v-model.number="draftMatchSize" class="form-control mono" type="number" min="2" max="64" />
          </div>
          <div class="col-md-2">
            <label class="form-label small">advancement_top_k</label>
            <input v-model.number="draftAdvancementTopK" class="form-control mono" type="number" min="1" max="64" />
          </div>
        </div>
        <div class="small text-muted mt-2">
          Ограничение: `advancement_top_k` не может быть больше `match_size`.
        </div>
      </article>

      <div class="agp-grid agp-grid--2">
        <article class="agp-card p-3">
          <h2 class="h6">Entrants</h2>
          <label class="form-label small">Команда для регистрации</label>
          <select v-model="selectedTeamId" class="form-select mb-3">
            <option value="">Выберите команду</option>
            <option v-for="team in teamsByGame" :key="team.team_id" :value="team.team_id">
              {{ team.name }}
            </option>
          </select>

          <table class="table align-middle mb-0">
            <thead>
              <tr>
                <th>team</th>
                <th>ready</th>
                <th>banned</th>
                <th>reason</th>
                <th>actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entrant in competition.entrants" :key="entrant.team_id">
                <td>{{ teamName(entrant.team_id) }}</td>
                <td class="mono small">{{ entrant.ready }}</td>
                <td class="mono small">{{ entrant.banned }}</td>
                <td class="small text-muted">{{ entrant.blocker_reason || '—' }}</td>
                <td>
                  <div class="d-flex gap-2 flex-wrap">
                    <button
                      class="btn btn-sm btn-outline-warning"
                      :disabled="!canModerate || !entrant.ready || entrant.banned || moderationBusyTeamId === entrant.team_id"
                      @click="setEntrantNotReady(entrant.team_id)"
                    >
                      Not ready
                    </button>
                    <button
                      class="btn btn-sm"
                      :class="entrant.banned ? 'btn-outline-success' : 'btn-outline-danger'"
                      :disabled="!canModerate || moderationBusyTeamId === entrant.team_id"
                      @click="toggleEntrantBan(entrant.team_id, !entrant.banned)"
                    >
                      {{ entrant.banned ? 'Unban' : 'Ban' }}
                    </button>
                    <button
                      class="btn btn-sm btn-outline-secondary"
                      :disabled="!canModerate || competition.status !== 'draft' || unregisteringTeamId === entrant.team_id"
                      @click="unregisterEntrant(entrant.team_id)"
                    >
                      Unregister
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="competition.entrants.length === 0">
                <td colspan="5" class="text-muted small">Пока нет зарегистрированных команд.</td>
              </tr>
            </tbody>
          </table>
        </article>

        <article class="agp-card p-3" v-if="view === 'rounds'">
          <h2 class="h6">Раунды и матчи</h2>
          <div class="d-flex flex-column gap-3">
            <article
              v-for="round in competition.rounds"
              :key="round.round_index"
              class="agp-card-soft p-3"
            >
              <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="fw-semibold">
                  Round {{ round.round_index }}
                </div>
                <span class="badge text-bg-light mono">{{ round.status }}</span>
              </div>
              <div class="d-flex flex-column gap-3">
                <article v-for="match in round.matches" :key="match.match_id" class="bg-white border rounded-3 p-3">
                  <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
                    <div>
                      <div class="fw-semibold mono">{{ match.match_id }}</div>
                      <div class="small text-muted">
                        Qualify top-{{ competition.advancement_top_k }} из {{ match.team_ids.length }}
                      </div>
                    </div>
                    <div class="d-flex gap-2 align-items-center">
                      <span class="badge text-bg-light mono">{{ match.status }}</span>
                      <button
                        class="btn btn-sm btn-outline-dark"
                        :disabled="!canModerate || match.status !== 'awaiting_tiebreak'"
                        @click="resolveTieByFirstTeam(round.round_index, match.match_id, match.team_ids)"
                      >
                        Resolve tie
                      </button>
                    </div>
                  </div>
                  <table class="table table-sm align-middle mb-0">
                    <thead>
                      <tr>
                        <th>team</th>
                        <th>score</th>
                        <th>placement</th>
                        <th>run</th>
                        <th>advanced</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="teamId in match.team_ids" :key="`${match.match_id}-${teamId}`">
                        <td>{{ teamName(teamId) }}</td>
                        <td class="mono small">{{ match.scores_by_team[teamId] ?? '—' }}</td>
                        <td class="mono small">{{ match.placements_by_team[teamId] ?? '—' }}</td>
                        <td class="mono small">
                          <template v-if="match.run_ids_by_team[teamId]">
                            <div class="d-flex align-items-center gap-2">
                              <RouterLink :to="`/runs/${match.run_ids_by_team[teamId]}/watch`">
                                {{ match.run_ids_by_team[teamId] }}
                              </RouterLink>
                              <button
                                class="btn btn-sm btn-outline-dark"
                                @click="inspectRunReplay(match.run_ids_by_team[teamId])"
                              >
                                Replay
                              </button>
                            </div>
                          </template>
                          <span v-else>—</span>
                        </td>
                        <td class="mono small">{{ match.advanced_team_ids.includes(teamId) ? 'yes' : '—' }}</td>
                      </tr>
                      <tr v-if="match.team_ids.length === 0">
                        <td colspan="5" class="text-muted small">В матче пока нет команд.</td>
                      </tr>
                    </tbody>
                  </table>
                  <div class="small text-muted mt-2" v-if="match.tie_break_reason">
                    tie_break_reason: <span class="mono">{{ match.tie_break_reason }}</span>
                  </div>
                </article>
              </div>
            </article>
            <div class="small text-muted" v-if="competition.rounds.length === 0">
              Раунды пока не созданы.
            </div>
          </div>
        </article>

        <article class="agp-card p-3" v-else>
          <h2 class="h6">Bracket view</h2>
          <div v-if="isBracketPrimaryCompatible" class="d-flex gap-3 flex-wrap">
            <article
              v-for="round in competition.rounds"
              :key="`bracket-${round.round_index}`"
              class="agp-card-soft p-3"
              style="min-width: 18rem"
            >
              <div class="fw-semibold mb-2">Round {{ round.round_index }}</div>
              <div class="d-flex flex-column gap-2">
                <div
                  v-for="match in round.matches"
                  :key="`bnode-${match.match_id}`"
                  class="bg-white border rounded-3 p-2"
                >
                  <div class="mono small fw-semibold mb-1">{{ match.match_id }}</div>
                  <div class="small" v-for="teamId in match.team_ids" :key="`bnode-team-${match.match_id}-${teamId}`">
                    {{ teamName(teamId) }}
                  </div>
                  <div class="small text-muted mt-1">
                    winner: {{ match.advanced_team_ids.map((teamId) => teamName(teamId)).join(', ') || '—' }}
                  </div>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="agp-card-soft p-3">
            <div class="fw-semibold mb-2">Multi-team elimination node</div>
            <div class="small text-muted mb-2">
              Для текущего формата основной bracket не является бинарным (match_size={{ competition.match_size }}, top_k={{ competition.advancement_top_k }}).
            </div>
            <div class="d-flex flex-column gap-2">
              <div
                v-for="round in competition.rounds"
                :key="`multi-round-${round.round_index}`"
                class="bg-white border rounded-3 p-2"
              >
                <div class="fw-semibold small mb-1">Round {{ round.round_index }}</div>
                <div v-for="match in round.matches" :key="`multi-node-${match.match_id}`" class="border rounded-2 p-2 mb-2">
                  <div class="mono small fw-semibold">{{ match.match_id }}</div>
                  <div class="small text-muted">Qualify top-{{ competition.advancement_top_k }}</div>
                  <div class="small" v-for="teamId in match.team_ids" :key="`multi-node-team-${match.match_id}-${teamId}`">
                    {{ teamName(teamId) }}
                  </div>
                  <div class="small text-muted">
                    advanced: {{ match.advanced_team_ids.map((teamId) => teamName(teamId)).join(', ') || '—' }}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="mt-3">
            <h3 class="h6">Runs (debug view)</h3>
            <table class="table align-middle mb-0">
              <thead>
                <tr>
                  <th>run_id</th>
                  <th>team</th>
                  <th>status</th>
                  <th>reason</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="run in competitionRuns" :key="run.run_id">
                  <td class="mono small">
                    <RouterLink :to="`/runs/${run.run_id}/watch`">{{ run.run_id }}</RouterLink>
                  </td>
                  <td>{{ teamName(run.team_id) }}</td>
                  <td class="mono small">{{ run.status }}</td>
                  <td><RunReasonBadge :reason="run.error_message" /></td>
                  <td class="text-end">
                    <button class="btn btn-sm btn-outline-dark" @click="inspectRunReplay(run.run_id)">
                      Replay
                    </button>
                  </td>
                </tr>
                <tr v-if="competitionRuns.length === 0">
                  <td colspan="5" class="text-muted small">Пока нет запусков competition_match.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </div>

      <article class="agp-card p-3" v-if="inspectedRunId">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Replay Inspector</h2>
          <span class="mono small">run_id={{ inspectedRunId }}</span>
        </div>
        <div v-if="isInspectReplayLoading" class="text-muted small">Загрузка replay...</div>
        <div v-else-if="inspectReplayError" class="text-danger small">{{ inspectReplayError }}</div>
        <div v-else-if="inspectedReplay">
          <div class="small text-muted mb-2">
            frames: <span class="mono">{{ inspectedReplay.frames.length }}</span>
            · events: <span class="mono">{{ inspectedReplay.events.length }}</span>
            · updated_at: <span class="mono">{{ inspectedReplay.updated_at }}</span>
          </div>
          <pre class="mono small mb-0">{{ inspectedReplaySummary }}</pre>
        </div>
        <div v-else class="text-muted small">Replay для выбранного run пока недоступен.</div>
      </article>

      <article class="agp-card p-3">
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
          <div>
            <h2 class="h6 mb-0">Проверка схожести решений</h2>
            <div class="small text-muted">
              Проверяются последние competition snapshot'ы команд по слотам.
            </div>
          </div>
          <div class="d-flex align-items-center gap-2">
            <label class="small text-muted" for="antiplag-threshold">threshold</label>
            <input
              id="antiplag-threshold"
              v-model.number="antiplagThreshold"
              class="form-control form-control-sm mono"
              style="width: 7rem"
              type="number"
              min="0"
              max="1"
              step="0.01"
            />
            <button class="btn btn-sm btn-outline-dark" :disabled="isCheckingAntiplag || !canModerate" @click="runAntiplagiarismCheck">
              {{ isCheckingAntiplag ? 'Проверка...' : 'Проверить' }}
            </button>
          </div>
        </div>

        <table class="table align-middle mb-0">
          <thead>
            <tr>
              <th>team A</th>
              <th>team B</th>
              <th>slot</th>
              <th>similarity</th>
              <th>runs</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="warning in antiplagWarnings" :key="warning.warning_id">
              <td>{{ teamName(warning.team_a_id) }}</td>
              <td>{{ teamName(warning.team_b_id) }}</td>
              <td class="mono small">{{ warning.slot_key }}</td>
              <td class="mono small">{{ warning.similarity.toFixed(4) }}</td>
              <td class="small mono">{{ warning.run_a_id }} / {{ warning.run_b_id }}</td>
            </tr>
            <tr v-if="antiplagWarnings.length === 0">
              <td colspan="5" class="text-muted small">Предупреждений нет. Запустите проверку вручную.</td>
            </tr>
          </tbody>
        </table>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import RunReasonBadge from '../components/RunReasonBadge.vue';
import {
  advanceCompetition,
  checkCompetitionAntiplagiarism,
  createCompetition,
  createTeam,
  patchCompetition,
  resolveCompetitionMatchTie,
  setCompetitionEntrantBan,
  setCompetitionEntrantNotReady,
  getCompetition,
  getRunReplay,
  listCompetitions,
  listCompetitionRuns,
  listGames,
  listTeamsByGame,
  pauseCompetition,
  registerCompetitionTeam,
  unregisterCompetitionTeam,
  finishCompetition,
  startCompetition,
  type StreamEnvelopeDto,
  type AntiplagiarismWarningDto,
  type CompetitionDto,
  type CompetitionRunItemDto,
  type ReplayDto,
  type TeamDto,
  type TieBreakPolicy,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const sessionStore = useSessionStore();
const view = ref<'rounds' | 'bracket'>('rounds');
const competition = ref<CompetitionDto | null>(null);
const teamsByGame = ref<TeamDto[]>([]);
const selectedTeamId = ref('');
const competitionRuns = ref<CompetitionRunItemDto[]>([]);
const inspectedRunId = ref('');
const inspectedReplay = ref<ReplayDto | null>(null);
const inspectReplayError = ref('');
const isInspectReplayLoading = ref(false);
const antiplagWarnings = ref<AntiplagiarismWarningDto[]>([]);
const antiplagThreshold = ref(0.85);
const isLoading = ref(false);
const isCreatingTeam = ref(false);
const isStarting = ref(false);
const isAdvancing = ref(false);
const isChangingStatus = ref(false);
const isCheckingAntiplag = ref(false);
const isSavingDraftSettings = ref(false);
const moderationBusyTeamId = ref<string | null>(null);
const unregisteringTeamId = ref<string | null>(null);
const errorMessage = ref('');
const competitionLiveMode = ref<'idle' | 'sse' | 'polling'>('idle');
const draftTitle = ref('');
const draftTieBreakPolicy = ref<TieBreakPolicy>('manual');
const draftMatchSize = ref(2);
const draftAdvancementTopK = ref(1);
let competitionEventSource: EventSource | null = null;
let competitionPollingHandle: ReturnType<typeof setInterval> | null = null;

const canModerate = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const isBracketPrimaryCompatible = computed(() => {
  if (!competition.value) return false;
  return (
    competition.value.format === 'single_elimination' &&
    competition.value.match_size === 2 &&
    competition.value.advancement_top_k === 1
  );
});

const canRegister = computed(() => {
  if (!competition.value || !selectedTeamId.value) return false;
  if (!canModerate.value) return false;
  if (competition.value.status !== 'draft') return false;
  return !competition.value.entrants.some((entrant) => entrant.team_id === selectedTeamId.value);
});
const canStart = computed(() => {
  if (!competition.value) return false;
  if (!canModerate.value) return false;
  if (competition.value.status !== 'draft' && competition.value.status !== 'paused') return false;
  const ready = competition.value.entrants.filter((entrant) => entrant.ready && !entrant.banned);
  return ready.length >= 2;
});
const canPause = computed(() => canModerate.value && competition.value?.status === 'running' && !isChangingStatus.value);
const canAdvance = computed(() => canModerate.value && competition.value?.status === 'running' && !isAdvancing.value);
const canFinish = computed(
  () =>
    canModerate.value &&
    (competition.value?.status === 'running' || competition.value?.status === 'paused') &&
    !isChangingStatus.value
);
const canSaveDraftSettings = computed(() => {
  if (!competition.value || !canModerate.value) return false;
  if (competition.value.status !== 'draft') return false;
  const titleOk = draftTitle.value.trim().length >= 2;
  const matchSizeOk = Number.isFinite(draftMatchSize.value) && draftMatchSize.value >= 2 && draftMatchSize.value <= 64;
  const topKOk =
    Number.isFinite(draftAdvancementTopK.value) &&
    draftAdvancementTopK.value >= 1 &&
    draftAdvancementTopK.value <= 64 &&
    draftAdvancementTopK.value <= draftMatchSize.value;
  return titleOk && matchSizeOk && topKOk;
});
const inspectedReplaySummary = computed(() => JSON.stringify(inspectedReplay.value?.summary ?? {}, null, 2));
const readyEntrantsCount = computed(() => competition.value?.entrants.filter((entrant) => entrant.ready && !entrant.banned).length ?? 0);
const bannedEntrantsCount = computed(() => competition.value?.entrants.filter((entrant) => entrant.banned).length ?? 0);
const competitionStatusLabel = computed(() => {
  const status = competition.value?.status;
  if (status === 'draft') return 'черновик';
  if (status === 'running') return 'идет';
  if (status === 'paused') return 'пауза';
  if (status === 'finished') return 'завершено';
  return 'не загружено';
});
const competitionStatusToneClass = computed(() => {
  const status = competition.value?.status;
  if (status === 'running') return 'agp-pill--primary';
  if (status === 'paused' || status === 'draft') return 'agp-pill--warning';
  if (status === 'finished') return 'agp-pill--neutral';
  return 'agp-pill--neutral';
});
const competitionLiveLabel = computed(() => {
  if (competitionLiveMode.value === 'sse') return 'stream';
  if (competitionLiveMode.value === 'polling') return 'fallback polling';
  return 'ожидание';
});
const shortVersionId = computed(() => {
  const versionId = competition.value?.game_version_id ?? '';
  return versionId.length > 14 ? `${versionId.slice(0, 8)}…${versionId.slice(-4)}` : versionId;
});

function teamName(teamId: string): string {
  const found = teamsByGame.value.find((item) => item.team_id === teamId);
  return found?.name ?? teamId;
}

function syncSelectedTeam(): void {
  if (!selectedTeamId.value && teamsByGame.value[0]) {
    selectedTeamId.value = teamsByGame.value[0].team_id;
    return;
  }
  if (selectedTeamId.value && !teamsByGame.value.some((item) => item.team_id === selectedTeamId.value)) {
    selectedTeamId.value = teamsByGame.value[0]?.team_id ?? '';
  }
}

function syncDraftSettingsFromCompetition(): void {
  if (!competition.value) return;
  draftTitle.value = competition.value.title;
  draftTieBreakPolicy.value = competition.value.tie_break_policy;
  draftMatchSize.value = competition.value.match_size;
  draftAdvancementTopK.value = competition.value.advancement_top_k;
}

async function ensureCompetitionLoaded(): Promise<void> {
  const competitionIdFromRoute = String(route.params.competitionId || '').trim();
  if (!competitionIdFromRoute) {
    errorMessage.value = 'Не передан competitionId';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';
  try {
    if (competitionIdFromRoute !== 'demo-comp') {
      competition.value = await getCompetition(competitionIdFromRoute);
    } else {
      competition.value = await bootstrapDemoCompetition();
    }
    syncDraftSettingsFromCompetition();
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить соревнование';
  } finally {
    isLoading.value = false;
  }
}

async function bootstrapDemoCompetition(): Promise<CompetitionDto> {
  const existing = await listCompetitions();
  if (existing.length > 0) {
    return existing[0];
  }
  const games = await listGames();
  const candidate = games.find((game) => game.mode !== 'single_task') ?? games[0];
  if (!candidate) {
    throw new Error('В каталоге нет игр для demo-соревнования');
  }
  return createCompetition({
    game_id: candidate.game_id,
    title: `Demo Competition / ${candidate.title}`,
    format: 'single_elimination',
    tie_break_policy: 'manual',
    advancement_top_k: 1,
    match_size: 2,
  });
}

async function refreshCompetitionRelatedData(): Promise<void> {
  if (!competition.value) return;
  competition.value = await getCompetition(competition.value.competition_id);
  syncDraftSettingsFromCompetition();
  teamsByGame.value = await listTeamsByGame(competition.value.game_id);
  competitionRuns.value = await listCompetitionRuns(competition.value.competition_id);
  syncSelectedTeam();
}

async function inspectRunReplay(runId: string): Promise<void> {
  inspectedRunId.value = runId;
  inspectedReplay.value = null;
  inspectReplayError.value = '';
  isInspectReplayLoading.value = true;
  try {
    inspectedReplay.value = await getRunReplay(runId);
  } catch (error) {
    inspectReplayError.value = error instanceof Error ? error.message : 'Replay недоступен';
  } finally {
    isInspectReplayLoading.value = false;
  }
}

function startCompetitionLiveUpdates(competitionId: string): void {
  stopCompetitionLiveUpdates();
  if (typeof EventSource === 'undefined') {
    startCompetitionPolling(competitionId);
    return;
  }
  competitionEventSource = new EventSource(
    `/api/v1/competitions/${encodeURIComponent(competitionId)}/stream?poll_interval_ms=1000`,
  );
  competitionLiveMode.value = 'sse';

  const applyCompetitionSnapshot = async (payload: CompetitionDto | null): Promise<void> => {
    if (!payload) return;
    competition.value = payload;
    syncDraftSettingsFromCompetition();
    teamsByGame.value = await listTeamsByGame(payload.game_id);
    competitionRuns.value = await listCompetitionRuns(payload.competition_id);
    syncSelectedTeam();
  };

  competitionEventSource.addEventListener('agp.update', (event: MessageEvent) => {
    try {
      const envelope = JSON.parse(event.data) as StreamEnvelopeDto<CompetitionDto>;
      if (envelope.channel !== 'competition') return;
      void applyCompetitionSnapshot(envelope.payload ?? null);
    } catch {
      // ignore malformed stream payload
    }
  });

  competitionEventSource.addEventListener('competition', (event: MessageEvent) => {
    try {
      void applyCompetitionSnapshot(JSON.parse(event.data) as CompetitionDto);
    } catch {
      // ignore malformed legacy payload
    }
  });

  const onTerminal = (): void => {
    stopCompetitionLiveUpdates();
  };
  competitionEventSource.addEventListener('agp.terminal', onTerminal);
  competitionEventSource.addEventListener('terminal', onTerminal);

  competitionEventSource.onerror = () => {
    if (competition.value?.status === 'finished') {
      stopCompetitionLiveUpdates();
      return;
    }
    stopCompetitionLiveUpdates();
    startCompetitionPolling(competitionId);
  };
}

function startCompetitionPolling(competitionId: string): void {
  stopCompetitionPolling();
  competitionLiveMode.value = 'polling';
  competitionPollingHandle = setInterval(async () => {
    try {
      competition.value = await getCompetition(competitionId);
      if (competition.value) {
        syncDraftSettingsFromCompetition();
        teamsByGame.value = await listTeamsByGame(competition.value.game_id);
        competitionRuns.value = await listCompetitionRuns(competition.value.competition_id);
        syncSelectedTeam();
      }
      if (competition.value?.status === 'finished') {
        stopCompetitionLiveUpdates();
      }
    } catch {
      // transient polling failures are ignored
    }
  }, 2000);
}

function stopCompetitionPolling(): void {
  if (!competitionPollingHandle) return;
  clearInterval(competitionPollingHandle);
  competitionPollingHandle = null;
}

function stopCompetitionEventStream(): void {
  if (!competitionEventSource) return;
  competitionEventSource.close();
  competitionEventSource = null;
}

function stopCompetitionLiveUpdates(): void {
  stopCompetitionEventStream();
  stopCompetitionPolling();
  competitionLiveMode.value = 'idle';
}

async function createTeamForCompetitionGame(): Promise<void> {
  if (!competition.value) return;
  isCreatingTeam.value = true;
  errorMessage.value = '';
  try {
    const created = await createTeam({
      game_id: competition.value.game_id,
      name: `${sessionStore.nickname} / comp`,
      captain_user_id: sessionStore.nickname,
    });
    await refreshCompetitionRelatedData();
    selectedTeamId.value = created.team_id;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось создать команду';
  } finally {
    isCreatingTeam.value = false;
  }
}

function resetDraftSettings(): void {
  syncDraftSettingsFromCompetition();
}

async function saveDraftSettings(): Promise<void> {
  if (!competition.value || !canModerate.value || competition.value.status !== 'draft') return;
  if (!canSaveDraftSettings.value) return;
  isSavingDraftSettings.value = true;
  errorMessage.value = '';
  try {
    competition.value = await patchCompetition({
      competition_id: competition.value.competition_id,
      title: draftTitle.value,
      tie_break_policy: draftTieBreakPolicy.value,
      match_size: draftMatchSize.value,
      advancement_top_k: draftAdvancementTopK.value,
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось сохранить настройки соревнования';
  } finally {
    isSavingDraftSettings.value = false;
  }
}

async function registerSelectedTeam(): Promise<void> {
  if (!competition.value || !selectedTeamId.value || !canModerate.value) return;
  errorMessage.value = '';
  try {
    competition.value = await registerCompetitionTeam({
      competition_id: competition.value.competition_id,
      team_id: selectedTeamId.value,
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось зарегистрировать команду';
  }
}

async function unregisterEntrant(teamId: string): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  unregisteringTeamId.value = teamId;
  errorMessage.value = '';
  try {
    competition.value = await unregisterCompetitionTeam({
      competition_id: competition.value.competition_id,
      team_id: teamId,
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось снять команду с регистрации';
  } finally {
    unregisteringTeamId.value = null;
  }
}

async function setEntrantNotReady(teamId: string): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  moderationBusyTeamId.value = teamId;
  errorMessage.value = '';
  try {
    competition.value = await setCompetitionEntrantNotReady({
      competition_id: competition.value.competition_id,
      team_id: teamId,
      reason: 'manual moderation',
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось перевести команду в not_ready';
  } finally {
    moderationBusyTeamId.value = null;
  }
}

async function toggleEntrantBan(teamId: string, banned: boolean): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  moderationBusyTeamId.value = teamId;
  errorMessage.value = '';
  try {
    competition.value = await setCompetitionEntrantBan({
      competition_id: competition.value.competition_id,
      team_id: teamId,
      banned,
      reason: banned ? 'manual moderation' : 'ban removed by moderator',
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось изменить бан команды';
  } finally {
    moderationBusyTeamId.value = null;
  }
}

async function startCurrentCompetition(): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  isStarting.value = true;
  errorMessage.value = '';
  try {
    competition.value = await startCompetition({
      competition_id: competition.value.competition_id,
      requested_by: sessionStore.nickname,
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось запустить соревнование';
  } finally {
    isStarting.value = false;
  }
}

async function advanceCurrentCompetition(): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  isAdvancing.value = true;
  errorMessage.value = '';
  try {
    competition.value = await advanceCompetition({
      competition_id: competition.value.competition_id,
      requested_by: sessionStore.nickname,
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось продвинуть соревнование';
  } finally {
    isAdvancing.value = false;
  }
}

async function resolveTieByFirstTeam(roundIndex: number, matchId: string, teamIds: string[]): Promise<void> {
  if (!competition.value || teamIds.length === 0 || !canModerate.value) return;
  errorMessage.value = '';
  try {
    competition.value = await resolveCompetitionMatchTie({
      competition_id: competition.value.competition_id,
      round_index: roundIndex,
      match_id: matchId,
      advanced_team_ids: [teamIds[0]],
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось применить tie-break решение';
  }
}

async function pauseCurrentCompetition(): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  isChangingStatus.value = true;
  errorMessage.value = '';
  try {
    competition.value = await pauseCompetition(competition.value.competition_id);
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось поставить соревнование на паузу';
  } finally {
    isChangingStatus.value = false;
  }
}

async function finishCurrentCompetition(): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  isChangingStatus.value = true;
  errorMessage.value = '';
  try {
    competition.value = await finishCompetition(competition.value.competition_id);
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось завершить соревнование';
  } finally {
    isChangingStatus.value = false;
  }
}

async function runAntiplagiarismCheck(): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  isCheckingAntiplag.value = true;
  errorMessage.value = '';
  try {
    antiplagWarnings.value = await checkCompetitionAntiplagiarism({
      competition_id: competition.value.competition_id,
      similarity_threshold: antiplagThreshold.value,
      min_token_count: 12,
    });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось выполнить antiplagiarism проверку';
  } finally {
    isCheckingAntiplag.value = false;
  }
}

onMounted(async () => {
  await ensureCompetitionLoaded();
  if (competition.value) {
    startCompetitionLiveUpdates(competition.value.competition_id);
  }
});

onUnmounted(() => {
  stopCompetitionLiveUpdates();
});
</script>

<style scoped>
.competition-page {
  gap: 0.9rem;
}

.competition-hero,
.competition-command-center {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.competition-hero {
  background: #f8fafc;
}

.competition-view-toggle {
  flex-shrink: 0;
}

.competition-command-main {
  min-width: 0;
  flex: 1 1 auto;
}

.competition-status-line,
.competition-actions > div {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.competition-actions {
  flex: 0 1 28rem;
}

.competition-stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
}

.competition-stat {
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 1rem;
  background: rgba(248, 250, 252, 0.78);
  padding: 0.75rem;
}

.competition-stat span {
  display: block;
  color: var(--agp-muted);
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.competition-stat strong {
  display: block;
  margin-top: 0.15rem;
  overflow-wrap: anywhere;
}

.competition-warning {
  border: 1px solid rgba(217, 119, 6, 0.26);
  border-radius: 0.9rem;
  background: rgba(255, 251, 235, 0.88);
  color: #8a4b0c;
  padding: 0.65rem 0.8rem;
}

@media (max-width: 1080px) {
  .competition-hero,
  .competition-command-center {
    flex-direction: column;
  }

  .competition-actions {
    flex-basis: auto;
    width: 100%;
  }
}

@media (max-width: 720px) {
  .competition-stat-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
