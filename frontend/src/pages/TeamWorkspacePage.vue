<template>
  <section class="agp-grid workspace-page">
    <header class="agp-card p-4 workspace-hero">
      <div>
        <p class="workspace-kicker mb-1">{{ canEditWorkspace ? 'Рабочее место игрока' : 'Просмотр кода игрока' }}</p>
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
        <div>
          <span>Ролей</span>
          <strong class="mono">{{ slotCount }}</strong>
        </div>
        <div>
          <span>Заполнено</span>
          <strong class="mono">{{ filledSlotCount }}</strong>
        </div>
        <div>
          <span>Готовность</span>
          <strong class="mono">{{ workspaceReadyPercent }}%</strong>
        </div>
      </div>
    </header>

    <div v-if="isLoading" class="agp-card p-4">
      <div class="agp-loading-state agp-loading-state--compact">Загрузка кода игрока...</div>
    </div>
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
            class="workspace-slot-button"
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
        <div class="workspace-editor-head mb-2">
          <div>
            <p class="workspace-kicker mb-1">Python</p>
            <h2 class="h6 mb-0">Роль: <span class="mono">{{ selectedSlotKey || '—' }}</span></h2>
          </div>
          <div v-if="canEditWorkspace" class="workspace-editor-actions">
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
        <div class="workspace-inspector-head mb-2">
          <p class="workspace-kicker mb-1">Сводка</p>
          <h2 class="h6 mb-0">Состояние игрока</h2>
        </div>
        <div class="workspace-progress" role="progressbar" :aria-valuenow="workspaceReadyPercent" aria-valuemin="0" aria-valuemax="100">
          <i :style="{ width: `${workspaceReadyPercent}%` }"></i>
        </div>
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
const filledSlotCount = computed(() =>
  workspace.value?.slot_states.filter((slot) => slot.state !== 'empty' && slot.state !== 'incompatible').length ?? 0
);
const workspaceReadyPercent = computed(() =>
  slotCount.value > 0 ? Math.round((filledSlotCount.value / slotCount.value) * 100) : 0
);
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
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  background:
    radial-gradient(circle at 14% 18%, rgba(20, 184, 166, 0.18), transparent 15rem),
    radial-gradient(circle at 88% 12%, rgba(37, 99, 235, 0.14), transparent 14rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(240, 253, 250, 0.9)),
    url("data:image/svg+xml,%3Csvg width='176' height='112' viewBox='0 0 176 112' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.14' stroke-width='2'%3E%3Cpath d='M24 24h34v34H24zM78 18h28v28H78zM130 34h26v26h-26zM50 72h28v20H50zM108 68h30v28h-30z'/%3E%3Cpath d='M58 41h20M106 32h24M78 82h30M92 46v22'/%3E%3C/g%3E%3C/svg%3E");
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.workspace-hero::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.25rem;
  background: linear-gradient(90deg, #14b8a6, #2563eb, #f59e0b);
}

.workspace-hero > * {
  position: relative;
}

.workspace-kicker {
  color: #0f766e;
  font-size: 0.74rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.workspace-hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(5.5rem, 1fr));
  gap: 0.55rem;
  min-width: min(100%, 24rem);
}

.workspace-hero-stats div {
  display: grid;
  gap: 0.05rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 0.85rem;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.workspace-hero-stats span {
  color: var(--agp-text-muted);
  font-size: 0.72rem;
  font-weight: 750;
}

.workspace-hero-stats strong {
  color: var(--agp-text);
  font-size: 1.16rem;
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
  overflow: hidden;
  min-width: 0;
}

.workspace-slots,
.workspace-inspector,
.workspace-editor {
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.07);
}

.workspace-slot-button {
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 0.75rem;
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.1), transparent 6rem),
    #ffffff;
  color: inherit;
  padding: 0.7rem;
  text-align: left;
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.workspace-slot-button:hover {
  border-color: rgba(20, 184, 166, 0.45);
  box-shadow: 0 12px 26px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.workspace-editor-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.15rem 0 0.65rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
}

.workspace-editor-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.45rem;
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
  border-color: rgba(15, 118, 110, 0.6);
  outline: 2px solid rgba(20, 184, 166, 0.18);
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.17), transparent 6rem),
    #f0fdfa;
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

.workspace-progress {
  height: 0.55rem;
  overflow: hidden;
  border-radius: 999px;
  background: #dbeafe;
  margin-bottom: 0.75rem;
}

.workspace-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #14b8a6, #f59e0b);
  transition: width 0.2s ease;
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
    grid-template-columns: repeat(3, minmax(0, 1fr));
    min-width: 0;
    width: 100%;
  }

  .workspace-layout {
    grid-template-columns: 1fr;
  }

  .workspace-slots {
    position: static;
  }

  .workspace-editor-head {
    flex-direction: column;
  }

  .workspace-editor-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 560px) {
  .workspace-hero-stats {
    grid-template-columns: 1fr;
  }
}
</style>
