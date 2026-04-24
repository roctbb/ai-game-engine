<template>
  <section class="agp-grid">
    <header>
      <h1 class="h3 mb-1">Командный Workspace</h1>
      <p class="text-muted mb-0">
        Каноническая точка редактирования: сохранение кода обновляет `TeamSlotCode`, а запуски используют snapshot.
      </p>
    </header>

    <div v-if="isLoading" class="agp-card p-4 text-muted">Загрузка workspace...</div>
    <div v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</div>

    <div v-else class="agp-grid agp-grid--2">
      <aside class="agp-card p-3">
        <h2 class="h6 mb-3">Слоты команды</h2>
        <div class="d-flex flex-column gap-2">
          <button
            v-for="slot in workspace?.slot_states ?? []"
            :key="slot.slot_key"
            type="button"
            class="agp-card-soft p-2 d-flex justify-content-between align-items-center text-start border-0"
            :class="{ 'slot-selected': selectedSlotKey === slot.slot_key }"
            @click="selectSlot(slot.slot_key)"
          >
            <div>
              <div class="fw-semibold">
                {{ slot.slot_key }}
                <span v-if="slot.required" class="text-danger">*</span>
              </div>
              <div class="small text-muted">revision: {{ slot.revision ?? 'n/a' }}</div>
            </div>
            <SlotStateBadge :slot-state="slot.state" />
          </button>
        </div>
      </aside>

      <article class="agp-card p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Редактор слота `{{ selectedSlotKey || '—' }}`</h2>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-secondary" :disabled="!selectedSlotKey" @click="resetSelectedSlotCode">
              Сбросить
            </button>
            <button
              class="btn btn-sm btn-outline-secondary"
              :disabled="!selectedSlotKey || isTemplateLoading"
              @click="applyTemplateToSelectedSlot"
            >
              {{ isTemplateLoading ? 'Загрузка шаблона...' : 'Шаблон' }}
            </button>
            <select
              v-model="selectedDemoStrategyId"
              class="form-select form-select-sm demo-select"
              :disabled="!selectedSlotKey || selectedSlotDemoStrategies.length === 0 || isTemplateLoading"
            >
              <option value="">Демо-стратегия</option>
              <option
                v-for="strategy in selectedSlotDemoStrategies"
                :key="strategy.strategy_id"
                :value="strategy.strategy_id"
              >
                {{ strategy.title }}
              </option>
            </select>
            <button
              class="btn btn-sm btn-outline-primary"
              :disabled="!selectedSlotKey || isTemplateLoading"
              @click="applyDemoStrategyToSelectedSlot"
            >
              Демо
            </button>
            <button class="btn btn-sm btn-dark" :disabled="!selectedSlotKey || isSaving" @click="saveSelectedSlotCode">
              {{ isSaving ? 'Сохранение...' : 'Сохранить' }}
            </button>
          </div>
        </div>
        <CodeEditor
          v-model="editorCode"
          :readonly="!selectedSlotKey"
          language="python"
        />
        <div class="small text-muted mt-2">
          Подсветка синтаксиса Python доступна в редакторе.
        </div>
        <div class="small text-muted mt-1">
          Кнопки `Шаблон` и `Демо` подставляют starter-код или готовую демо-стратегию из `/games/{gameId}/templates`.
        </div>
        <div class="small text-muted mt-1">
          Snapshot фиксируется при `run: created -> queued`. Изменения здесь попадут только в новые запуски.
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import CodeEditor from '../components/CodeEditor.vue';
import SlotStateBadge from '../components/SlotStateBadge.vue';
import {
  getGameTemplates,
  getWorkspace,
  updateSlotCode,
  type GameDemoStrategyDto,
  type TeamWorkspaceDto,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const sessionStore = useSessionStore();

const workspace = ref<TeamWorkspaceDto | null>(null);
const selectedSlotKey = ref('');
const editorCode = ref('');
const isLoading = ref(false);
const isSaving = ref(false);
const isTemplateLoading = ref(false);
const errorMessage = ref('');
const templatesBySlot = ref<Record<string, string>>({});
const demoStrategiesBySlot = ref<Record<string, GameDemoStrategyDto[]>>({});
const templatesGameId = ref('');
const selectedDemoStrategyId = ref('');

const selectedSlot = computed(() =>
  workspace.value?.slot_states.find((slot) => slot.slot_key === selectedSlotKey.value) ?? null
);
const selectedSlotDemoStrategies = computed(() => demoStrategiesBySlot.value[selectedSlotKey.value] ?? []);

async function loadWorkspace(): Promise<void> {
  const teamId = String(route.params.teamId || '').trim();
  if (!teamId) {
    errorMessage.value = 'Некорректный teamId в маршруте';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';
  try {
    const payload = await getWorkspace(teamId);
    workspace.value = payload;
    if (templatesGameId.value !== payload.game_id) {
      templatesBySlot.value = {};
      demoStrategiesBySlot.value = {};
      templatesGameId.value = payload.game_id;
    }
    if (!selectedSlotKey.value || !payload.slot_states.some((item) => item.slot_key === selectedSlotKey.value)) {
      selectedSlotKey.value = payload.slot_states[0]?.slot_key ?? '';
    }
    editorCode.value = selectedSlot.value?.code ?? '';
    selectedDemoStrategyId.value = selectedSlotDemoStrategies.value[0]?.strategy_id ?? '';
    await ensureGameTemplates(payload.game_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить workspace';
  } finally {
    isLoading.value = false;
  }
}

function selectSlot(slotKey: string): void {
  selectedSlotKey.value = slotKey;
  editorCode.value = workspace.value?.slot_states.find((slot) => slot.slot_key === slotKey)?.code ?? '';
  selectedDemoStrategyId.value = selectedSlotDemoStrategies.value[0]?.strategy_id ?? '';
}

function resetSelectedSlotCode(): void {
  editorCode.value = selectedSlot.value?.code ?? '';
}

async function applyTemplateToSelectedSlot(): Promise<void> {
  if (!workspace.value || !selectedSlotKey.value) return;
  isTemplateLoading.value = true;
  errorMessage.value = '';
  try {
    await ensureGameTemplates(workspace.value.game_id);
    const templateCode = templatesBySlot.value[selectedSlotKey.value];
    if (!templateCode) {
      errorMessage.value = `Для слота ${selectedSlotKey.value} шаблон не найден`;
      return;
    }
    editorCode.value = templateCode;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить шаблон';
  } finally {
    isTemplateLoading.value = false;
  }
}

async function applyDemoStrategyToSelectedSlot(): Promise<void> {
  if (!workspace.value || !selectedSlotKey.value) return;
  isTemplateLoading.value = true;
  errorMessage.value = '';
  try {
    await ensureGameTemplates(workspace.value.game_id);
    const strategies = selectedSlotDemoStrategies.value;
    const strategy =
      strategies.find((item) => item.strategy_id === selectedDemoStrategyId.value) ?? strategies[0] ?? null;
    if (!strategy) {
      errorMessage.value = `Для слота ${selectedSlotKey.value} демо-стратегия не найдена`;
      return;
    }
    selectedDemoStrategyId.value = strategy.strategy_id;
    editorCode.value = strategy.code;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить демо-стратегию';
  } finally {
    isTemplateLoading.value = false;
  }
}

async function ensureGameTemplates(gameId: string): Promise<void> {
  if (templatesGameId.value === gameId && Object.keys(templatesBySlot.value).length > 0) {
    return;
  }

  const payload = await getGameTemplates(gameId);
  templatesBySlot.value = Object.fromEntries(payload.templates.map((item) => [item.slot_key, item.code]));

  const strategiesBySlot: Record<string, GameDemoStrategyDto[]> = {};
  for (const strategy of payload.demo_strategies ?? []) {
    if (!strategiesBySlot[strategy.slot_key]) {
      strategiesBySlot[strategy.slot_key] = [];
    }
    strategiesBySlot[strategy.slot_key].push(strategy);
  }
  demoStrategiesBySlot.value = strategiesBySlot;
  templatesGameId.value = gameId;
  selectedDemoStrategyId.value = selectedSlotDemoStrategies.value[0]?.strategy_id ?? '';
}

async function saveSelectedSlotCode(): Promise<void> {
  if (!workspace.value || !selectedSlotKey.value) {
    return;
  }
  isSaving.value = true;
  errorMessage.value = '';
  try {
    await updateSlotCode({
      team_id: workspace.value.team_id,
      slot_key: selectedSlotKey.value,
      actor_user_id: sessionStore.nickname,
      code: editorCode.value,
    });
    await loadWorkspace();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось сохранить код';
  } finally {
    isSaving.value = false;
  }
}

watch(
  () => route.params.teamId,
  async () => {
    await loadWorkspace();
  }
);

onMounted(async () => {
  await loadWorkspace();
});
</script>

<style scoped>
.slot-selected {
  outline: 2px solid var(--agp-accent);
}

.demo-select {
  min-width: 190px;
}
</style>
