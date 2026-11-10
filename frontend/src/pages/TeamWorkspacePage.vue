<template>
  <section class="arena-player-workspace">
    <header>
      <RouterLink class="agp-back-link" :to="backTarget" aria-label="Назад"
        >←</RouterLink
      >
      <h1 :title="workspace?.team_name || workspace?.captain_user_id">{{ workspace?.team_name || workspace?.captain_user_id || "Код игрока" }}</h1>
      <span class="small text-muted">{{
        isEditorDirty ? "Черновик" : formatTime(selectedSlot?.updated_at)
      }}</span
      ><RouterLink
        v-if="workspace"
        class="btn btn-outline-secondary"
        :to="{ name: 'game-docs', params: { gameId: workspace.game_id } }"
        >Условие</RouterLink
      ><button
        v-if="canEditWorkspace"
        class="btn btn-primary"
        :disabled="!selectedSlotKey || isSaving || !isEditorDirty"
        @click="saveSelectedSlotCode"
      >
        Сохранить
      </button>
    </header>
    <LoadingSkeleton
      v-if="isLoading"
      :count="1"
      layout="workspace"
      label="Загрузка кода"
    />
    <p v-if="errorMessage" role="alert" class="text-danger">
      {{ errorMessage }}
    </p>
    <article
      v-if="workspace && !isLoading"
      class="agp-card arena-player-editor"
    >
      <header>
        <select
          :value="selectedSlotKey"
          aria-label="Файл бота"
          @change="selectSlot(($event.target as HTMLSelectElement).value)"
        >
          <option
            v-for="slot in workspace.slot_states"
            :key="slot.slot_key"
            :value="slot.slot_key"
          >
            {{ slot.slot_key }}
          </option></select
        ><span v-if="!canEditWorkspace" class="text-muted small"
          >Только просмотр</span
        >
        <details v-else>
          <summary aria-label="Меню файла">⋯</summary>
          <div>
            <button v-if="replacementUndo !== null" @click="undoImport">
              Отменить замену
            </button>
            <button
              :disabled="!selectedSlotKey"
              @click="applyTemplateToSelectedSlot"
            >
              Вставить шаблон</button
            ><button :disabled="!isEditorDirty" @click="resetSelectedSlotCode">
              Отменить изменения</button
            ><template v-if="canUseDemoStrategy"
              ><select
                v-model="selectedDemoStrategyId"
                aria-label="Пример стратегии"
              >
                <option
                  v-for="strategy in selectedSlotDemoStrategies"
                  :key="strategy.strategy_id"
                  :value="strategy.strategy_id"
                >
                  {{ strategy.title }}
                </option></select
              ><button @click="applyDemoStrategyToSelectedSlot">
                Вставить пример
              </button></template
            >
          </div>
        </details>
      </header>
      <div v-if="pendingSlotKey" class="arena-player-pending">
        <span>Сохранить изменения?</span
        ><button class="btn btn-sm btn-primary" @click="saveAndSwitchSlot">
          Сохранить</button
        ><button
          class="btn btn-sm btn-outline-secondary"
          @click="discardAndSwitchSlot"
        >
          Сбросить</button
        ><button
          class="btn btn-sm btn-outline-secondary"
          @click="pendingSlotKey = ''"
        >
          Остаться
        </button>
      </div>
      <CodeEditor
        v-model="editorCode"
        :readonly="!canEditWorkspace"
        @run="saveSelectedSlotCode"
      />
    </article>
  </section>
</template>
<script setup lang="ts">
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { formatTime } from "../lib/attemptPresentation";

import CodeEditor from "../components/CodeEditor.vue";
import {
  getRun,
  getRunCode,
  getGameTemplates,
  getWorkspace,
  updateSlotCode,
  type GameDemoStrategyDto,
  type TeamWorkspaceDto,
} from "../lib/api";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const sessionStore = useSessionStore();
const backTarget = computed(() =>
  typeof route.query.back === "string" &&
  route.query.back.startsWith("/") &&
  !route.query.back.startsWith("//")
    ? route.query.back
    : "/lobbies",
);

const workspace = ref<TeamWorkspaceDto | null>(null);
const selectedSlotKey = ref("");
const pendingSlotKey = ref("");
const editorCode = ref("");
const isLoading = ref(false);
const isSaving = ref(false);
const isTemplateLoading = ref(false);
const errorMessage = ref("");
const replacementUndo = ref<string | null>(null);
function undoImport(): void {
  if (replacementUndo.value !== null) {
    editorCode.value = replacementUndo.value;
    replacementUndo.value = null;
  }
}
const templatesBySlot = ref<Record<string, string>>({});
const demoStrategiesBySlot = ref<Record<string, GameDemoStrategyDto[]>>({});
const templatesGameId = ref("");
const selectedDemoStrategyId = ref("");

const selectedSlot = computed(
  () =>
    workspace.value?.slot_states.find(
      (slot) => slot.slot_key === selectedSlotKey.value,
    ) ?? null,
);
const canEditWorkspace = computed(
  () => workspace.value?.captain_user_id === sessionStore.nickname,
);
const selectedSlotDemoStrategies = computed(
  () => demoStrategiesBySlot.value[selectedSlotKey.value] ?? [],
);
const canInspectTechnicalDetails = computed(
  () => sessionStore.role === "teacher" || sessionStore.role === "admin",
);
const canUseDemoStrategy = computed(() => canInspectTechnicalDetails.value);
const savedSelectedSlotCode = computed(() => selectedSlot.value?.code ?? "");
const isEditorDirty = computed(
  () => editorCode.value !== savedSelectedSlotCode.value,
);

async function loadWorkspace(): Promise<void> {
  const teamId = String(route.params.teamId || "").trim();
  if (!teamId) {
    errorMessage.value = "Не найден игрок для просмотра кода";
    return;
  }

  isLoading.value = true;
  errorMessage.value = "";
  try {
    const payload = await getWorkspace(teamId);
    workspace.value = payload;
    if (templatesGameId.value !== payload.game_id) {
      templatesBySlot.value = {};
      demoStrategiesBySlot.value = {};
      templatesGameId.value = payload.game_id;
    }
    if (
      !selectedSlotKey.value ||
      !payload.slot_states.some(
        (item) => item.slot_key === selectedSlotKey.value,
      )
    ) {
      selectedSlotKey.value = payload.slot_states[0]?.slot_key ?? "";
    }
    editorCode.value = selectedSlot.value?.code ?? "";
    try {
      const draft = JSON.parse(
        localStorage.getItem(
          `agp_player_code_draft:${sessionStore.nickname}:${teamId}:${selectedSlotKey.value}`,
        ) || "null",
      );
      if (draft?.base === editorCode.value && typeof draft.code === "string")
        editorCode.value = draft.code;
    } catch {
      /* Server code stays available. */
    }
    selectedDemoStrategyId.value =
      selectedSlotDemoStrategies.value[0]?.strategy_id ?? "";
    await ensureGameTemplates(payload.game_id);
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Не удалось загрузить код игрока";
  } finally {
    isLoading.value = false;
  }
}

function selectSlot(slotKey: string): void {
  if (slotKey === selectedSlotKey.value) return;
  if (canEditWorkspace.value && isEditorDirty.value) {
    pendingSlotKey.value = slotKey;
    return;
  }
  switchToSlot(slotKey);
}

function switchToSlot(slotKey: string): void {
  selectedSlotKey.value = slotKey;
  pendingSlotKey.value = "";
  editorCode.value =
    workspace.value?.slot_states.find((slot) => slot.slot_key === slotKey)
      ?.code ?? "";
  selectedDemoStrategyId.value =
    selectedSlotDemoStrategies.value[0]?.strategy_id ?? "";
}

async function saveAndSwitchSlot(): Promise<void> {
  if (!pendingSlotKey.value) return;
  const targetSlotKey = pendingSlotKey.value;
  await saveSelectedSlotCode();
  if (!errorMessage.value) {
    switchToSlot(targetSlotKey);
  }
}

function discardAndSwitchSlot(): void {
  if (!pendingSlotKey.value) return;
  switchToSlot(pendingSlotKey.value);
}

function resetSelectedSlotCode(): void {
  editorCode.value = selectedSlot.value?.code ?? "";
}

async function applyTemplateToSelectedSlot(): Promise<void> {
  if (!workspace.value || !selectedSlotKey.value) return;
  isTemplateLoading.value = true;
  errorMessage.value = "";
  try {
    await ensureGameTemplates(workspace.value.game_id);
    const templateCode = templatesBySlot.value[selectedSlotKey.value];
    if (!templateCode) {
      errorMessage.value = `Для роли ${selectedSlotKey.value} шаблон не найден`;
      return;
    }
    editorCode.value = templateCode;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Не удалось загрузить шаблон";
  } finally {
    isTemplateLoading.value = false;
  }
}

async function applyDemoStrategyToSelectedSlot(): Promise<void> {
  if (!canUseDemoStrategy.value) return;
  if (!workspace.value || !selectedSlotKey.value) return;
  isTemplateLoading.value = true;
  errorMessage.value = "";
  try {
    await ensureGameTemplates(workspace.value.game_id);
    const strategies = selectedSlotDemoStrategies.value;
    const strategy =
      strategies.find(
        (item) => item.strategy_id === selectedDemoStrategyId.value,
      ) ??
      strategies[0] ??
      null;
    if (!strategy) {
      errorMessage.value = `Для роли ${selectedSlotKey.value} демо-стратегия не найдена`;
      return;
    }
    selectedDemoStrategyId.value = strategy.strategy_id;
    editorCode.value = strategy.code;
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Не удалось загрузить демо-стратегию";
  } finally {
    isTemplateLoading.value = false;
  }
}

async function ensureGameTemplates(gameId: string): Promise<void> {
  if (
    templatesGameId.value === gameId &&
    Object.keys(templatesBySlot.value).length > 0
  ) {
    return;
  }

  const payload = await getGameTemplates(gameId);
  templatesBySlot.value = Object.fromEntries(
    payload.templates.map((item) => [item.slot_key, item.code]),
  );

  const strategiesBySlot: Record<string, GameDemoStrategyDto[]> = {};
  for (const strategy of payload.demo_strategies ?? []) {
    if (!strategiesBySlot[strategy.slot_key]) {
      strategiesBySlot[strategy.slot_key] = [];
    }
    strategiesBySlot[strategy.slot_key].push(strategy);
  }
  demoStrategiesBySlot.value = strategiesBySlot;
  templatesGameId.value = gameId;
  selectedDemoStrategyId.value =
    selectedSlotDemoStrategies.value[0]?.strategy_id ?? "";
}

async function saveSelectedSlotCode(): Promise<void> {
  if (!workspace.value || !selectedSlotKey.value) {
    return;
  }
  isSaving.value = true;
  errorMessage.value = "";
  try {
    await updateSlotCode({
      team_id: workspace.value.team_id,
      slot_key: selectedSlotKey.value,
      actor_user_id: sessionStore.nickname,
      code: editorCode.value,
    });
    await loadWorkspace();
    pendingSlotKey.value = "";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Не удалось сохранить код";
  } finally {
    isSaving.value = false;
  }
}

watch(
  () => route.params.teamId,
  async () => {
    await loadWorkspace();
  },
);

watch([editorCode, savedSelectedSlotCode], () => {
  if (
    isLoading.value ||
    !workspace.value ||
    !selectedSlotKey.value ||
    !canEditWorkspace.value
  )
    return;
  try {
    const key = `agp_player_code_draft:${sessionStore.nickname}:${workspace.value.team_id}:${selectedSlotKey.value}`;
    if (isEditorDirty.value)
      localStorage.setItem(
        key,
        JSON.stringify({
          code: editorCode.value,
          base: savedSelectedSlotCode.value,
        }),
      );
    else localStorage.removeItem(key);
  } catch {
    /* Explicit server saving remains available. */
  }
});
onMounted(async () => {
  await loadWorkspace();
  if (
    typeof route.query.from_run === "string" &&
    workspace.value &&
    canEditWorkspace.value
  ) {
    try {
      const run = await getRun(route.query.from_run);
      if (run.team_id !== workspace.value.team_id)
        throw new Error("Код относится к другому игроку");
      const snapshot = await getRunCode(run.run_id);
      const slot =
        typeof route.query.slot === "string"
          ? route.query.slot
          : Object.keys(snapshot.codes_by_slot)[0];
      if (slot && snapshot.codes_by_slot[slot] !== undefined) {
        selectedSlotKey.value = slot;
        replacementUndo.value = editorCode.value;
        editorCode.value = snapshot.codes_by_slot[slot];
      }
    } catch (e) {
      errorMessage.value =
        e instanceof Error ? e.message : "Не удалось взять код";
    }
  }
});
</script>

<style scoped>
.arena-player-workspace {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: calc(100dvh - 24px);
}
.arena-player-workspace > header {
  display: flex;
  gap: 8px;
  align-items: center;
  min-height: 44px;
}
.arena-player-workspace h1 {
  font-size: 16px;
  line-height: 24px;
  margin: 0;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.arena-player-workspace > header > :not(h1) { flex-shrink: 0; }
.arena-player-editor {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.arena-player-editor > header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  min-height: 44px;
  border-bottom: 1px solid var(--agp-border);
}
.arena-player-editor select {
  background: var(--agp-surface);
  color: var(--agp-text);
  border: 1px solid var(--agp-border);
  border-radius: 6px;
  padding: 4px;
  max-width: 220px;
  min-height: 32px;
}
.arena-player-editor details {
  position: relative;
  margin-left: auto;
}
.arena-player-editor summary {
  font-size: 22px;
  cursor: pointer;
  list-style: none;
  display: grid;
  place-items: center;
  min-height: 32px;
  min-width: 32px;
}
.arena-player-editor details > div {
  position: absolute;
  right: 0;
  width: 220px;
  background: var(--agp-surface);
  border: 1px solid var(--agp-border);
  padding: 8px;
  z-index: 10;
  display: grid;
  gap: 4px;
  border-radius: 8px;
}
.arena-player-editor details button {
  background: none;
  border: 0;
  text-align: left;
  color: var(--agp-text);
  font-size: 13px;
  padding: 8px;
}
.arena-player-editor > .agp-code-editor {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.arena-player-editor :deep(.cm-editor) {
  height: 100%;
  min-height: 0 !important;
  border: 0 !important;
  border-radius: 0 !important;
}
.arena-player-pending {
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
@media (max-width: 767px) {
  .arena-player-workspace {
    height: calc(100dvh - 16px);
  }
  .arena-player-workspace > header {
    flex-wrap: nowrap;
  }
  .arena-player-editor select, .arena-player-editor summary { min-height: 44px; }
  .arena-player-editor summary { min-width: 44px; }
  .arena-player-workspace > header > .small {
    display: none;
  }
}
</style>
