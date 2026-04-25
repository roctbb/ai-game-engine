<template>
  <section class="agp-grid workspace-page">
    <header class="agp-card p-4 workspace-hero">
      <div>
        <div class="small text-muted text-uppercase fw-semibold">Просмотр кода игрока</div>
        <h1 class="h3 mb-1">Код игрока</h1>
        <p class="text-muted mb-0">
          <template v-if="canEditWorkspace">
            Сохраненный код будет использоваться в новых запусках после старта.
          </template>
          <template v-else>
            Режим просмотра кода игрока. Редактировать может владелец.
          </template>
        </p>
      </div>
      <div class="workspace-hero-stats">
        <span class="agp-pill agp-pill--primary">ролей: {{ slotCount }}</span>
        <span class="agp-pill" :class="emptySlotCount > 0 ? 'agp-pill--warning' : 'agp-pill--primary'">
          не заполнено: {{ emptySlotCount }}
        </span>
      </div>
    </header>

    <div v-if="isLoading" class="agp-card p-4 text-muted">Загрузка кода игрока...</div>
    <div v-else-if="errorMessage" class="agp-card p-4 text-danger">{{ errorMessage }}</div>

    <div v-else class="workspace-layout">
      <aside class="agp-card p-3 workspace-slots">
        <div class="d-flex justify-content-between align-items-center gap-2 mb-3">
          <div>
            <h2 class="h6 mb-1">Роли игрока</h2>
            <div class="small text-muted">Роли, которые игра ожидает от участника.</div>
          </div>
        </div>
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
              <div class="small text-muted">{{ slot.required ? 'обязательная роль' : 'необязательная роль' }}</div>
            </div>
            <SlotStateBadge :slot-state="slot.state" />
          </button>
        </div>
      </aside>

      <article class="agp-card p-3 workspace-editor">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Редактор роли `{{ selectedSlotKey || '—' }}`</h2>
          <div v-if="canEditWorkspace" class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-secondary" :disabled="!selectedSlotKey || !isEditorDirty" @click="resetSelectedSlotCode">
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
              v-if="canUseDemoStrategy"
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
              v-if="canUseDemoStrategy"
              class="btn btn-sm btn-outline-primary"
              :disabled="!selectedSlotKey || isTemplateLoading"
              @click="applyDemoStrategyToSelectedSlot"
            >
              Демо
            </button>
            <button class="btn btn-sm btn-dark" :disabled="!selectedSlotKey || isSaving || !isEditorDirty" @click="saveSelectedSlotCode">
              {{ isSaving ? 'Сохранение...' : 'Сохранить изменения' }}
            </button>
          </div>
          <span v-else class="badge text-bg-light">только просмотр</span>
        </div>
        <div v-if="canEditWorkspace && isEditorDirty" class="workspace-editor-notice mb-2">
          Есть несохраненные изменения. Они попадут в новые запуски только после сохранения.
        </div>
        <div v-if="pendingSlotKey" class="workspace-switch-notice mb-2">
          <div>
            <div class="fw-semibold">Перейти к роли `{{ pendingSlotKey }}`?</div>
            <div class="small text-muted">В текущей роли есть несохраненный код.</div>
          </div>
          <div class="d-flex gap-2 flex-wrap">
            <button class="btn btn-sm btn-dark" :disabled="isSaving" @click="saveAndSwitchSlot">
              {{ isSaving ? 'Сохраняем...' : 'Сохранить и перейти' }}
            </button>
            <button class="btn btn-sm btn-outline-secondary" @click="discardAndSwitchSlot">Перейти без сохранения</button>
            <button class="btn btn-sm btn-link" @click="pendingSlotKey = ''">Остаться</button>
          </div>
        </div>
        <CodeEditor
          v-model="editorCode"
          :readonly="!selectedSlotKey || !canEditWorkspace"
          language="python"
        />
        <div class="small text-muted mt-2">Подсветка синтаксиса Python доступна в редакторе.</div>
        <div v-if="canEditWorkspace" class="small text-muted mt-1">
          <template v-if="canUseDemoStrategy">
            Кнопки «Шаблон» и «Демо» подставляют стартовый код или готовую демо-стратегию.
          </template>
          <template v-else>
            Кнопка «Шаблон» подставляет стартовый код для выбранной роли.
          </template>
        </div>
        <div class="small text-muted mt-1">
          <template v-if="canEditWorkspace">
            Изменения здесь попадут только в новые запуски.
          </template>
          <template v-else>
            Это безопасный просмотр текущего кода. Новые запуски не создаются.
          </template>
        </div>
      </article>

      <aside class="agp-card p-3 workspace-inspector">
        <h2 class="h6 mb-2">Сводка</h2>
        <div class="workspace-inspector-row">
          <span>Режим</span>
          <strong>{{ canEditWorkspace ? 'редактирование' : 'просмотр' }}</strong>
        </div>
        <div class="workspace-inspector-row">
          <span>Владелец</span>
          <strong class="mono">{{ workspace?.captain_user_id }}</strong>
        </div>
        <div class="workspace-inspector-row">
          <span>Выбранная роль</span>
          <strong class="mono">{{ selectedSlotKey || '—' }}</strong>
        </div>
        <div class="workspace-inspector-row">
          <span>Состояние роли</span>
          <strong>{{ selectedSlot ? slotStateLabel(selectedSlot.state) : '—' }}</strong>
        </div>
        <div v-if="canEditWorkspace" class="workspace-inspector-row">
          <span>Изменения</span>
          <strong :class="isEditorDirty ? 'text-warning-emphasis' : ''">
            {{ isEditorDirty ? 'не сохранены' : 'сохранены' }}
          </strong>
        </div>
        <div class="workspace-callout mt-3">
          <div class="fw-semibold mb-1">Что попадет в матч?</div>
          <div class="small text-muted">
            Если запуск создать сейчас, платформа возьмет текущие сохраненные версии кода. Несохраненный текст в редакторе в матч не попадет.
          </div>
        </div>
        <div v-if="incompatibleSlotCount > 0" class="workspace-callout workspace-callout--warning mt-2">
          <div class="fw-semibold mb-1">Есть несовместимые роли</div>
          <div class="small">
            {{ incompatibleSlotCount }} роль(ей) больше не требуется текущей версией игры. Код виден, но не участвует в новых матчах.
          </div>
        </div>
        <details v-if="canInspectTechnicalDetails" class="workspace-technical mt-3">
          <summary class="small text-muted">Технические детали</summary>
          <div class="mono small mt-2">version: {{ workspace?.version_id }}</div>
          <div class="mono small text-muted">player_id: {{ workspace?.team_id }}</div>
        </details>
      </aside>
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
const pendingSlotKey = ref('');
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
const canEditWorkspace = computed(() => workspace.value?.captain_user_id === sessionStore.nickname);
const selectedSlotDemoStrategies = computed(() => demoStrategiesBySlot.value[selectedSlotKey.value] ?? []);
const canInspectTechnicalDetails = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');
const canUseDemoStrategy = computed(() => canInspectTechnicalDetails.value);
const slotCount = computed(() => workspace.value?.slot_states.length ?? 0);
const emptySlotCount = computed(() => workspace.value?.slot_states.filter((slot) => slot.state === 'empty').length ?? 0);
const incompatibleSlotCount = computed(
  () => workspace.value?.slot_states.filter((slot) => slot.state === 'incompatible').length ?? 0
);
const savedSelectedSlotCode = computed(() => selectedSlot.value?.code ?? '');
const isEditorDirty = computed(() => editorCode.value !== savedSelectedSlotCode.value);

function slotStateLabel(state: string): string {
  const labels: Record<string, string> = {
    filled: 'заполнен',
    empty: 'пустой',
    dirty: 'изменен',
    locked: 'заблокирован',
    incompatible: 'несовместим',
  };
  return labels[state] ?? state;
}

async function loadWorkspace(): Promise<void> {
  const teamId = String(route.params.teamId || '').trim();
  if (!teamId) {
    errorMessage.value = 'Не найден игрок для просмотра кода';
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
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить код игрока';
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
  pendingSlotKey.value = '';
  editorCode.value = workspace.value?.slot_states.find((slot) => slot.slot_key === slotKey)?.code ?? '';
  selectedDemoStrategyId.value = selectedSlotDemoStrategies.value[0]?.strategy_id ?? '';
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
      errorMessage.value = `Для роли ${selectedSlotKey.value} шаблон не найден`;
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
  if (!canUseDemoStrategy.value) return;
  if (!workspace.value || !selectedSlotKey.value) return;
  isTemplateLoading.value = true;
  errorMessage.value = '';
  try {
    await ensureGameTemplates(workspace.value.game_id);
    const strategies = selectedSlotDemoStrategies.value;
    const strategy =
      strategies.find((item) => item.strategy_id === selectedDemoStrategyId.value) ?? strategies[0] ?? null;
    if (!strategy) {
      errorMessage.value = `Для роли ${selectedSlotKey.value} демо-стратегия не найдена`;
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
    pendingSlotKey.value = '';
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
.workspace-page {
  gap: 0.9rem;
}

.workspace-hero {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  background: #f8fafc;
}

.workspace-hero-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  justify-content: flex-end;
}

.workspace-layout {
  display: grid;
  grid-template-columns: minmax(14rem, 0.55fr) minmax(0, 1.35fr) minmax(18rem, 0.7fr);
  gap: 0.9rem;
  align-items: start;
}

.workspace-slots,
.workspace-inspector {
  position: sticky;
  top: 0.85rem;
}

.workspace-editor {
  min-width: 0;
}

.workspace-editor-notice {
  border: 1px solid rgba(217, 119, 6, 0.26);
  border-radius: 8px;
  background: rgba(255, 251, 235, 0.88);
  color: #8a4b0c;
  padding: 0.55rem 0.7rem;
  font-size: 0.86rem;
}

.workspace-switch-notice {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 8px;
  background: #f8fafc;
  padding: 0.65rem 0.75rem;
}

.slot-selected {
  outline: 2px solid var(--agp-accent);
}

.demo-select {
  min-width: 190px;
}

.workspace-inspector-row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  font-size: 0.86rem;
}

.workspace-inspector-row span {
  color: var(--agp-muted);
}

.workspace-inspector-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: right;
}

.workspace-callout {
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: 1rem;
  background: rgba(240, 253, 250, 0.76);
  padding: 0.8rem;
}

.workspace-callout--warning {
  border-color: rgba(217, 119, 6, 0.26);
  background: rgba(255, 251, 235, 0.88);
  color: #8a4b0c;
}

@media (max-width: 1180px) {
  .workspace-layout {
    grid-template-columns: minmax(13rem, 0.55fr) minmax(0, 1fr);
  }

  .workspace-inspector {
    grid-column: 1 / -1;
    position: static;
  }
}

@media (max-width: 820px) {
  .workspace-hero {
    flex-direction: column;
  }

  .workspace-hero-stats {
    justify-content: flex-start;
  }

  .workspace-layout {
    grid-template-columns: 1fr;
  }

  .workspace-slots {
    position: static;
  }
}
</style>
