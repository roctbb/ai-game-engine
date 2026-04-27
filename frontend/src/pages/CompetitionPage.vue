<template>
  <section class="agp-grid competition-page">
    <header class="agp-card p-3 competition-hero">
      <div>
        <p class="competition-kicker mb-1">Соревнование</p>
        <h1 class="h4 mb-1">{{ competition?.title || 'Турнир' }}</h1>
        <p class="text-muted mb-0">Сетка, результаты и победители.</p>
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

    <article v-if="isLoading" class="agp-card p-4">
      <div class="agp-loading-state agp-loading-state--compact">Загрузка соревнования...</div>
    </article>
    <article v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</article>

    <template v-else-if="competition">
      <article class="agp-card p-3 competition-command-center">
        <div class="competition-command-main">
          <div class="competition-status-line">
            <span class="agp-pill" :class="competitionStatusToneClass">{{ competitionStatusLabel }}</span>
            <span v-if="canModerate" class="agp-pill agp-pill--neutral">{{ competition.format }}</span>
            <span v-if="canModerate" class="agp-pill agp-pill--neutral">код: {{ competitionCodePolicyLabel(competition.code_policy) }}</span>
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
              <span>ограничены</span>
              <strong>{{ bannedEntrantsCount }}</strong>
            </div>
            <div class="competition-stat">
              <span>матч</span>
              <strong>{{ competitionMatchBoundsLabel }} · проходят {{ competition.advancement_top_k }}</strong>
            </div>
          </div>
          <div class="small mt-2" v-if="competition.winner_team_ids.length">
            Победители:
            <span class="mono">{{ competition.winner_team_ids.map((teamId) => teamName(teamId)).join(', ') }}</span>
          </div>
        </div>
        <details v-if="canModerate" class="competition-actions">
          <summary>Управление</summary>
          <div class="d-flex gap-2">
            <RouterLink
              v-if="competition"
              class="btn btn-sm btn-outline-secondary"
              :to="`/replays?game_id=${competition.game_id}&run_kind=competition_match`"
            >
              Все повторы игры
            </RouterLink>
            <button class="btn btn-sm btn-outline-secondary" :disabled="isCreatingTeam" @click="createTeamForCompetitionGame">
              {{ isCreatingTeam ? 'Создание...' : 'Создать игрока' }}
            </button>
            <button class="btn btn-sm btn-dark" :disabled="!canRegister" @click="registerSelectedTeam">
              Зарегистрировать
            </button>
            <button class="btn btn-sm btn-outline-primary" :disabled="!canStart" @click="startCurrentCompetition">
              {{ isStarting ? 'Запуск...' : 'Начать' }}
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
        </details>
      </article>

      <article class="agp-card p-3 competition-settings-card" v-if="competition.status === 'draft' && canModerate">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Настройки соревнования</h2>
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
          <div class="col-md-4">
            <label class="form-label small">Название</label>
            <input v-model.trim="draftTitle" class="form-control" />
          </div>
          <div class="col-md-3">
            <label class="form-label small">Разрешение ничьей</label>
            <select v-model="draftTieBreakPolicy" class="form-select mono">
              <option value="manual">Ручное решение</option>
              <option value="shared_advancement">Пропустить всех на границе</option>
            </select>
          </div>
          <div class="col-md-3">
            <label class="form-label small">Политика кода</label>
            <select v-model="draftCodePolicy" class="form-select">
              <option value="locked_on_start">Заблокировать на старте</option>
              <option value="allowed_between_matches">Разрешить между матчами</option>
              <option value="locked_on_registration">Заблокировать при регистрации</option>
            </select>
          </div>
          <div class="col-md-1">
            <label class="form-label small">Игроков</label>
            <input
              v-model.number="draftMatchSize"
              class="form-control mono"
              type="number"
              :min="competition?.min_match_size ?? 2"
              max="64"
            />
          </div>
          <div class="col-md-2">
            <label class="form-label small">Проходят</label>
            <input v-model.number="draftAdvancementTopK" class="form-control mono" type="number" min="1" max="64" />
          </div>
        </div>
        <div class="small text-muted mt-2">
          Число проходящих дальше не может быть больше размера матча.
        </div>
      </article>

      <div class="competition-focus-layout">
        <article class="agp-card p-3 competition-section-card competition-participants-card">
          <h2 class="h6">Участники</h2>
          <label v-if="canModerate" class="form-label small">Игрок для регистрации</label>
          <select v-if="canModerate" v-model="selectedTeamId" class="form-select mb-3">
            <option value="">Выберите игрока</option>
            <option v-for="team in teamsByGame" :key="team.team_id" :value="team.team_id">
              {{ team.name }}
            </option>
          </select>

          <div class="competition-entrant-list">
            <div v-for="entrant in competition.entrants" :key="entrant.team_id" class="competition-entrant-row">
              <div>
                <strong>{{ teamName(entrant.team_id) }}</strong>
                <span v-if="canModerate && entrant.blocker_reason" class="small text-muted">{{ entrant.blocker_reason }}</span>
              </div>
              <span class="agp-pill" :class="entrantStatusToneClass(entrant)">
                {{ entrantStatusLabel(entrant) }}
              </span>
              <div v-if="canModerate" class="competition-entrant-actions">
                    <button
                      class="btn btn-sm btn-outline-warning"
                      :disabled="!canModerate || !entrant.ready || entrant.banned || moderationBusyTeamId === entrant.team_id"
                      @click="setEntrantNotReady(entrant.team_id)"
                    >
                      Снять готовность
                    </button>
                    <button
                      class="btn btn-sm"
                      :class="entrant.banned ? 'btn-outline-success' : 'btn-outline-danger'"
                      :disabled="!canModerate || moderationBusyTeamId === entrant.team_id"
                      @click="toggleEntrantBan(entrant.team_id, !entrant.banned)"
                    >
                      {{ entrant.banned ? 'Разрешить' : 'Заблокировать' }}
                    </button>
                    <button
                      class="btn btn-sm btn-outline-secondary"
                      :disabled="!canModerate || competition.status !== 'draft' || unregisteringTeamId === entrant.team_id"
                      @click="unregisterEntrant(entrant.team_id)"
                    >
                      Убрать
                    </button>
              </div>
            </div>
            <div v-if="competition.entrants.length === 0" class="text-muted small">Пока нет зарегистрированных игроков.</div>
          </div>
        </article>

        <article v-if="competitionLeaderboard.length" class="agp-card p-3 competition-leaderboard competition-side-card">
          <div class="competition-leaderboard-head">
            <div>
              <h2 class="h6 mb-1">Лидерборд</h2>
              <div class="small text-muted">Победы, поражения и очки.</div>
            </div>
            <div v-if="competition.winner_team_ids.length" class="competition-winner-callout">
              <span>Победитель</span>
              <strong>{{ competition.winner_team_ids.map((teamId) => teamName(teamId)).join(', ') }}</strong>
            </div>
          </div>
          <div class="competition-leaderboard-list">
            <div
              v-for="(stat, index) in competitionLeaderboard"
              :key="stat.team_id"
              class="competition-leaderboard-row"
              :class="{ winner: competition.winner_team_ids.includes(stat.team_id) }"
            >
              <span class="competition-leaderboard-place">{{ index + 1 }}</span>
              <div>
                <strong>{{ stat.name }}</strong>
                <span>
                  побед {{ stat.wins }} · поражений {{ stat.losses }} · очков {{ scoreLabel(stat.points) }}
                </span>
              </div>
            </div>
          </div>
        </article>

        <article class="agp-card p-3 competition-section-card competition-rounds-card" v-if="view === 'rounds'">
          <div class="competition-section-title">
            <h2 class="h6 mb-0">Раунды и матчи</h2>
            <span class="small text-muted">{{ competition.rounds.length }} раундов</span>
          </div>
          <div class="d-flex flex-column gap-3">
            <article
              v-for="round in competition.rounds"
              :key="round.round_index"
              class="agp-card-soft p-3"
            >
              <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="fw-semibold">
                  Раунд {{ round.round_index }}
                </div>
                <span class="badge text-bg-light">{{ roundStatusLabel(round.status) }}</span>
              </div>
              <div class="d-flex flex-column gap-3">
                <article v-for="(match, matchIndex) in round.matches" :key="match.match_id" class="competition-match-card">
                  <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
                    <div>
                      <div class="fw-semibold">Матч {{ matchIndex + 1 }}</div>
                      <div class="small text-muted">
                        Проходят дальше: {{ competition.advancement_top_k }} из {{ match.team_ids.length }}
                      </div>
                    </div>
                    <div class="d-flex gap-2 align-items-center">
                      <span class="badge text-bg-light">{{ matchStatusLabel(match.status) }}</span>
                      <RouterLink
                        v-if="matchPrimaryRunId(match)"
                        class="btn btn-sm btn-outline-secondary"
                        :to="`/runs/${matchPrimaryRunId(match)}/watch`"
                      >
                        Открыть матч
                      </RouterLink>
                      <button
                        v-if="canModerate"
                        class="btn btn-sm btn-outline-dark"
                        :disabled="!canModerate || match.status !== 'awaiting_tiebreak'"
                        @click="resolveTieByFirstTeam(round.round_index, match.match_id, match.team_ids)"
                      >
                        Решить ничью
                      </button>
                    </div>
                  </div>
                  <div class="competition-match-players">
                    <div
                      v-for="teamId in match.team_ids"
                      :key="`${match.match_id}-${teamId}`"
                      class="competition-match-player"
                      :class="{ advanced: match.advanced_team_ids.includes(teamId) }"
                    >
                      <div>
                        <strong>{{ teamName(teamId) }}</strong>
                        <span>
                          счет {{ match.scores_by_team[teamId] ?? '—' }}
                          · место {{ match.placements_by_team[teamId] ?? '—' }}
                        </span>
                      </div>
                      <span v-if="match.advanced_team_ids.includes(teamId)" class="competition-advanced-badge">прошел</span>
                    </div>
                    <div v-if="match.team_ids.length === 0" class="text-muted small">В матче пока нет участников.</div>
                  </div>
                  <div class="small text-muted mt-2" v-if="match.tie_break_reason">
                    Требуется решение: <span>{{ match.tie_break_reason }}</span>
                  </div>
                </article>
              </div>
            </article>
            <div class="small text-muted" v-if="competition.rounds.length === 0">
              Раунды пока не созданы.
            </div>
          </div>
        </article>

        <article class="agp-card p-3 competition-section-card competition-rounds-card" v-else>
          <div class="competition-section-title">
            <h2 class="h6 mb-0">Сетка</h2>
            <span class="small text-muted">{{ competition.rounds.length }} раундов</span>
          </div>
          <div v-if="isBracketPrimaryCompatible" class="d-flex gap-3 flex-wrap">
            <article
              v-for="round in competition.rounds"
              :key="`bracket-${round.round_index}`"
              class="competition-bracket-round p-3"
            >
              <div class="fw-semibold mb-2">Раунд {{ round.round_index }}</div>
              <div class="d-flex flex-column gap-2">
                <div
                  v-for="(match, matchIndex) in round.matches"
                  :key="`bnode-${match.match_id}`"
                  class="competition-bracket-node"
                >
                  <div class="small fw-semibold mb-1">Матч {{ matchIndex + 1 }}</div>
                  <div class="small" v-for="teamId in match.team_ids" :key="`bnode-team-${match.match_id}-${teamId}`">
                    {{ teamName(teamId) }}
                  </div>
                  <div class="small text-muted mt-1">
                    победитель: {{ match.advanced_team_ids.map((teamId) => teamName(teamId)).join(', ') || '—' }}
                  </div>
                  <RouterLink
                    v-if="matchPrimaryRunId(match)"
                    class="btn btn-sm btn-outline-secondary mt-2"
                    :to="`/runs/${matchPrimaryRunId(match)}/watch`"
                  >
                    Открыть матч
                  </RouterLink>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="competition-bracket-round p-3">
            <div class="fw-semibold mb-2">Матчи с несколькими участниками</div>
            <div class="small text-muted mb-2">
              Для текущих настроек удобнее смотреть раунды списком.
            </div>
            <div class="d-flex flex-column gap-2">
              <div
                v-for="round in competition.rounds"
                :key="`multi-round-${round.round_index}`"
                class="competition-bracket-node"
              >
                <div class="fw-semibold small mb-1">Раунд {{ round.round_index }}</div>
                <div v-for="(match, matchIndex) in round.matches" :key="`multi-node-${match.match_id}`" class="competition-bracket-node-inner">
                  <div class="small fw-semibold">Матч {{ matchIndex + 1 }}</div>
                  <div class="small text-muted">Проходят дальше: {{ competition.advancement_top_k }}</div>
                  <div class="small" v-for="teamId in match.team_ids" :key="`multi-node-team-${match.match_id}-${teamId}`">
                    {{ teamName(teamId) }}
                  </div>
                  <div class="small text-muted">
                    прошли дальше: {{ match.advanced_team_ids.map((teamId) => teamName(teamId)).join(', ') || '—' }}
                  </div>
                  <RouterLink
                    v-if="matchPrimaryRunId(match)"
                    class="btn btn-sm btn-outline-secondary mt-2"
                    :to="`/runs/${matchPrimaryRunId(match)}/watch`"
                  >
                    Открыть матч
                  </RouterLink>
                </div>
              </div>
            </div>
          </div>
        </article>
      </div>

      <details v-if="canModerate" class="agp-card p-3 competition-section-card competition-admin-details">
        <summary>
          <span>Администрирование и проверки</span>
          <small>{{ competitionRuns.length }} запусков · {{ antiplagWarnings.length }} предупреждений</small>
        </summary>

        <section class="competition-admin-subsection">
        <h2 class="h6">Запуски соревнования</h2>
        <table class="table align-middle mb-0 competition-table">
          <thead>
            <tr>
              <th>Игрок</th>
              <th>Статус</th>
              <th>Причина</th>
              <th>Повтор</th>
              <th>Детали</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in competitionRuns" :key="run.run_id">
              <td>{{ teamName(run.team_id) }}</td>
              <td>{{ runStatusLabel(run.status) }}</td>
              <td><RunReasonBadge :reason="run.error_message" /></td>
              <td>
                <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/runs/${run.run_id}/watch`">
                  Смотреть
                </RouterLink>
              </td>
              <td>
                <details class="small">
                  <summary class="text-muted">Технический ID</summary>
                  <span class="mono small">{{ run.run_id }}</span>
                </details>
              </td>
              <td class="text-end">
                <button class="btn btn-sm btn-outline-dark" @click="inspectRunReplay(run.run_id)">
                  Инспектор
                </button>
              </td>
            </tr>
            <tr v-if="competitionRuns.length === 0">
              <td colspan="6" class="text-muted small">Пока нет запусков соревнования.</td>
            </tr>
          </tbody>
        </table>
        </section>

        <section class="competition-admin-subsection" v-if="inspectedRunId">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Инспектор повтора</h2>
          <details class="small">
            <summary class="text-muted">Технические детали</summary>
            <span class="mono small">{{ inspectedRunId }}</span>
          </details>
        </div>
        <div v-if="isInspectReplayLoading" class="agp-loading-state agp-loading-state--compact">Загрузка повтора...</div>
        <div v-else-if="inspectReplayError" class="text-danger small">{{ inspectReplayError }}</div>
        <div v-else-if="inspectedReplay">
          <div class="small text-muted mb-2">
            кадры: <span class="mono">{{ inspectedReplay.frames.length }}</span>
            · события: <span class="mono">{{ inspectedReplay.events.length }}</span>
            · обновлено: <span class="mono">{{ inspectedReplay.updated_at }}</span>
          </div>
          <section class="competition-replay-summary">
            <div class="fw-semibold mb-2">Сводка повтора</div>
            <pre class="mono small mb-0">{{ inspectedReplaySummary }}</pre>
          </section>
        </div>
        <div v-else class="text-muted small">Повтор для выбранного запуска пока недоступен.</div>
        </section>

        <section class="competition-admin-subsection">
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
          <div>
            <h2 class="h6 mb-0">Проверка схожести решений</h2>
            <div class="small text-muted">Проверка обновляется при появлении новых запусков соревнования.</div>
          </div>
          <div class="d-flex align-items-center gap-2">
            <label class="small text-muted" for="antiplag-threshold">порог</label>
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
              {{ isCheckingAntiplag ? 'Проверка...' : 'Обновить' }}
            </button>
          </div>
        </div>

        <table class="table align-middle mb-0 competition-table">
          <thead>
            <tr>
              <th>Игрок A</th>
              <th>Игрок B</th>
              <th>Роль</th>
              <th>схожесть</th>
              <th>Повторы</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="warning in antiplagWarnings" :key="warning.warning_id">
              <td>{{ teamName(warning.team_a_id) }}</td>
              <td>{{ teamName(warning.team_b_id) }}</td>
              <td class="mono small">{{ warning.slot_key }}</td>
              <td class="mono small">{{ warning.similarity.toFixed(4) }}</td>
              <td>
                <div class="d-flex gap-2 flex-wrap align-items-center">
                  <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/runs/${warning.run_a_id}/watch`">A</RouterLink>
                  <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/runs/${warning.run_b_id}/watch`">B</RouterLink>
                  <details class="small">
                    <summary class="text-muted">Технические ID</summary>
                    <div class="mono small">{{ warning.run_a_id }}</div>
                    <div class="mono small">{{ warning.run_b_id }}</div>
                  </details>
                </div>
              </td>
            </tr>
            <tr v-if="antiplagWarnings.length === 0">
              <td colspan="5" class="text-muted small">Предупреждений нет.</td>
            </tr>
          </tbody>
        </table>
        </section>
      </details>
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
  createTeam,
  patchCompetition,
  resolveCompetitionMatchTie,
  setCompetitionEntrantBan,
  setCompetitionEntrantNotReady,
  getCompetition,
  getRunReplay,
  listCompetitionRuns,
  listTeamsByGame,
  pauseCompetition,
  registerCompetitionTeam,
  unregisterCompetitionTeam,
  finishCompetition,
  startCompetition,
  type StreamEnvelopeDto,
  type AntiplagiarismWarningDto,
  type CompetitionCodePolicy,
  type CompetitionDto,
  type CompetitionEntrantDto,
  type CompetitionMatchDto,
  type CompetitionMatchStatus,
  type CompetitionRoundStatus,
  type CompetitionRunItemDto,
  type ReplayDto,
  type TeamDto,
  type TieBreakPolicy,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

interface CompetitionTeamStatRow {
  team_id: string;
  name: string;
  wins: number;
  losses: number;
  points: number;
}

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
const draftCodePolicy = ref<CompetitionCodePolicy>('locked_on_start');
const draftMatchSize = ref(2);
const draftAdvancementTopK = ref(1);
let competitionEventSource: EventSource | null = null;
let competitionPollingHandle: ReturnType<typeof setInterval> | null = null;
let antiplagRunSignature = '';
let isRefreshingCompetition = false;
let pendingCompetitionRefresh = false;
let pendingCompetitionReload = false;

const canModerate = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const isBracketPrimaryCompatible = computed(() => {
  if (!competition.value) return false;
  return (
    competition.value.format === 'single_elimination' &&
    competition.value.match_size === 2 &&
    competition.value.advancement_top_k === 1
  );
});
const competitionMatchBoundsLabel = computed(() => {
  if (!competition.value) return 'матч';
  const min = competition.value.min_match_size;
  const max = competition.value.match_size;
  return min === max ? `${max} игроков` : `${min}-${max} игроков`;
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
    competition.value?.status === 'completed' &&
    !isChangingStatus.value
);
const canSaveDraftSettings = computed(() => {
  if (!competition.value || !canModerate.value) return false;
  if (competition.value.status !== 'draft') return false;
  const titleOk = draftTitle.value.trim().length >= 2;
  const matchSizeOk =
    Number.isFinite(draftMatchSize.value) &&
    draftMatchSize.value >= (competition.value.min_match_size ?? 2) &&
    draftMatchSize.value <= 64;
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
const competitionLeaderboard = computed<CompetitionTeamStatRow[]>(() => {
  const rows: Record<string, CompetitionTeamStatRow> = {};
  const winnerSet = new Set(competition.value?.winner_team_ids ?? []);
  const ensureRow = (teamId: string) => {
    rows[teamId] ??= {
      team_id: teamId,
      name: teamName(teamId),
      wins: 0,
      losses: 0,
      points: 0,
    };
    return rows[teamId];
  };

  for (const entrant of competition.value?.entrants ?? []) ensureRow(entrant.team_id);
  for (const round of competition.value?.rounds ?? []) {
    for (const match of round.matches) {
      for (const teamId of match.team_ids) {
        const row = ensureRow(teamId);
        row.points += match.scores_by_team[teamId] ?? 0;
        if (!isResolvedCompetitionMatch(match)) continue;
        if (match.advanced_team_ids.includes(teamId)) row.wins += 1;
        else row.losses += 1;
      }
    }
  }

  return Object.values(rows).sort((left, right) => {
    const rightWinner = winnerSet.has(right.team_id) ? 1 : 0;
    const leftWinner = winnerSet.has(left.team_id) ? 1 : 0;
    if (rightWinner !== leftWinner) return rightWinner - leftWinner;
    if (right.wins !== left.wins) return right.wins - left.wins;
    if (right.points !== left.points) return right.points - left.points;
    if (left.losses !== right.losses) return left.losses - right.losses;
    return left.name.localeCompare(right.name);
  });
});
const competitionStatusLabel = computed(() => {
  const status = competition.value?.status;
  if (status === 'draft') return 'черновик';
  if (status === 'running') return 'идет';
  if (status === 'paused') return 'пауза';
  if (status === 'completed') return 'победитель определен';
  if (status === 'finished') return 'завершено';
  return 'не загружено';
});
const competitionStatusToneClass = computed(() => {
  const status = competition.value?.status;
  if (status === 'running') return 'agp-pill--primary';
  if (status === 'completed') return 'agp-pill--success';
  if (status === 'paused' || status === 'draft') return 'agp-pill--warning';
  if (status === 'finished') return 'agp-pill--neutral';
  return 'agp-pill--neutral';
});
const competitionLiveLabel = computed(() => {
  if (competitionLiveMode.value === 'sse') return 'обновляется в реальном времени';
  if (competitionLiveMode.value === 'polling') return 'обновляется периодически';
  return 'ожидает обновления';
});
function teamName(teamId: string): string {
  const found = teamsByGame.value.find((item) => item.team_id === teamId);
  return found?.name ?? teamId;
}

function scoreLabel(value: number): string {
  return value.toFixed(1);
}

function isResolvedCompetitionMatch(match: CompetitionMatchDto): boolean {
  return match.status === 'finished' || match.status === 'auto_advanced' || match.advanced_team_ids.length > 0;
}

function entrantStatusLabel(entrant: CompetitionEntrantDto): string {
  if (entrant.banned) return 'заблокирован';
  if (entrant.ready) return 'готов';
  return 'готовится';
}

function entrantStatusToneClass(entrant: CompetitionEntrantDto): string {
  if (entrant.banned) return 'agp-pill--danger';
  if (entrant.ready) return 'agp-pill--success';
  return 'agp-pill--warning';
}

function roundStatusLabel(status: CompetitionRoundStatus): string {
  if (status === 'running') return 'идет';
  if (status === 'finished') return 'завершен';
  return status;
}

function matchStatusLabel(status: CompetitionMatchStatus): string {
  if (status === 'pending') return 'ожидает';
  if (status === 'running') return 'идет';
  if (status === 'finished') return 'завершен';
  if (status === 'awaiting_tiebreak') return 'ничья';
  if (status === 'auto_advanced') return 'без матча';
  return status;
}

function matchPrimaryRunId(match: CompetitionMatchDto): string {
  for (const teamId of match.team_ids) {
    const runId = match.run_ids_by_team[teamId];
    if (runId) return runId;
  }
  return Object.values(match.run_ids_by_team)[0] ?? '';
}

function runStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    created: 'Создан',
    queued: 'В очереди',
    running: 'Выполняется',
    finished: 'Завершен',
    failed: 'Ошибка',
    timeout: 'Таймаут',
    canceled: 'Остановлен',
  };
  return labels[status] ?? status;
}

function competitionCodePolicyLabel(policy: CompetitionCodePolicy): string {
  if (policy === 'locked_on_registration') return 'с регистрации';
  if (policy === 'allowed_between_matches') return 'между матчами';
  return 'со старта';
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
  draftCodePolicy.value = competition.value.code_policy;
  draftMatchSize.value = competition.value.match_size;
  draftAdvancementTopK.value = competition.value.advancement_top_k;
}

async function ensureCompetitionLoaded(): Promise<void> {
  const competitionIdFromRoute = String(route.params.competitionId || '').trim();
  if (!competitionIdFromRoute) {
    errorMessage.value = 'Не найдено соревнование для просмотра';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';
  try {
    if (competitionIdFromRoute === 'demo-comp') {
      errorMessage.value = 'Соревнование создается и запускается из лобби.';
      return;
    }
    competition.value = await getCompetition(competitionIdFromRoute);
    syncDraftSettingsFromCompetition();
    await refreshCompetitionRelatedData({ reloadCompetition: false });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить соревнование';
  } finally {
    isLoading.value = false;
  }
}

async function refreshCompetitionRelatedData(options: { reloadCompetition?: boolean } = {}): Promise<void> {
  if (!competition.value) return;
  const reloadCompetition = options.reloadCompetition !== false;
  if (isRefreshingCompetition) {
    pendingCompetitionRefresh = true;
    pendingCompetitionReload = pendingCompetitionReload || reloadCompetition;
    return;
  }
  let shouldReloadCompetition = reloadCompetition;
  isRefreshingCompetition = true;
  try {
    do {
      pendingCompetitionRefresh = false;
      shouldReloadCompetition = shouldReloadCompetition || pendingCompetitionReload;
      pendingCompetitionReload = false;
      if (!competition.value) return;
      const competitionId: string = competition.value.competition_id;
      const nextCompetition: CompetitionDto = shouldReloadCompetition ? await getCompetition(competitionId) : competition.value;
      shouldReloadCompetition = false;
      if (competition.value?.competition_id !== competitionId) return;
      competition.value = nextCompetition;
      syncDraftSettingsFromCompetition();
      teamsByGame.value = await listTeamsByGame(nextCompetition.game_id);
      if (competition.value?.competition_id !== competitionId) return;
      competitionRuns.value = await listCompetitionRuns(nextCompetition.competition_id);
      if (competition.value?.competition_id !== competitionId) return;
      syncSelectedTeam();
      await refreshAntiplagiarismWarnings({ silent: true });
    } while (pendingCompetitionRefresh);
  } finally {
    isRefreshingCompetition = false;
  }
}

async function inspectRunReplay(runId: string): Promise<void> {
  inspectedRunId.value = runId;
  inspectedReplay.value = null;
  inspectReplayError.value = '';
  isInspectReplayLoading.value = true;
  try {
    inspectedReplay.value = await getRunReplay(runId);
  } catch (error) {
    inspectReplayError.value = error instanceof Error ? error.message : 'Повтор недоступен';
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
    `/api/v1/competitions/${encodeURIComponent(competitionId)}/stream?poll_interval_ms=1000&session_id=${encodeURIComponent(sessionStore.sessionId)}`,
  );
  competitionLiveMode.value = 'sse';

  const applyCompetitionSnapshot = async (payload: CompetitionDto | null): Promise<void> => {
    if (!payload) return;
    competition.value = payload;
    syncDraftSettingsFromCompetition();
    await refreshCompetitionRelatedData({ reloadCompetition: false });
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
      if (!competition.value || competition.value.competition_id !== competitionId) {
        competition.value = await getCompetition(competitionId);
      }
      await refreshCompetitionRelatedData();
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
      name: `Игрок ${sessionStore.nickname}`,
      captain_user_id: sessionStore.nickname,
    });
    await refreshCompetitionRelatedData();
    selectedTeamId.value = created.team_id;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось создать игрока';
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
      code_policy: draftCodePolicy.value,
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
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось зарегистрировать игрока';
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
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось снять игрока с регистрации';
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
      reason: 'готовность снята преподавателем',
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось перевести игрока в статус подготовки';
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
      reason: banned ? 'заблокировано преподавателем' : 'ограничение снято преподавателем',
    });
    await refreshCompetitionRelatedData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось изменить бан игрока';
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
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось применить решение по ничьей';
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

function currentAntiplagiarismSignature(): string {
  return [
    antiplagThreshold.value,
    ...competitionRuns.value
      .map((run) => `${run.run_id}:${run.team_id}:${run.status}`)
      .sort((left, right) => left.localeCompare(right)),
  ].join('|');
}

async function refreshAntiplagiarismWarnings(options: { force?: boolean; silent?: boolean } = {}): Promise<void> {
  if (!competition.value || !canModerate.value) return;
  const signature = currentAntiplagiarismSignature();
  if (!options.force && signature === antiplagRunSignature) return;
  if (!options.silent) {
    isCheckingAntiplag.value = true;
    errorMessage.value = '';
  }
  try {
    antiplagWarnings.value = await checkCompetitionAntiplagiarism({
      competition_id: competition.value.competition_id,
      similarity_threshold: antiplagThreshold.value,
      min_token_count: 12,
    });
    antiplagRunSignature = signature;
  } catch (error) {
    if (!options.silent) {
      errorMessage.value = error instanceof Error ? error.message : 'Не удалось выполнить проверку схожести';
    }
  } finally {
    if (!options.silent) {
      isCheckingAntiplag.value = false;
    }
  }
}

async function runAntiplagiarismCheck(): Promise<void> {
  await refreshAntiplagiarismWarnings({ force: true });
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
  gap: 0.75rem;
}

.competition-hero,
.competition-command-center {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.competition-hero {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 12% 18%, rgba(20, 184, 166, 0.18), transparent 15rem),
    radial-gradient(circle at 88% 12%, rgba(245, 158, 11, 0.16), transparent 14rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.9)),
    url("data:image/svg+xml,%3Csvg width='184' height='112' viewBox='0 0 184 112' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.14' stroke-width='2'%3E%3Cpath d='M20 20h32v24H20zM76 20h32v24H76zM132 20h32v24h-32zM48 70h32v24H48zM104 70h32v24h-32z'/%3E%3Cpath d='M52 32h24M108 32h24M92 44v26M80 82h24'/%3E%3C/g%3E%3C/svg%3E");
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.competition-hero h1 {
  line-height: 1.15;
}

.competition-hero::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.25rem;
  background: linear-gradient(90deg, #14b8a6, #f59e0b, #2563eb);
}

.competition-hero > * {
  position: relative;
}

.competition-kicker {
  color: #0f766e;
  font-size: 0.74rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.competition-view-toggle {
  flex-shrink: 0;
}

.competition-view-toggle .btn {
  border-radius: 999px;
  font-weight: 800;
}

.competition-view-toggle .btn.active {
  background: #0f766e;
  border-color: #0f766e;
  color: #fff;
}

.competition-command-center,
.competition-section-card,
.competition-settings-card,
.competition-leaderboard {
  position: relative;
  overflow: hidden;
}

.competition-command-center {
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.12), transparent 14rem),
    linear-gradient(180deg, #ffffff, #f8fafc);
  align-items: center;
}

.competition-section-card::before,
.competition-settings-card::before,
.competition-leaderboard::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.18rem;
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.72), rgba(37, 99, 235, 0.5), transparent);
}

.competition-section-card > *,
.competition-settings-card > *,
.competition-leaderboard > * {
  position: relative;
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
  flex: 0 0 auto;
}

.competition-actions summary,
.competition-admin-details > summary {
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.competition-actions summary::-webkit-details-marker,
.competition-admin-details > summary::-webkit-details-marker {
  display: none;
}

.competition-actions summary {
  border: 1px solid var(--agp-border);
  border-radius: 999px;
  background: #fff;
  padding: 0.45rem 0.8rem;
  color: var(--agp-text);
  font-weight: 800;
}

.competition-actions[open] summary {
  margin-bottom: 0.65rem;
}

.competition-focus-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 24rem);
  gap: 0.75rem;
  align-items: start;
}

.competition-rounds-card {
  grid-column: 1;
  grid-row: 1 / span 3;
}

.competition-participants-card,
.competition-side-card {
  grid-column: 2;
}

.competition-section-title {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.competition-entrant-list,
.competition-match-players {
  display: grid;
  gap: 0.5rem;
}

.competition-entrant-row,
.competition-match-player {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 0.85rem;
  background: rgba(255, 255, 255, 0.82);
  padding: 0.65rem;
}

.competition-entrant-row {
  display: grid;
  gap: 0.5rem;
}

.competition-entrant-row > div:first-child,
.competition-match-player > div {
  min-width: 0;
  display: grid;
  gap: 0.12rem;
}

.competition-entrant-row strong,
.competition-match-player strong {
  overflow-wrap: anywhere;
}

.competition-entrant-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.competition-match-player {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.competition-match-player span:not(.competition-advanced-badge) {
  color: var(--agp-text-muted);
  font-size: 0.82rem;
}

.competition-match-player.advanced {
  border-color: rgba(20, 184, 166, 0.45);
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.14), transparent 7rem),
    rgba(240, 253, 250, 0.9);
}

.competition-advanced-badge {
  border-radius: 999px;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-size: 0.74rem;
  font-weight: 850;
  padding: 0.2rem 0.55rem;
}

.competition-stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
}

.competition-stat {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 1rem;
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.1), transparent 6rem),
    rgba(248, 250, 252, 0.88);
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

.competition-leaderboard {
  display: grid;
  gap: 0.75rem;
}

.competition-leaderboard-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.competition-winner-callout {
  border: 1px solid rgba(20, 184, 166, 0.24);
  border-radius: 0.65rem;
  background: rgba(204, 251, 241, 0.5);
  padding: 0.45rem 0.65rem;
  display: grid;
  gap: 0.05rem;
  min-width: 12rem;
}

.competition-winner-callout span {
  color: var(--agp-text-muted);
  font-size: 0.74rem;
  font-weight: 800;
  text-transform: uppercase;
}

.competition-leaderboard-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.5rem;
}

.competition-side-card .competition-leaderboard-list {
  grid-template-columns: 1fr;
}

.competition-leaderboard-row {
  border: 1px solid var(--agp-border);
  border-radius: 0.75rem;
  background:
    radial-gradient(circle at 100% 0%, rgba(37, 99, 235, 0.06), transparent 6rem),
    #fff;
  padding: 0.55rem 0.65rem;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.5rem;
  align-items: center;
}

.competition-leaderboard-row.winner {
  border-color: rgba(20, 184, 166, 0.42);
  background:
    radial-gradient(circle at 100% 0%, rgba(245, 158, 11, 0.14), transparent 6rem),
    rgba(240, 253, 250, 0.9);
}

.competition-leaderboard-row > div {
  display: grid;
  gap: 0.05rem;
  min-width: 0;
}

.competition-leaderboard-row span:not(.competition-leaderboard-place) {
  color: var(--agp-text-muted);
  font-size: 0.8rem;
}

.competition-leaderboard-place {
  width: 1.65rem;
  height: 1.65rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-weight: 850;
  font-size: 0.78rem;
}

.competition-replay-summary {
  border: 1px solid var(--agp-border);
  border-radius: 8px;
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.12), transparent 10rem),
    var(--agp-surface-soft);
  padding: 0.85rem;
}

.competition-replay-summary pre {
  max-height: 18rem;
  overflow: auto;
  white-space: pre-wrap;
}

.competition-table {
  --bs-table-bg: transparent;
  --bs-table-striped-bg: rgba(248, 250, 252, 0.82);
  border-color: rgba(148, 163, 184, 0.24);
}

.competition-table thead th {
  color: var(--agp-text-muted);
  font-size: 0.74rem;
  font-weight: 850;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.competition-table--compact {
  font-size: 0.86rem;
}

.competition-match-card,
.competition-bracket-node,
.competition-bracket-node-inner {
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 0.85rem;
  background:
    radial-gradient(circle at 100% 0%, rgba(37, 99, 235, 0.07), transparent 7rem),
    #ffffff;
}

.competition-match-card {
  padding: 0.85rem;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
}

.competition-admin-details {
  background:
    radial-gradient(circle at 100% 0%, rgba(15, 23, 42, 0.05), transparent 13rem),
    #fff;
}

.competition-admin-details > summary {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  font-weight: 850;
}

.competition-admin-details > summary small {
  color: var(--agp-text-muted);
  font-weight: 700;
}

.competition-admin-details[open] > summary {
  margin-bottom: 0.9rem;
}

.competition-admin-subsection {
  border-top: 1px solid rgba(148, 163, 184, 0.22);
  padding-top: 0.85rem;
  margin-top: 0.85rem;
}

.competition-admin-subsection:first-of-type {
  border-top: 0;
  padding-top: 0;
  margin-top: 0;
}

.competition-bracket-round {
  min-width: 18rem;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 1rem;
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.1), transparent 8rem),
    #f8fafc;
}

.competition-bracket-node {
  padding: 0.65rem;
}

.competition-bracket-node-inner {
  padding: 0.65rem;
  margin-bottom: 0.5rem;
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

  .competition-focus-layout {
    grid-template-columns: 1fr;
  }

  .competition-rounds-card,
  .competition-participants-card,
  .competition-side-card {
    grid-column: auto;
    grid-row: auto;
  }

  .competition-rounds-card {
    order: 1;
  }

  .competition-side-card {
    order: 2;
  }

  .competition-participants-card {
    order: 3;
  }
}

@media (max-width: 720px) {
  .competition-stat-grid {
    grid-template-columns: 1fr 1fr;
  }

  .competition-view-toggle {
    width: 100%;
  }

  .competition-view-toggle .btn {
    flex: 1 1 0;
  }
}

@media (max-width: 520px) {
  .competition-stat-grid,
  .competition-leaderboard-list {
    grid-template-columns: 1fr;
  }
}
</style>
