<template>
  <section class="agp-grid lobby-page" :class="{ 'lobby-page--game': activeTab === 'game' }">
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
        <button
          v-if="canManage && canCloseLobby"
          class="btn btn-sm btn-outline-danger"
          :disabled="isBusy"
          @click="closeLobby"
        >
          Закрыть лобби
        </button>
      </div>
      <div v-else-if="lobby && canManage" class="lobby-head-actions">
        <button class="btn btn-outline-secondary" :disabled="!canJoinAsPlayer || isBusy" @click="joinAsPlayer">
          {{ isBusy ? '...' : 'Участвовать как игрок' }}
        </button>
        <button
          v-if="canCloseLobby"
          class="btn btn-sm btn-outline-danger"
          :disabled="isBusy"
          @click="closeLobby"
        >
          Закрыть лобби
        </button>
      </div>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>
    <article v-if="isLoading" class="agp-card p-4">
      <div class="agp-loading-state agp-loading-state--compact">Загрузка лобби...</div>
    </article>

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
          <div class="lobby-roles-head">
            <div>
              <strong>Роли</strong>
              <span>{{ filledRequiredSlots }}/{{ requiredSlotCount }} обязательных</span>
            </div>
            <div class="lobby-role-progress" aria-hidden="true">
              <i :style="{ width: `${roleProgressPercent}%` }"></i>
            </div>
          </div>
          <button
            v-for="slot in slotStates"
            :key="slot.slot_key"
            class="lobby-role-button"
            :class="{ active: activeSlotKey === slot.slot_key, filled: Boolean(slot.code?.trim()), required: slot.required }"
            @click="selectSlot(slot.slot_key)"
          >
            <span>
              <i aria-hidden="true"></i>
              {{ slot.slot_key }}
            </span>
            <small>{{ slot.code?.trim() ? 'заполнено' : slot.required ? 'нужно заполнить' : 'необязательная' }}</small>
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
              <p class="small mb-0">{{ codeStateLabel }}</p>
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
            <strong class="mono">{{ allTrainingMatchGroups.length }}</strong>
          </div>
        </article>

        <div class="lobby-main-stack">
          <article class="agp-card p-3 lobby-participants-card">
            <h2 class="h6 mb-3">Участники</h2>
            <div class="lobby-participant-columns">
              <ParticipantColumn title="Играют" :team-ids="lobby.playing_team_ids" :stats="statsByTeam" empty="Сейчас никто не играет" />
              <ParticipantColumn title="В очереди" :team-ids="lobby.queued_team_ids" :stats="statsByTeam" empty="Очередь пуста" />
              <ParticipantColumn title="Готовятся" :team-ids="preparingTeamIds" :stats="statsByTeam" empty="Все уже готовы" />
            </div>
          </article>

          <article class="agp-card p-3 lobby-matches-card">
            <header class="lobby-section-head">
              <div>
                <h2 class="h6 mb-1">Матчи</h2>
                <p class="small text-muted mb-0">Последние игры в этом лобби.</p>
              </div>
              <span class="lobby-count-pill">{{ allTrainingMatchGroups.length }} всего</span>
            </header>
            <div class="lobby-match-list">
              <article
                v-for="group in pagedTrainingMatchGroups"
                :key="group.group_id"
                class="lobby-match-group"
                :class="{ muted: group.archived }"
              >
                <header>
                  <div>
                    <span>{{ group.archived ? 'Архивный матч' : 'Текущий матч' }}</span>
                    <strong>{{ matchGroupTeamIds(group).length }} {{ pluralizePlayers(matchGroupTeamIds(group).length) }}</strong>
                  </div>
                  <RouterLink
                    class="btn btn-sm btn-outline-secondary"
                    :to="`/runs/${primaryRunId(group)}/watch`"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click.stop
                  >
                    Смотреть
                  </RouterLink>
                </header>
                <div class="lobby-match-meta">
                  <span>{{ formatMatchDate(group) }}</span>
                  <span>Победитель: <strong>{{ matchWinnerLabel(group) }}</strong></span>
                </div>
                <div class="lobby-run-links">
                  <RouterLink
                    v-for="teamId in matchGroupTeamIds(group)"
                    :key="`${group.group_id}-${teamId}`"
                    class="btn btn-sm btn-outline-secondary"
                    :to="`/runs/${runIdForTeamInGroup(group, teamId)}/watch`"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click.stop
                  >
                    {{ teamLabel(teamId) }}
                  </RouterLink>
                </div>
              </article>
              <div v-if="!allTrainingMatchGroups.length" class="agp-empty-state agp-empty-state--compact">
                Матчей пока нет.
              </div>
            </div>
            <footer v-if="matchPageCount > 1" class="lobby-match-pagination">
              <button class="btn btn-sm btn-outline-secondary" :disabled="matchPage === 1" @click="matchPage -= 1">
                Назад
              </button>
              <span class="small text-muted">Страница {{ matchPage }} из {{ matchPageCount }}</span>
              <button class="btn btn-sm btn-outline-secondary" :disabled="matchPage === matchPageCount" @click="matchPage += 1">
                Вперед
              </button>
            </footer>
          </article>
        </div>

        <aside class="lobby-side-stack">
          <article class="agp-card p-3">
            <h2 class="h6 mb-3">Лидерборд</h2>
            <div v-if="lobbyLeaderboard.length" class="lobby-leaderboard-list">
              <div v-for="(stat, index) in lobbyLeaderboard" :key="stat.team_id" class="lobby-leaderboard-row">
                <span class="lobby-leaderboard-place">{{ index + 1 }}</span>
                <div>
                  <strong>{{ stat.display_name }}</strong>
                  <span>
                    побед {{ stat.wins }} · игр {{ stat.matches_total }} · средний счет {{ averageScoreLabel(stat.average_score) }}
                  </span>
                </div>
              </div>
            </div>
            <div v-else class="agp-empty-state agp-empty-state--compact">Статистика появится после первых матчей.</div>
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
        <article class="lobby-game-view">
          <iframe
            v-if="displayedGameRunId"
            :src="`/runs/${displayedGameRunId}/watch?embed=1&autoplay=1&speed_ms=500`"
            title="Текущая игра"
          ></iframe>
          <div v-if="isGameFinishedPhase" class="lobby-game-finished-overlay">
            <div class="lobby-game-finished-card">
              <strong>Игра завершена</strong>
              <span>Победитель: {{ currentGameLeaderLabel }}</span>
              <small>Ожидайте следующей игры</small>
            </div>
          </div>
          <div v-if="!displayedGameRunId" class="lobby-empty">
            <h2 class="h6">Текущей игры пока нет</h2>
            <p class="small text-muted mb-0">Заполните код и нажмите Play. Изменения попадут в следующую игру.</p>
          </div>
        </article>
        <aside class="lobby-game-stats">
          <header class="lobby-game-stats-head">
            <div>
              <h2 class="h6 mb-1">Матч</h2>
              <span>{{ currentGamePhaseLabel }}</span>
            </div>
            <strong>{{ currentGameFrameLabel }}</strong>
          </header>

          <div class="lobby-game-mini-stats">
            <div>
              <span>Лидер</span>
              <strong>{{ currentGameLeaderLabel }}</strong>
            </div>
            <div>
              <span>Игроков</span>
              <strong>{{ currentGameStats.length || '—' }}</strong>
            </div>
          </div>

          <div v-if="currentGameStats.length" class="lobby-stats-list lobby-game-scoreboard">
            <article
              v-for="stat in currentGameStats"
              :key="`${stat.run_id}-${stat.team_id}`"
              class="lobby-stat-row"
              :class="{ 'lobby-stat-row--self': stat.isSelf }"
            >
              <div class="lobby-stat-title">
                <strong>{{ stat.display_name }}</strong>
                <span>{{ stat.status }}</span>
              </div>
              <div class="lobby-stat-score">{{ stat.score }}</div>
              <div class="lobby-stat-bars">
                <span><i :style="{ width: `${stat.lifePercent}%` }"></i></span>
                <span><i :style="{ width: `${stat.shieldPercent}%` }"></i></span>
              </div>
              <small v-if="stat.meta">{{ stat.meta }}</small>
            </article>
          </div>
          <div v-else class="lobby-game-empty-stat">Статистика появится, когда начнется матч.</div>
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
        <div v-if="competitionTeamStats.length" class="lobby-competition-leaderboard mt-3">
          <h3 class="h6 mb-0">Итоги команд</h3>
          <div class="lobby-competition-stat-list">
            <div v-for="stat in competitionTeamStats" :key="stat.team_id" class="lobby-competition-stat-row">
              <strong>{{ stat.name }}</strong>
              <span>побед {{ stat.wins }} · поражений {{ stat.losses }} · очков {{ scoreLabel(stat.points) }}</span>
            </div>
          </div>
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
                <div class="d-flex align-items-center gap-2 flex-wrap">
                  <span class="small text-muted">{{ competitionMatchStatusLabel(effectiveCompetitionMatchStatus(match)) }}</span>
                  <RouterLink
                    v-if="matchPrimaryRunId(match)"
                    class="btn btn-sm btn-outline-secondary"
                    :to="`/runs/${matchPrimaryRunId(match)}/watch`"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Смотреть
                  </RouterLink>
                </div>
              </div>
              <div class="lobby-competition-team-rows">
                <div
                  v-for="teamId in match.team_ids"
                  :key="`${match.match_id}-${teamId}`"
                  class="lobby-competition-team-row"
                  :class="{ winner: match.advanced_team_ids.includes(teamId), loser: isCompetitionMatchLoser(match, teamId) }"
                >
                  <strong>{{ teamLabel(teamId) }}</strong>
                  <span>{{ competitionTeamMatchSummary(match, teamId) }}</span>
                </div>
              </div>
              <div v-if="match.tie_break_reason" class="small text-warning">{{ match.tie_break_reason }}</div>
            </article>
          </section>
        </div>
        <div v-else class="agp-empty-state agp-empty-state--compact mt-3">Сетка появится после старта первого раунда.</div>
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
            <span>
              <strong>{{ cleanCompetitionTitle(item.title) }}</strong>
              <small class="text-muted">
                Победитель: {{ archiveCompetitionWinnerLabel(item) }}
              </small>
            </span>
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
  setLobbyStatus,
  startLobbyCompetition,
  stopLobby,
  updateSlotCode,
  type CompetitionCodePolicy,
  type CompetitionDto,
  type CompetitionMatchDto,
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
          : h('div', { class: 'lobby-column-empty' }, props.empty),
      ]);
  },
});

interface TrainingRunLink {
  run_id: string;
  team_id: string;
}

interface TrainingMatchGroup {
  group_id: string;
  archived: boolean;
  runs: TrainingRunLink[];
}

interface CurrentGameStatRow {
  run_id: string;
  team_id: string;
  display_name: string;
  status: string;
  score: string;
  scoreValue: number | null;
  lifePercent: number;
  shieldPercent: number;
  meta: string;
  isSelf: boolean;
}

interface EmbeddedGameFrame {
  runId: string;
  status: RunDto['status'];
  tick: number;
  phase: string;
  frame: Record<string, unknown>;
  replayFrameIndex: number;
  replayFrameCount: number;
}

interface CompetitionTeamStatRow {
  team_id: string;
  name: string;
  wins: number;
  losses: number;
  points: number;
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
const matchPage = ref(1);
const matchesPerPage = 5;
const embeddedGameFrame = ref<EmbeddedGameFrame | null>(null);
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
const roleProgressPercent = computed(() =>
  requiredSlotCount.value ? Math.round((filledRequiredSlots.value / requiredSlotCount.value) * 100) : 0
);
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
  if (isGameFinishedPhase.value && lobby.value?.my_status === 'queued') return 'Показ реплея';
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
  if (isGameFinishedPhase.value && lobby.value?.my_status === 'queued') return 'Система дожидается окончания реплея перед следующей игрой.';
  if (lobby.value?.my_status === 'queued') return 'Матч начнется автоматически, когда найдутся соперники.';
  if (codeLockedByCompetition.value) return 'Политика соревнования запрещает менять код.';
  if (isDirty.value) return 'Сохраните код, чтобы встать в очередь.';
  if (requiredSlotCount.value === 0) return 'Игра не описала обязательные роли.';
  if (filledRequiredSlots.value < requiredSlotCount.value) {
    return `Заполнено ${filledRequiredSlots.value} из ${requiredSlotCount.value} обязательных ролей.`;
  }
  return 'Нажмите “Готов”, чтобы встать в очередь.';
});
const currentCompetitionMatch = computed(() => {
  const competition = activeCompetition.value;
  const myTeamId = lobby.value?.my_team_id ?? '';
  if (!competition || !myTeamId) return null;
  const currentRound = competition.rounds.find((round) => round.round_index === competition.current_round_index);
  return currentRound?.matches.find(
    (match) =>
      effectiveCompetitionMatchStatus(match) === 'running' &&
      match.team_ids.includes(myTeamId) &&
      Boolean(match.run_ids_by_team[myTeamId]),
  ) ?? null;
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
  if (currentCompetitionMatch.value) return currentCompetitionMatch.value.run_ids_by_team[myTeamId] ?? '';
  return '';
});
const currentGameRunId = computed(() => currentCompetitionRunId.value || lobby.value?.current_run_id || '');
const displayedGameRunId = computed(() => currentGameRunId.value || (activeCompetition.value ? '' : lastGameRunId.value));
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
const competitionRunsById = computed(() => {
  const result: Record<string, CompetitionRunItemDto> = {};
  for (const run of competitionRuns.value) result[run.run_id] = run;
  return result;
});
const currentTrainingMatchGroups = computed(() =>
  buildTrainingMatchGroups(lobby.value?.current_run_ids ?? [], false)
);
const archivedTrainingMatchGroups = computed(() =>
  buildTrainingMatchGroups(lobby.value?.archived_run_ids ?? [], true)
);
const allTrainingMatchGroups = computed(() => [
  ...currentTrainingMatchGroups.value,
  ...archivedTrainingMatchGroups.value,
]);
const matchPageCount = computed(() =>
  Math.max(1, Math.ceil(allTrainingMatchGroups.value.length / matchesPerPage))
);
const pagedTrainingMatchGroups = computed(() => {
  const start = (matchPage.value - 1) * matchesPerPage;
  return allTrainingMatchGroups.value.slice(start, start + matchesPerPage);
});
watch(matchPageCount, (pageCount) => {
  if (matchPage.value > pageCount) matchPage.value = pageCount;
});
watch(allTrainingMatchGroups, () => {
  if (matchPage.value < 1) matchPage.value = 1;
  if (matchPage.value > matchPageCount.value) matchPage.value = matchPageCount.value;
});
const displayedTrainingRunIds = computed(() => {
  if (!displayedGameRunId.value) return [];
  const group = allTrainingMatchGroups.value
    .find((item) => item.runs.some((run) => run.run_id === displayedGameRunId.value));
  if (group) return group.runs.map((run) => run.run_id);
  const competitionMatch = currentCompetitionMatch.value;
  if (competitionMatch && Object.values(competitionMatch.run_ids_by_team).includes(displayedGameRunId.value)) {
    return competitionMatch.team_ids
      .map((teamId) => competitionMatch.run_ids_by_team[teamId] ?? '')
      .filter(Boolean);
  }
  return [displayedGameRunId.value];
});
const frameGameStats = computed<CurrentGameStatRow[]>(() => {
  const message = embeddedGameFrame.value;
  if (!message || message.runId !== displayedGameRunId.value) return [];
  const players = collectFrameGamePlayers(message.frame);
  return dedupeCurrentGameStats(players.map((player, index) => buildCurrentGameStatFromFrame(message, player, index)));
});
const currentGameStats = computed<CurrentGameStatRow[]>(() =>
  frameGameStats.value.length
    ? frameGameStats.value
    : displayedTrainingRunIds.value.flatMap((runId) => {
      const trainingRun = trainingRunsById.value[runId];
      if (trainingRun) {
        return [{
          run_id: trainingRun.run_id,
          team_id: trainingRun.team_id,
          display_name: teamLabel(trainingRun.team_id),
          status: runStatusLabel(trainingRun.status),
          score: runScoreLabel(trainingRun),
          scoreValue: extractRunScore(isRecord(trainingRun.result_payload) ? trainingRun.result_payload : {}, trainingRun.team_id),
          lifePercent: 0,
          shieldPercent: 0,
          meta: '',
          isSelf: trainingRun.team_id === lobby.value?.my_team_id,
        }];
      }
      const competitionRun = competitionRunsById.value[runId];
      if (!competitionRun) return [];
      return [{
        run_id: competitionRun.run_id,
        team_id: competitionRun.team_id,
        display_name: teamLabel(competitionRun.team_id),
        status: runStatusLabel(competitionRun.status as RunDto['status']),
        score: 'пока нет',
        scoreValue: null,
        lifePercent: 0,
        shieldPercent: 0,
        meta: '',
        isSelf: competitionRun.team_id === lobby.value?.my_team_id,
      }];
    }),
);
const currentGameFrameLabel = computed(() => {
  const message = embeddedGameFrame.value;
  if (!message || message.runId !== displayedGameRunId.value) return 'кадр —';
  if (message.replayFrameCount > 0) {
    return `кадр ${message.replayFrameIndex + 1}/${message.replayFrameCount}`;
  }
  return `ход ${message.tick}`;
});
const currentGamePhaseLabel = computed(() => {
  const message = embeddedGameFrame.value;
  if (!message || message.runId !== displayedGameRunId.value) {
    return displayedGameRunId.value ? 'ожидаем кадры' : 'нет активной игры';
  }
  return gamePhaseLabel(message.phase, message.status);
});
const isGameFinishedPhase = computed(() => {
  const message = embeddedGameFrame.value;
  if (!message || message.runId !== displayedGameRunId.value) return false;
  if (message.replayFrameCount > 1) return message.replayFrameIndex >= message.replayFrameCount - 1;
  return message.phase === 'finished';
});
const currentGameLeaderLabel = computed(() => {
  const leader = [...currentGameStats.value].sort((left, right) => {
    const rightScore = right.scoreValue ?? Number.NEGATIVE_INFINITY;
    const leftScore = left.scoreValue ?? Number.NEGATIVE_INFINITY;
    return rightScore - leftScore;
  })[0];
  return leader?.display_name ?? '—';
});
const statsByTeam = computed(() => {
  const result: Record<string, LobbyParticipantStatsDto> = {};
  for (const stat of lobby.value?.participant_stats ?? []) result[stat.team_id] = stat;
  return result;
});
const lobbyLeaderboard = computed(() =>
  [...(lobby.value?.participant_stats ?? [])].sort((left, right) => {
    const rightAverage = right.average_score ?? Number.NEGATIVE_INFINITY;
    const leftAverage = left.average_score ?? Number.NEGATIVE_INFINITY;
    if (rightAverage !== leftAverage) return rightAverage - leftAverage;
    if (right.wins !== left.wins) return right.wins - left.wins;
    return right.matches_total - left.matches_total;
  }),
);
const competitionTeamStats = computed<CompetitionTeamStatRow[]>(() => {
  const rows: Record<string, CompetitionTeamStatRow> = {};
  const ensureRow = (teamId: string) => {
    rows[teamId] ??= {
      team_id: teamId,
      name: teamLabel(teamId),
      wins: 0,
      losses: 0,
      points: 0,
    };
    return rows[teamId];
  };

  for (const entrant of activeCompetition.value?.entrants ?? []) ensureRow(entrant.team_id);
  for (const round of activeCompetition.value?.rounds ?? []) {
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
    if (right.wins !== left.wins) return right.wins - left.wins;
    if (right.points !== left.points) return right.points - left.points;
    return left.losses - right.losses;
  });
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

function averageScoreLabel(value: number | null | undefined): string {
  return value === null || value === undefined ? 'нет данных' : value.toFixed(1);
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

function gamePhaseLabel(phase: string, status: RunDto['status']): string {
  const normalized = phase.toLowerCase();
  const labels: Record<string, string> = {
    created: 'создан',
    queued: 'ожидает запуска',
    running: 'игра идет',
    started: 'игра идет',
    playing: 'игра идет',
    finished: 'завершен',
    failed: 'ошибка',
    timeout: 'таймаут',
    canceled: 'остановлен',
  };
  return labels[normalized] ?? runStatusLabel(status);
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

function primaryRunId(group: TrainingMatchGroup): string {
  return group.runs[0]?.run_id ?? '';
}

function matchGroupTeamIds(group: TrainingMatchGroup): string[] {
  return [...new Set(group.runs.map((run) => run.team_id).filter(Boolean))];
}

function runIdForTeamInGroup(group: TrainingMatchGroup, teamId: string): string {
  return group.runs.find((run) => run.team_id === teamId)?.run_id ?? primaryRunId(group);
}

function formatMatchDate(group: TrainingMatchGroup): string {
  const run = group.runs
    .map((item) => trainingRunsById.value[item.run_id])
    .filter(Boolean)
    .sort((left, right) => Date.parse(left.created_at) - Date.parse(right.created_at))[0];
  if (!run?.created_at) return 'время неизвестно';
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(run.created_at));
}

function matchWinnerLabel(group: TrainingMatchGroup): string {
  const winners = matchGroupWinnerIds(group);
  return winners.length ? winners.map(teamLabel).join(', ') : 'не определен';
}

function matchGroupWinnerIds(group: TrainingMatchGroup): string[] {
  const explicitWinners = new Set<string>();
  const placements = new Map<string, number>();
  const scores = new Map<string, number>();

  for (const runLink of group.runs) {
    const run = trainingRunsById.value[runLink.run_id];
    const payload = isRecord(run?.result_payload) ? run.result_payload : {};
    const winners = payload.winners ?? payload.winner;
    if (Array.isArray(winners)) {
      for (const winner of winners) {
        if (typeof winner === 'string' && winner) explicitWinners.add(winner);
      }
    } else if (typeof winners === 'string' && winners) {
      explicitWinners.add(winners);
    }

    const payloadPlacements = isRecord(payload.placements) ? payload.placements : {};
    for (const [teamId, rawPlacement] of Object.entries(payloadPlacements)) {
      if (typeof rawPlacement === 'number' && Number.isFinite(rawPlacement)) {
        placements.set(teamId, Math.min(placements.get(teamId) ?? rawPlacement, rawPlacement));
      }
    }

    const payloadScores = isRecord(payload.scores) ? payload.scores : {};
    for (const [teamId, rawScore] of Object.entries(payloadScores)) {
      if (typeof rawScore === 'number' && Number.isFinite(rawScore)) {
        scores.set(teamId, Math.max(scores.get(teamId) ?? rawScore, rawScore));
      }
    }

    const ownScore = extractRunScore(payload, runLink.team_id);
    if (ownScore !== null && runLink.team_id) {
      scores.set(runLink.team_id, Math.max(scores.get(runLink.team_id) ?? ownScore, ownScore));
    }
  }

  if (explicitWinners.size) return [...explicitWinners];
  if (placements.size) {
    const bestPlacement = Math.min(...placements.values());
    return [...placements.entries()].filter(([, placement]) => placement === bestPlacement).map(([teamId]) => teamId);
  }
  if (scores.size) {
    const bestScore = Math.max(...scores.values());
    return [...scores.entries()].filter(([, score]) => score === bestScore).map(([teamId]) => teamId);
  }
  return [];
}

function matchPrimaryRunId(match: { team_ids: string[]; run_ids_by_team: Record<string, string> }): string {
  for (const teamId of match.team_ids) {
    const runId = match.run_ids_by_team[teamId];
    if (runId) return runId;
  }
  return Object.values(match.run_ids_by_team)[0] ?? '';
}

function runCreatedAtMs(run: { run_id: string }): number {
  const createdAt = trainingRunsById.value[run.run_id]?.created_at;
  const value = createdAt ? Date.parse(createdAt) : NaN;
  return Number.isFinite(value) ? value : 0;
}

function buildTrainingMatchGroups(runIds: string[], archived: boolean): TrainingMatchGroup[] {
  const runs = runIds.map((runId) => ({
    run_id: runId,
    team_id: trainingRunsById.value[runId]?.team_id ?? '',
  })).sort((left, right) => runCreatedAtMs(right) - runCreatedAtMs(left));
  if (game.value?.mode === 'small_match') {
    const groupSize = 2;
    const groups: TrainingMatchGroup[] = [];
    for (let index = 0; index < runs.length; index += groupSize) {
      const groupRuns = runs.slice(index, index + groupSize);
      groups.push({
        group_id: `${archived ? 'archive' : 'current'}-${index}-${groupRuns.map((run) => run.run_id).join('-')}`,
        archived,
        runs: groupRuns,
      });
    }
    return groups;
  }

  const closeCreatedAtMs = 2_000;
  const groups: TrainingMatchGroup[] = [];
  let currentGroup: typeof runs = [];
  for (const run of runs) {
    const previousRun = currentGroup[currentGroup.length - 1];
    const createdAt = runCreatedAtMs(run);
    const previousCreatedAt = previousRun ? runCreatedAtMs(previousRun) : 0;
    if (previousRun && Math.abs(previousCreatedAt - createdAt) > closeCreatedAtMs) {
      groups.push({
        group_id: `${archived ? 'archive' : 'current'}-${groups.length}-${currentGroup.map((item) => item.run_id).join('-')}`,
        archived,
        runs: currentGroup,
      });
      currentGroup = [];
    }
    currentGroup.push(run);
  }
  if (currentGroup.length) {
    groups.push({
      group_id: `${archived ? 'archive' : 'current'}-${groups.length}-${currentGroup.map((item) => item.run_id).join('-')}`,
      archived,
      runs: currentGroup,
    });
  }
  return groups;
}

function cleanCompetitionTitle(title: string): string {
  return title.replace(/^\[lobby:[^\]]+\]\s*/, '');
}

function archiveCompetitionWinnerLabel(item: LobbyCompetitionDto): string {
  return item.winner_team_ids.length ? item.winner_team_ids.map(teamLabel).join(', ') : 'не определен';
}

function teamLabel(teamId: string): string {
  return statsByTeam.value[teamId]?.display_name ?? teamId;
}

function collectFrameGamePlayers(frame: Record<string, unknown>): Record<string, unknown>[] {
  const byId = new Map<string, Record<string, unknown>>();
  const visit = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (!isRecord(value)) return;

    const name = value.name ?? value.player ?? value.role ?? value.key;
    const hasPlayerShape =
      name !== undefined &&
      (
        value.team_id !== undefined ||
        value.score !== undefined ||
        value.points !== undefined ||
        value.life !== undefined ||
        value.hp !== undefined ||
        value.shield !== undefined ||
        value.coins !== undefined
      );
    if (hasPlayerShape) {
      const id = String(value.team_id ?? value.key ?? value.role ?? value.name ?? `player-${byId.size + 1}`);
      byId.set(id, value);
    }
    Object.values(value).forEach(visit);
  };

  visit(frame);
  return [...byId.values()];
}

function buildCurrentGameStatFromFrame(
  message: EmbeddedGameFrame,
  player: Record<string, unknown>,
  index: number,
): CurrentGameStatRow {
  const teamId = typeof player.team_id === 'string' ? player.team_id : '';
  const name = typeof player.name === 'string' ? player.name : '';
  const scoreValue = numericFrameValue(player.score ?? player.points);
  const life = numericFrameValue(player.life ?? player.hp);
  const shield = numericFrameValue(player.shield);
  const alive = typeof player.alive === 'boolean' ? player.alive : life !== 0;
  return {
    run_id: message.runId,
    team_id: teamId || `frame-player-${index}`,
    display_name: teamId ? teamLabel(teamId) : name || `Игрок ${index + 1}`,
    status: message.phase === 'finished' ? (alive ? 'финиш' : 'выбыл') : alive ? 'в игре' : 'выбыл',
    score: framePlayerScoreLabel(player),
    scoreValue,
    lifePercent: percentFrameValue(life, 50),
    shieldPercent: percentFrameValue(shield, 25),
    meta: framePlayerMetaLabel(player),
    isSelf: teamId === lobby.value?.my_team_id,
  };
}

function normalizeGameStatName(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9а-яё]+/gi, '');
}

function isSyntheticFrameTeamId(value: string): boolean {
  return value.startsWith('frame-player-');
}

function dedupeCurrentGameStats(rows: CurrentGameStatRow[]): CurrentGameStatRow[] {
  const concreteRows = rows.filter((row) => !isSyntheticFrameTeamId(row.team_id));
  const concreteNames = concreteRows
    .map((row) => normalizeGameStatName(row.display_name))
    .filter(Boolean);
  const result = new Map<string, CurrentGameStatRow>();

  const put = (row: CurrentGameStatRow): void => {
    const normalizedName = normalizeGameStatName(row.display_name);
    if (
      isSyntheticFrameTeamId(row.team_id) &&
      normalizedName &&
      concreteNames.some((name) => name.includes(normalizedName) || normalizedName.includes(name))
    ) {
      return;
    }

    const key = isSyntheticFrameTeamId(row.team_id) ? normalizedName || row.team_id : row.team_id;
    const previous = result.get(key);
    if (!previous) {
      result.set(key, row);
      return;
    }

    const previousHasScore = previous.scoreValue !== null;
    const rowHasScore = row.scoreValue !== null;
    if ((!previousHasScore && rowHasScore) || row.meta.length > previous.meta.length) {
      result.set(key, row);
    }
  };

  rows.forEach(put);
  return [...result.values()];
}

function numericFrameValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function percentFrameValue(value: number | null, max: number): number {
  if (value === null) return 0;
  return Math.max(0, Math.min(100, (value / max) * 100));
}

function framePlayerScoreLabel(player: Record<string, unknown>): string {
  const parts: string[] = [];
  const score = player.score;
  if (typeof score === 'number' && Number.isFinite(score)) {
    parts.push(scoreLabel(score));
  }

  const details: Array<[string, string]> = [
    ['очки', 'points'],
    ['монеты', 'coins'],
    ['жизни', 'life'],
    ['хиты', 'hits'],
    ['урон', 'damage'],
  ];
  for (const [label, key] of details) {
    const value = player[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      parts.push(`${label} ${scoreLabel(value)}`);
    }
  }

  return parts.length ? parts.join(' · ') : 'пока нет';
}

function framePlayerMetaLabel(player: Record<string, unknown>): string {
  const parts: string[] = [];
  const details: Array<[string, string]> = [
    ['позиция', 'position'],
    ['роль', 'role'],
  ];
  for (const [label, key] of details) {
    const value = player[key];
    if (typeof value === 'string' && value) parts.push(`${label}: ${value}`);
  }
  return parts.join(' · ');
}

function isRunStatus(value: unknown): value is RunDto['status'] {
  return typeof value === 'string'
    && ['created', 'queued', 'running', 'finished', 'failed', 'timeout', 'canceled'].includes(value);
}

function handleEmbeddedGameFrameMessage(event: MessageEvent): void {
  if (event.origin !== window.location.origin) return;
  const data = event.data;
  if (!isRecord(data) || data.type !== 'agp.watch.frame' || !isRecord(data.payload)) return;
  const payload = data.payload;
  if (typeof payload.runId !== 'string' || !isRecord(payload.frame)) return;

  embeddedGameFrame.value = {
    runId: payload.runId,
    status: isRunStatus(payload.status) ? payload.status : 'running',
    tick: typeof payload.tick === 'number' && Number.isFinite(payload.tick) ? payload.tick : 0,
    phase: typeof payload.phase === 'string' ? payload.phase : '',
    frame: payload.frame,
    replayFrameIndex: typeof payload.replayFrameIndex === 'number' ? payload.replayFrameIndex : 0,
    replayFrameCount: typeof payload.replayFrameCount === 'number' ? payload.replayFrameCount : 0,
  };
}

function isTerminalRunStatus(status: string | null | undefined): boolean {
  return Boolean(status && ['finished', 'failed', 'timeout', 'canceled'].includes(status));
}

function isResolvedCompetitionMatch(match: CompetitionMatchDto): boolean {
  return ['finished', 'auto_advanced', 'awaiting_tiebreak'].includes(match.status) || match.advanced_team_ids.length > 0;
}

function effectiveCompetitionMatchStatus(match: CompetitionMatchDto): CompetitionMatchStatus {
  if (match.status !== 'running') return match.status;
  const runIds = Object.values(match.run_ids_by_team);
  if (!runIds.length) return match.status;
  const allTerminal = runIds.every((runId) => isTerminalRunStatus(competitionRunsById.value[runId]?.status));
  return allTerminal ? 'finished' : match.status;
}

function isCompetitionMatchLoser(match: CompetitionMatchDto, teamId: string): boolean {
  return isResolvedCompetitionMatch(match) && !match.advanced_team_ids.includes(teamId);
}

function competitionTeamMatchSummary(match: CompetitionMatchDto, teamId: string): string {
  const score = match.scores_by_team[teamId];
  const placement = match.placements_by_team[teamId];
  const parts: string[] = [];
  if (score !== undefined) parts.push(`очки ${scoreLabel(score)}`);
  if (placement !== undefined) parts.push(`место ${placement}`);
  if (match.advanced_team_ids.includes(teamId)) parts.push('победа');
  else if (isCompetitionMatchLoser(match, teamId)) parts.push('поражение');
  else {
    const runStatus = competitionRunsById.value[match.run_ids_by_team[teamId] ?? '']?.status;
    parts.push(isTerminalRunStatus(runStatus) ? 'завершил' : 'играет');
  }
  return parts.join(' · ');
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
const canCloseLobby = computed(() =>
  Boolean(lobby.value && lobby.value.status !== 'closed'),
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

async function closeLobby(): Promise<void> {
  if (!lobby.value || !canManage.value) return;
  if (!confirm('Закрыть лобби? Это действие нельзя отменить.')) return;
  isBusy.value = true;
  errorMessage.value = '';
  try {
    lobby.value = await setLobbyStatus({ lobby_id: lobby.value.lobby_id, status: 'closed' });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось закрыть лобби';
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
    if (embeddedGameFrame.value?.runId !== runId) embeddedGameFrame.value = null;
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
  window.addEventListener('message', handleEmbeddedGameFrameMessage);
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
  window.removeEventListener('message', handleEmbeddedGameFrameMessage);
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
  background-color: #eef4fb;
  background-image:
    url("data:image/svg+xml,%3Csvg width='160' height='160' viewBox='0 0 160 160' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.12' stroke-width='2'%3E%3Cpath d='M16 16h28v28H16zM116 16h28v28h-28zM16 116h28v28H16zM116 116h28v28h-28z'/%3E%3Cpath d='M64 80h32M80 64v32M0 80h24M136 80h24M80 0v24M80 136v24'/%3E%3C/g%3E%3C/svg%3E"),
    radial-gradient(circle at 12% 8%, rgba(45, 212, 191, 0.22), transparent 26rem),
    radial-gradient(circle at 85% 18%, rgba(251, 191, 36, 0.18), transparent 24rem),
    linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
  background-size: 160px 160px, auto, auto, auto;
}

.lobby-page--game {
  gap: 0;
  background-color: #020617;
  background-image:
    url("data:image/svg+xml,%3Csvg width='144' height='144' viewBox='0 0 144 144' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.14' stroke-width='1.5'%3E%3Cpath d='M18 18h30v30H18zM96 18h30v30H96zM18 96h30v30H18zM96 96h30v30H96z'/%3E%3Cpath d='M72 0v144M0 72h144'/%3E%3C/g%3E%3C/svg%3E"),
    radial-gradient(circle at 14% 12%, rgba(20, 184, 166, 0.24), transparent 28rem),
    radial-gradient(circle at 82% 20%, rgba(59, 130, 246, 0.18), transparent 24rem),
    linear-gradient(135deg, #030712 0%, #071528 50%, #020617 100%);
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

.lobby-page--game > :not(.lobby-head) {
  margin-inline: 0;
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

.lobby-code-layout {
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
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 23rem);
  gap: 0;
  align-items: stretch;
  height: calc(100dvh - 3.35rem);
  min-height: 0;
}

.lobby-roles,
.lobby-editor,
.lobby-participant-column,
.lobby-match-list,
.lobby-stats-list,
.lobby-main-stack,
.lobby-side-stack,
.lobby-teacher-card {
  display: grid;
  gap: 0.5rem;
}

.lobby-roles,
.lobby-editor {
  position: relative;
  overflow: hidden;
  border-color: rgba(34, 211, 238, 0.24);
  background:
    url("data:image/svg+xml,%3Csvg width='128' height='96' viewBox='0 0 128 96' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.12'%3E%3Cpath d='M16 16h24v24H16zM88 16h24v24H88zM52 52h24v24H52z'/%3E%3Cpath d='M40 28h12M76 64h12M64 0v16M64 80v16'/%3E%3C/g%3E%3C/svg%3E") right 0.75rem top 0.75rem / 9rem auto no-repeat,
    linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.98));
  color: #e5f3ff;
  box-shadow: 0 18px 48px rgba(2, 6, 23, 0.2);
}

.lobby-roles::before,
.lobby-editor::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.18rem;
  background: linear-gradient(90deg, #22d3ee, #14b8a6, #facc15);
  opacity: 0.82;
}

.lobby-roles-head {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 0.55rem;
  margin-bottom: 0.5rem;
}

.lobby-roles-head > div:first-child {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
}

.lobby-roles-head span {
  color: #8ea7c1;
  font-size: 0.78rem;
}

.lobby-role-progress {
  height: 0.42rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.22);
}

.lobby-role-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #22d3ee, #14b8a6, #facc15);
  box-shadow: 0 0 18px rgba(34, 211, 238, 0.32);
}

.lobby-role-button {
  position: relative;
  z-index: 1;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 0.55rem;
  background: rgba(15, 23, 42, 0.64);
  color: #dbeafe;
  padding: 0.55rem 0.65rem;
  display: grid;
  gap: 0.1rem;
  text-align: left;
}

.lobby-role-button.active {
  border-color: rgba(45, 212, 191, 0.72);
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.32), rgba(15, 23, 42, 0.72));
  box-shadow: 0 10px 24px rgba(20, 184, 166, 0.12);
}

.lobby-role-button span {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.lobby-role-button span i {
  width: 0.58rem;
  height: 0.58rem;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 0 0.18rem rgba(245, 158, 11, 0.12);
}

.lobby-role-button.filled span i {
  background: #14b8a6;
  box-shadow: 0 0 0 0.18rem rgba(20, 184, 166, 0.14);
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

.lobby-role-button small {
  color: #8ea7c1;
}

.lobby-competition-panel,
.lobby-competition-leaderboard,
.lobby-competition-stat-list,
.lobby-rounds,
.lobby-round,
.lobby-competition-match,
.lobby-competition-team-rows {
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

.lobby-competition-stat-list {
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 0.5rem;
}

.lobby-competition-stat-row,
.lobby-competition-team-row {
  border: 1px solid var(--agp-border);
  border-radius: 0.45rem;
  background: #fff;
  padding: 0.5rem 0.6rem;
  display: grid;
  gap: 0.05rem;
}

.lobby-competition-stat-row span,
.lobby-competition-team-row span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-competition-team-rows {
  gap: 0.45rem;
}

.lobby-competition-team-row {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.lobby-competition-team-row.winner {
  border-color: rgba(15, 118, 110, 0.28);
  background: #edf8f6;
}

.lobby-competition-team-row.loser {
  background: #fff;
}

.lobby-competition-setting {
  display: grid;
  gap: 0.15rem;
  min-width: 7.2rem;
  font-size: 0.78rem;
  color: var(--agp-text-muted);
}

.lobby-editor-toolbar {
  position: relative;
  z-index: 1;
  justify-content: space-between;
  margin-bottom: 0.65rem;
}

.lobby-editor-toolbar h2 {
  color: #e5f3ff;
}

.lobby-editor-toolbar p {
  color: #8ea7c1;
}

.lobby-editor-toolbar .btn-outline-secondary {
  border-color: rgba(125, 211, 252, 0.34);
  background: rgba(15, 23, 42, 0.62);
  color: #cfe6f5;
}

.lobby-editor-toolbar .btn-outline-secondary:hover:not(:disabled) {
  border-color: rgba(45, 212, 191, 0.68);
  background: rgba(20, 184, 166, 0.18);
  color: #ffffff;
}

.lobby-editor-toolbar .btn-dark {
  border: 0;
  background: linear-gradient(135deg, #14b8a6, #2563eb);
  color: #ffffff;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
}

.lobby-participant-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
}

.lobby-participant-column {
  align-content: start;
}

.lobby-column-empty {
  border: 1px dashed rgba(15, 118, 110, 0.22);
  border-radius: 0.55rem;
  background:
    url("data:image/svg+xml,%3Csvg width='72' height='48' viewBox='0 0 72 48' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2314b8a6' stroke-opacity='.16'%3E%3Cpath d='M12 12h14v14H12zM46 12h14v14H46zM29 26h14v14H29z'/%3E%3C/g%3E%3C/svg%3E") right 0.4rem center / 4.5rem auto no-repeat,
    rgba(240, 253, 250, 0.46);
  color: var(--agp-text-muted);
  font-size: 0.84rem;
  padding: 0.65rem;
}

.lobby-participants-card {
  min-height: 10rem;
}

.lobby-main-stack {
  align-content: start;
  min-width: 0;
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
.lobby-stat-row,
.lobby-leaderboard-row {
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

.lobby-match-row > span {
  display: grid;
  gap: 0.05rem;
  min-width: 0;
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
.lobby-run-links,
.lobby-leaderboard-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.lobby-match-group header {
  justify-content: space-between;
}

.lobby-match-group header > div {
  display: grid;
  gap: 0.05rem;
}

.lobby-match-group header > div span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-section-head,
.lobby-match-pagination,
.lobby-match-meta {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.lobby-section-head {
  justify-content: space-between;
  margin-bottom: 0.65rem;
}

.lobby-count-pill {
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: 999px;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  padding: 0.2rem 0.55rem;
  font-size: 0.78rem;
  font-weight: 850;
}

.lobby-match-meta {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-match-meta strong {
  color: var(--agp-text);
}

.lobby-match-pagination {
  justify-content: space-between;
  margin-top: 0.65rem;
}

.lobby-leaderboard-list {
  display: grid;
  gap: 0.45rem;
}

.lobby-leaderboard-row {
  grid-template-columns: auto minmax(0, 1fr);
  background: #fff;
}

.lobby-leaderboard-row > div {
  display: grid;
  gap: 0.05rem;
  min-width: 0;
}

.lobby-leaderboard-row span:not(.lobby-leaderboard-place) {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
}

.lobby-leaderboard-place {
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--agp-primary-soft);
  color: var(--agp-primary);
  font-weight: 850;
  font-size: 0.78rem;
}

.lobby-game-view {
  position: relative;
  min-height: 0;
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: #020617;
  box-shadow: none;
}

.lobby-game-view iframe {
  width: 100%;
  height: 100%;
  min-height: 0;
  border: 0;
  border-radius: 0;
}

.lobby-game-finished-overlay {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: grid;
  place-items: center;
  background: rgba(2, 6, 23, 0.6);
  backdrop-filter: blur(4px);
  pointer-events: none;
}

.lobby-game-finished-card {
  display: grid;
  gap: 0.25rem;
  text-align: center;
  padding: 1rem 1.5rem;
  border-radius: 0.6rem;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(135, 226, 255, 0.3);
  color: #e9f7ff;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
}

.lobby-game-finished-card strong {
  font-size: 1.1rem;
}

.lobby-game-finished-card small {
  color: #9bb3c9;
}

.lobby-game-stats {
  min-height: 0;
  padding: 0.85rem;
  overflow: auto;
  border: 0;
  border-left: 1px solid rgba(34, 211, 238, 0.24);
  border-radius: 0;
  background:
    linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.98)),
    url("data:image/svg+xml,%3Csvg width='104' height='104' viewBox='0 0 104 104' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23facc15' stroke-opacity='.12'%3E%3Cpath d='M16 52h72M52 16v72M28 28l48 48M76 28 28 76'/%3E%3C/g%3E%3C/svg%3E");
  color: #dbeafe;
  box-shadow: none;
}

.lobby-game-stats .text-muted {
  color: #8ea7c1 !important;
}

.lobby-game-stats-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.lobby-game-stats-head h2,
.lobby-game-stats-head strong {
  color: #e5f3ff;
}

.lobby-game-stats-head span {
  color: #8ea7c1;
  font-size: 0.78rem;
}

.lobby-game-mini-stats {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
}

.lobby-game-mini-stats div,
.lobby-game-empty-stat {
  border: 1px solid rgba(34, 211, 238, 0.16);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.66);
  padding: 0.55rem 0.65rem;
}

.lobby-game-mini-stats span {
  display: block;
  color: #8ea7c1;
  font-size: 0.72rem;
}

.lobby-game-mini-stats strong {
  color: #e5f3ff;
}

.lobby-game-scoreboard {
  gap: 0.5rem;
}

.lobby-game-layout .lobby-stat-row {
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.35rem 0.65rem;
  border-color: rgba(34, 211, 238, 0.18);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.68);
  color: #dbeafe;
}

.lobby-game-layout .lobby-stat-row--self {
  border-color: rgba(45, 212, 191, 0.5);
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.28), rgba(15, 23, 42, 0.7));
}

.lobby-stat-title {
  display: grid;
  gap: 0.05rem;
  min-width: 0;
}

.lobby-stat-title strong {
  overflow: hidden;
  color: #e5f3ff;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lobby-stat-score {
  color: #fef3c7;
  font-weight: 850;
  text-align: right;
}

.lobby-stat-bars {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.3rem;
}

.lobby-stat-bars span {
  height: 0.32rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.24);
}

.lobby-stat-bars i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.lobby-stat-bars span:first-child i {
  background: linear-gradient(90deg, #fb7185, #facc15);
}

.lobby-stat-bars span:last-child i {
  background: linear-gradient(90deg, #38bdf8, #22d3ee);
}

.lobby-game-layout .lobby-stat-row small {
  grid-column: 1 / -1;
  color: #8ea7c1;
}

.lobby-game-empty-stat {
  color: #8ea7c1;
  font-size: 0.86rem;
}

.lobby-empty {
  height: 100%;
  min-height: 24rem;
  display: grid;
  place-content: center;
  gap: 0.25rem;
  border: 1px solid rgba(34, 211, 238, 0.12);
  background:
    url("data:image/svg+xml,%3Csvg width='180' height='120' viewBox='0 0 180 120' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%2322d3ee' stroke-opacity='.14' stroke-width='2'%3E%3Cpath d='M32 24h32v32H32zM116 24h32v32h-32zM74 64h32v32H74z'/%3E%3Cpath d='M64 40h52M90 0v24M90 96v24'/%3E%3C/g%3E%3C/svg%3E") center / 16rem auto no-repeat,
    radial-gradient(circle at 50% 45%, rgba(20, 184, 166, 0.18), transparent 18rem),
    #020617;
  color: #e5f3ff;
  text-align: center;
}

.lobby-empty .text-muted {
  color: #8ea7c1 !important;
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
