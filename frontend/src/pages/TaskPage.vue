<template>
  <section class="arena-task-page">
    <LoadingSkeleton v-if="loading" :count="2" label="Загрузка задачи" />
    <p v-if="error" role="alert" class="text-danger">{{ error }}</p>
    <template v-if="game">
      <article class="agp-card arena-task-statement">
        <header>
          <h1>{{ game.title }}</h1>
          <RouterLink
            v-if="canManage"
            class="btn btn-sm btn-outline-secondary"
            :to="{ name: 'admin-catalog', query: { game_id: game.game_id } }"
            >Настройки</RouterLink
          >
          <button
            v-if="canManage"
            class="btn btn-sm btn-outline-secondary"
            @click="copyLink"
          >
            {{ copied ? "Скопировано" : "Ссылка на задачу" }}
          </button>
        </header>
        <MarkdownContent v-if="game.description" :source="game.description" />
        <MarkdownContent
          v-if="docs?.player_instruction"
          :source="docs.player_instruction"
        />
        <template v-for="link in docs?.links" :key="link.path"
          ><MarkdownContent
            v-if="link.content"
            :source="link.content.replace(/^# [^\n]+\n+/, '')"
        /></template>
      </article>
      <aside class="arena-task-results">
        <article class="agp-card arena-task-action">
          <RouterLink
            class="btn btn-primary w-100"
            :to="{
              name: 'task-run',
              params: { gameId: game.game_id },
              query: route.query,
            }"
            >{{
              hasDraft || myEntry ? "Продолжить решение" : "Решать"
            }}</RouterLink
          >
          <div v-if="myEntry" class="arena-task-personal">
            <span>{{ myEntry.solved ? "Решено" : "Лучший результат" }}</span
            ><strong>{{ myEntry.best_score ?? "—" }}</strong
            ><span v-if="myEntry.place">Место {{ myEntry.place }}</span>
          </div>
        </article>
        <article class="agp-card arena-task-section">
          <h2>Лидерборд</h2>
          <div v-if="!leaderboard?.entries.length" class="text-muted">
            Пока нет результатов
          </div>
          <table v-else class="table table-sm mb-0">
            <thead>
              <tr>
                <th>#</th>
                <th>Ученик</th>
                <th class="text-end">Результат</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in leaderboard.entries"
                :key="entry.user_id"
                :class="{ 'arena-my-row': entry.user_id === session.nickname }"
              >
                <td>{{ entry.place }}</td>
                <td>
                  <button
                    v-if="canManage"
                    class="arena-table-link"
                    @click="filterUser(entry.user_id)"
                  >
                    {{ entry.user_id }}</button
                  ><span v-else>{{ entry.user_id }}</span>
                </td>
                <td class="text-end mono">
                  {{ entry.best_score ?? (entry.solved ? "✓" : "—") }}
                </td>
              </tr>
            </tbody>
          </table>
        </article>
        <article class="agp-card arena-task-section">
          <header>
            <h2>{{ canManage ? "Последние попытки" : "Мои попытки" }}</h2>
            <button
              v-if="selectedUser"
              class="btn btn-sm btn-outline-secondary"
              @click="filterUser('')"
            >
              {{ selectedUser }} ×
            </button>
          </header>
          <SnakeLoader v-if="attemptsLoading" label="Загрузка попыток" />
          <p v-else-if="!attempts.length" class="text-muted mb-0">
            Пока нет попыток
          </p>
          <table v-else class="table table-sm mb-0">
            <tbody>
              <tr v-for="attempt in attempts" :key="attempt.run_id">
                <td class="arena-attempt-state">
                  <span
                    class="arena-status-icon"
                    :class="attemptPresentation(attempt).tone"
                    :title="attemptPresentation(attempt).label"
                    aria-hidden="true"
                    >{{ attemptPresentation(attempt).icon }}</span
                  >
                </td>
                <td>
                  <RouterLink
                    class="arena-table-link"
                    :to="{
                      name: 'task-run',
                      params: { gameId: game.game_id },
                      query: {
                        inspect_run: attempt.run_id,
                        back: route.fullPath,
                        attempt_user: selectedUser || undefined,
                      },
                    }"
                    ><span v-if="canManage">{{ attempt.requested_by }} · </span
                    >{{ formatTime(attempt.created_at) }}</RouterLink
                  >
                  <div class="small text-muted">
                    {{ attemptPresentation(attempt).label }}
                  </div>
                </td>
                <td class="text-end mono">
                  {{ attemptPresentation(attempt).score }}
                </td>
              </tr>
            </tbody>
          </table>
          <RouterLink
            :to="{
              name: 'task-attempts',
              params: { gameId: game.game_id },
              query: selectedUser ? { requested_by: selectedUser } : {},
            }"
            class="arena-table-link arena-all-attempts"
            >Все попытки →</RouterLink
          >
        </article>
      </aside>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import MarkdownContent from "../components/MarkdownContent.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import SnakeLoader from "../components/SnakeLoader.vue";
import {
  getGame,
  getGameDocs,
  getSingleTaskLeaderboard,
  listSingleTaskAttempts,
  listTeamsByGame,
  getWorkspace,
  type GameDto,
  type GameDocumentationDto,
  type SingleTaskLeaderboardDto,
  type RunDto,
} from "../lib/api";
import { attemptPresentation, formatTime } from "../lib/attemptPresentation";
import { useSessionStore } from "../stores/session";
const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const game = ref<GameDto | null>(null);
const docs = ref<GameDocumentationDto | null>(null);
const leaderboard = ref<SingleTaskLeaderboardDto | null>(null);
const attempts = ref<RunDto[]>([]);
const loading = ref(true);
const attemptsLoading = ref(false);
const error = ref("");
const selectedUser = ref(
  typeof route.query.requested_by === "string" ? route.query.requested_by : "",
);
const copied = ref(false);
const hasDraft = ref(false);
const canManage = computed(() => session.role !== "student");
const myEntry = computed(() =>
  leaderboard.value?.entries.find(
    (entry) => entry.user_id === session.nickname,
  ),
);
let refreshTimer: ReturnType<typeof setInterval> | undefined;
let refreshBusy = false;
async function refreshResults(): Promise<void> {
  if (!game.value || refreshBusy) return;
  refreshBusy = true;
  try {
    const [board, runs] = await Promise.all([
      getSingleTaskLeaderboard(game.value.game_id, 50),
      listSingleTaskAttempts({
        game_id: game.value.game_id,
        requested_by: selectedUser.value || undefined,
        limit: 8,
      }),
    ]);
    leaderboard.value = board;
    attempts.value = runs;
  } catch (e) {
    error.value =
      e instanceof Error ? e.message : "Не удалось загрузить результаты";
  } finally {
    refreshBusy = false;
    attemptsLoading.value = false;
  }
}
async function filterUser(user: string): Promise<void> {
  selectedUser.value = user;
  await router.replace({
    query: { ...route.query, requested_by: user || undefined },
  });
  attemptsLoading.value = true;
  await refreshResults();
}
async function copyLink(): Promise<void> {
  try {
    await navigator.clipboard.writeText(
      `${location.origin}/tasks/${game.value!.game_id}`,
    );
    copied.value = true;
  } catch {
    error.value = "Не удалось скопировать ссылку";
  }
}
onMounted(async () => {
  try {
    const id = String(route.params.gameId);
    const [task, documentation] = await Promise.all([
      getGame(id),
      getGameDocs(id),
    ]);
    if (task.mode !== "single_task") throw new Error("Это игра для лобби");
    game.value = task;
    docs.value = documentation;
    const ownTeam = (await listTeamsByGame(id)).find(
      (team) => team.captain_user_id === session.nickname,
    );
    if (ownTeam) {
      const slots = (await getWorkspace(ownTeam.team_id)).slot_states;
      hasDraft.value = slots.some((slot) => Boolean(slot.code?.trim()));
      try {
        hasDraft.value ||= slots.some((slot) =>
          Boolean(
            JSON.parse(
              localStorage.getItem(
                `agp_task_code_draft:${session.nickname}:${id}:${slot.slot_key}`,
              ) || "null",
            )?.code?.trim(),
          ),
        );
      } catch {
        /* A server draft remains available if local storage is blocked. */
      }
    }
    await refreshResults();
    refreshTimer = setInterval(() => {
      if (document.visibilityState === "visible") void refreshResults();
    }, 5000);
  } catch (e) {
    error.value =
      e instanceof Error ? e.message : "Не удалось загрузить задачу";
  } finally {
    loading.value = false;
  }
});
onUnmounted(() => clearInterval(refreshTimer));
</script>
<style scoped>
.arena-task-page {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(320px, 2fr);
  gap: 24px;
  align-items: start;
}
.arena-task-statement {
  padding: 24px;
  font-size: 14px;
  line-height: 22px;
}
.arena-task-statement header,
.arena-task-section header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.arena-task-statement h1,
.arena-task-section h2 {
  margin: 0;
}
.arena-task-results {
  display: grid;
  gap: 16px;
  min-width: 0;
}
.arena-task-action,
.arena-task-section {
  padding: 16px;
}
.arena-task-section h2 {
  margin-bottom: 12px;
}
.arena-task-section header h2 {
  margin: 0;
}
.arena-task-personal {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
  font-size: 13px;
}
.arena-table-link {
  border: 0;
  background: none;
  color: var(--agp-primary);
  padding: 0;
  text-decoration: none;
  text-align: left;
}
.arena-table-link:hover {
  text-decoration: underline;
}
.arena-all-attempts {
  display: inline-block;
  margin-top: 12px;
}
.arena-my-row {
  background: var(--agp-primary-soft);
}
@media (max-width: 850px) {
  .arena-task-page {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .arena-task-statement {
    padding: 16px;
  }
  .arena-task-action {
    position: static;
  }
  .arena-task-results {
    display: contents;
  }
  .arena-task-action {
    grid-row: 1;
  }
  .arena-task-statement {
    grid-row: 2;
  }
  .arena-task-statement header {
    align-items: flex-start;
  }
  .arena-task-statement header .btn {
    font-size: 12px;
  }
}
</style>
