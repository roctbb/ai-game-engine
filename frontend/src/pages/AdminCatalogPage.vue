<template>
  <section class="agp-grid admin-catalog-page">
    <header class="agp-card p-4 admin-catalog-hero">
      <div>
        <p class="admin-catalog-kicker mb-1">Учебный каталог</p>
        <h1 class="h3 mb-1">Каталог задач</h1>
        <p class="text-muted mb-0">Подготовка учебных задач: черновик → опубликовано → архив.</p>
      </div>
      <button class="btn btn-sm btn-outline-secondary" :disabled="isLoading || !canManage" @click="loadGames">
        {{ isLoading ? 'Обновление...' : 'Обновить' }}
      </button>
    </header>

    <article class="agp-card p-3" v-if="!canManage">
      <div class="agp-empty-state agp-empty-state--compact">
        Требуется роль преподавателя или администратора. У текущего пользователя нет прав редактирования каталога.
      </div>
    </article>

    <article class="admin-catalog-metrics" aria-label="Сводка каталога задач">
      <div class="agp-card-soft p-3 admin-catalog-metric">
        <span>Всего задач</span>
        <strong class="mono">{{ totalTaskCount }}</strong>
      </div>
      <div class="agp-card-soft p-3 admin-catalog-metric admin-catalog-metric--draft">
        <span>Черновики</span>
        <strong class="mono">{{ draftCount }}</strong>
      </div>
      <div class="agp-card-soft p-3 admin-catalog-metric admin-catalog-metric--ready">
        <span>Опубликовано</span>
        <strong class="mono">{{ readyCount }}</strong>
      </div>
      <div class="agp-card-soft p-3 admin-catalog-metric admin-catalog-metric--archive">
        <span>Архив</span>
        <strong class="mono">{{ archivedCount }}</strong>
      </div>
    </article>

    <article class="agp-card p-3 admin-catalog-filter-panel">
      <div class="admin-catalog-filter-copy">
        <div class="small text-muted text-uppercase fw-semibold">Фильтр</div>
        <div class="fw-semibold">Быстро найдите задачу по статусу, названию или коду</div>
      </div>
      <div class="admin-catalog-filter-grid">
        <div>
          <label class="form-label small">Статус</label>
          <select v-model="statusFilter" class="form-select mono">
            <option value="">Все</option>
            <option value="draft">Черновики</option>
            <option value="ready">Опубликованные</option>
            <option value="archived">Архив</option>
          </select>
        </div>
        <div>
          <label class="form-label small">Поиск</label>
          <input v-model.trim="searchQuery" class="form-control" placeholder="Название или технический код" />
        </div>
        <div class="admin-catalog-filter-result">
          <span>Показано</span>
          <strong class="mono">{{ rows.length }}/{{ totalTaskCount }}</strong>
        </div>
      </div>
    </article>

    <div v-if="hasActiveFilters" class="catalog-active-filter-line">
      <span>Фильтр:</span>
      <strong>{{ activeFilterSummary }}</strong>
    </div>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <article class="agp-card p-3 admin-catalog-table-card">
      <div v-if="isLoading" class="agp-loading-state agp-loading-state--compact">Загрузка задач...</div>
      <div v-else-if="rows.length === 0" class="agp-empty-state agp-empty-state--compact">Задачи не найдены.</div>
      <div v-else class="table-responsive">
        <table class="table align-middle mb-0 admin-catalog-table">
          <thead>
            <tr>
              <th>Игра</th>
              <th>Статус</th>
              <th>Сложность</th>
              <th>Раздел</th>
              <th>Темы</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="game in rows" :key="game.game_id">
              <tr>
                <td>
                  <div class="fw-semibold">{{ game.title }}</div>
                  <div class="small text-muted mono">{{ game.slug }}</div>
                </td>
                <td><span class="admin-catalog-status" :class="statusBadgeClass(game.catalog_metadata_status)">{{ statusLabel(game.catalog_metadata_status) }}</span></td>
                <td class="small">{{ difficultyLabel(game.difficulty) }}</td>
                <td class="small">{{ game.learning_section || '—' }}</td>
                <td class="small">{{ game.topics.join(', ') || '—' }}</td>
                <td>
                  <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-outline-secondary" @click="toggleExpanded(game.game_id)">
                      {{ isExpanded(game.game_id) ? 'Свернуть' : 'Редактировать' }}
                    </button>
                    <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/tasks/${game.game_id}/run`">Открыть</RouterLink>
                  </div>
                </td>
              </tr>

              <tr v-if="isExpanded(game.game_id)">
                <td colspan="6">
                  <div class="admin-catalog-editor p-3 d-flex flex-column gap-2">
                    <div class="row g-2">
                      <div class="col-md-8">
                        <label class="form-label small">Описание</label>
                        <textarea
                          v-model="editorByGameId[game.game_id].description"
                          rows="3"
                          class="form-control"
                        />
                      </div>
                      <div class="col-md-2">
                        <label class="form-label small">Сложность</label>
                        <select v-model="editorByGameId[game.game_id].difficulty" class="form-select mono">
                          <option value="">—</option>
                          <option value="easy">легкая</option>
                          <option value="medium">средняя</option>
                          <option value="hard">сложная</option>
                        </select>
                      </div>
                      <div class="col-md-2">
                        <label class="form-label small">Статус</label>
                        <select v-model="editorByGameId[game.game_id].status" class="form-select mono">
                          <option value="draft">черновик</option>
                          <option value="ready">опубликовано</option>
                          <option value="archived">архив</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label class="form-label small">Учебный раздел</label>
                      <input
                        v-model="editorByGameId[game.game_id].learningSection"
                        class="form-control"
                        placeholder="Поиск пути BFS"
                      />
                    </div>

                    <div>
                      <label class="form-label small">Теги (через запятую)</label>
                      <input v-model="editorByGameId[game.game_id].topicsCsv" class="form-control" placeholder="графы, bfs, симуляция" />
                    </div>

                    <div class="d-flex gap-2 flex-wrap align-items-center">
                      <button
                        class="btn btn-sm btn-outline-secondary"
                        :disabled="editorByGameId[game.game_id].isSaving || !canManage"
                        @click="saveCatalogMetadata(game.game_id)"
                      >
                        {{ editorByGameId[game.game_id].isSaving ? 'Сохранение...' : 'Сохранить' }}
                      </button>
                      <button
                        class="btn btn-sm btn-outline-success"
                        :disabled="editorByGameId[game.game_id].isSaving || !canManage || !canPublishReady(game.game_id)"
                        @click="publishReady(game.game_id)"
                      >
                        Опубликовать
                      </button>
                      <button
                        class="btn btn-sm btn-outline-warning"
                        :disabled="editorByGameId[game.game_id].isSaving || !canManage"
                        @click="setDraft(game.game_id)"
                      >
                        В черновик
                      </button>
                      <button
                        class="btn btn-sm btn-outline-danger"
                        :disabled="editorByGameId[game.game_id].isSaving || !canManage"
                        @click="archiveGame(game.game_id)"
                      >
                        Архивировать
                      </button>
                      <span class="small text-muted">{{ editorHint(game.game_id) }}</span>
                    </div>

                    <div v-if="editorByGameId[game.game_id].error" class="small text-danger">
                      {{ editorByGameId[game.game_id].error }}
                    </div>
                    <div
                      v-else-if="publishValidationError(game.game_id)"
                      class="small text-warning-emphasis"
                    >
                      Для публикации: {{ publishValidationError(game.game_id) }}
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';

import { listGames, type CatalogMetadataStatus, type GameDto, updateGameCatalogMetadata } from '../lib/api';
import { useSessionStore } from '../stores/session';

interface CatalogEditorState {
  description: string;
  difficulty: '' | 'easy' | 'medium' | 'hard';
  learningSection: string;
  topicsCsv: string;
  status: CatalogMetadataStatus;
  isSaving: boolean;
  error: string;
}

const sessionStore = useSessionStore();
const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');

const isLoading = ref(false);
const errorMessage = ref('');
const games = ref<GameDto[]>([]);
const expandedGameIds = ref<Set<string>>(new Set());
const editorByGameId = ref<Record<string, CatalogEditorState>>({});

const statusFilter = ref<'' | CatalogMetadataStatus>('');
const searchQuery = ref('');

const rows = computed(() => {
  const query = searchQuery.value.toLowerCase();
  return games.value
    .filter((game) => game.mode === 'single_task')
    .filter((game) => (statusFilter.value ? game.catalog_metadata_status === statusFilter.value : true))
    .filter((game) => {
      if (!query) return true;
      return game.title.toLowerCase().includes(query) || game.slug.toLowerCase().includes(query);
    })
    .sort((left, right) => left.title.localeCompare(right.title, 'ru'));
});

const totalTaskCount = computed(() => games.value.filter((game) => game.mode === 'single_task').length);
const draftCount = computed(() => rows.value.filter((game) => game.catalog_metadata_status === 'draft').length);
const readyCount = computed(() => rows.value.filter((game) => game.catalog_metadata_status === 'ready').length);
const archivedCount = computed(() => rows.value.filter((game) => game.catalog_metadata_status === 'archived').length);
const hasActiveFilters = computed(() => Boolean(statusFilter.value || searchQuery.value));
const activeFilterSummary = computed(() => {
  const parts: string[] = [];
  if (statusFilter.value) {
    parts.push(`статус: ${statusLabel(statusFilter.value)}`);
  }
  if (searchQuery.value) {
    parts.push(`поиск: ${searchQuery.value}`);
  }
  return parts.join(' · ');
});

function statusBadgeClass(status: CatalogMetadataStatus): string {
  if (status === 'ready') return 'admin-catalog-status--ready';
  if (status === 'draft') return 'admin-catalog-status--draft';
  return 'admin-catalog-status--archived';
}

function statusLabel(status: CatalogMetadataStatus): string {
  const labels: Record<CatalogMetadataStatus, string> = {
    draft: 'черновик',
    ready: 'опубликовано',
    archived: 'архив',
  };
  return labels[status];
}

function difficultyLabel(difficulty: GameDto['difficulty']): string {
  if (difficulty === 'easy') return 'легкая';
  if (difficulty === 'medium') return 'средняя';
  if (difficulty === 'hard') return 'сложная';
  return '—';
}

function isExpanded(gameId: string): boolean {
  return expandedGameIds.value.has(gameId);
}

function toggleExpanded(gameId: string): void {
  if (expandedGameIds.value.has(gameId)) {
    expandedGameIds.value.delete(gameId);
  } else {
    expandedGameIds.value.add(gameId);
    ensureEditor(gameId);
  }
}

function ensureEditor(gameId: string): CatalogEditorState {
  const existing = editorByGameId.value[gameId];
  if (existing) return existing;
  const game = games.value.find((item) => item.game_id === gameId);
  const created: CatalogEditorState = {
    description: game?.description ?? '',
    difficulty: ((game?.difficulty ?? '') as CatalogEditorState['difficulty']),
    learningSection: game?.learning_section ?? '',
    topicsCsv: (game?.topics ?? []).join(', '),
    status: game?.catalog_metadata_status ?? 'draft',
    isSaving: false,
    error: '',
  };
  editorByGameId.value[gameId] = created;
  return created;
}

function parseTopics(topicsCsv: string): string[] {
  return topicsCsv
    .split(',')
    .map((topic) => topic.trim())
    .filter((topic) => topic.length > 0);
}

function publishValidationError(gameId: string): string {
  const editor = ensureEditor(gameId);
  if (!editor.description.trim()) {
    return 'заполните описание';
  }
  if (!editor.difficulty) {
    return 'укажите сложность';
  }
  if (!editor.learningSection.trim()) {
    return 'укажите учебный раздел';
  }
  if (parseTopics(editor.topicsCsv).length === 0) {
    return 'добавьте хотя бы одну тему';
  }
  return '';
}

function canPublishReady(gameId: string): boolean {
  return publishValidationError(gameId) === '';
}

function editorHint(gameId: string): string {
  const editor = ensureEditor(gameId);
  if (editor.isSaving) return 'Сохраняем изменения...';
  const validationError = publishValidationError(gameId);
  if (editor.status === 'ready' && validationError) return `Нельзя опубликовать: ${validationError}.`;
  if (editor.status === 'ready') return 'Задача появится в каталоге учеников.';
  if (editor.status === 'archived') return 'Архивные задачи скрыты из каталога учеников.';
  return 'Черновик виден только преподавателю и администратору.';
}

async function loadGames(): Promise<void> {
  if (!canManage.value) {
    games.value = [];
    return;
  }
  isLoading.value = true;
  errorMessage.value = '';
  try {
    games.value = await listGames();
    const nextEditors: Record<string, CatalogEditorState> = {};
    for (const game of games.value) {
      if (game.mode !== 'single_task') continue;
      const existing = editorByGameId.value[game.game_id];
      nextEditors[game.game_id] = {
        description: existing?.description ?? game.description ?? '',
        difficulty: (existing?.difficulty ?? (game.difficulty ?? '')) as CatalogEditorState['difficulty'],
        learningSection: existing?.learningSection ?? game.learning_section ?? '',
        topicsCsv: existing?.topicsCsv ?? game.topics.join(', '),
        status: existing?.status ?? game.catalog_metadata_status,
        isSaving: false,
        error: '',
      };
    }
    editorByGameId.value = nextEditors;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить каталог задач';
  } finally {
    isLoading.value = false;
  }
}

async function saveCatalogMetadata(gameId: string): Promise<void> {
  if (!canManage.value) return;
  const editor = ensureEditor(gameId);
  editor.error = '';
  if (editor.status === 'ready') {
    const validationError = publishValidationError(gameId);
    if (validationError) {
      editor.error = `Для публикации: ${validationError}`;
      return;
    }
  }
  editor.isSaving = true;
  try {
    const payload = {
      game_id: gameId,
      description: editor.description.trim() ? editor.description.trim() : null,
      difficulty: editor.difficulty || null,
      learning_section: editor.learningSection.trim() ? editor.learningSection.trim() : null,
      topics: parseTopics(editor.topicsCsv),
      catalog_metadata_status: editor.status,
    };

    const updated = await updateGameCatalogMetadata(payload);
    const index = games.value.findIndex((game) => game.game_id === gameId);
    if (index >= 0) {
      games.value[index] = updated;
    }
    editor.description = updated.description ?? '';
    editor.difficulty = ((updated.difficulty ?? '') as CatalogEditorState['difficulty']);
    editor.learningSection = updated.learning_section ?? '';
    editor.topicsCsv = updated.topics.join(', ');
    editor.status = updated.catalog_metadata_status;
  } catch (error) {
    editor.error = error instanceof Error ? error.message : 'Не удалось сохранить метаданные';
  } finally {
    editor.isSaving = false;
  }
}

async function publishReady(gameId: string): Promise<void> {
  const editor = ensureEditor(gameId);
  const validationError = publishValidationError(gameId);
  if (validationError) {
    editor.error = `Для публикации: ${validationError}`;
    return;
  }
  editor.status = 'ready';
  await saveCatalogMetadata(gameId);
}

async function setDraft(gameId: string): Promise<void> {
  const editor = ensureEditor(gameId);
  editor.status = 'draft';
  await saveCatalogMetadata(gameId);
}

async function archiveGame(gameId: string): Promise<void> {
  const editor = ensureEditor(gameId);
  editor.status = 'archived';
  await saveCatalogMetadata(gameId);
}

onMounted(async () => {
  await loadGames();
});

watch(
  canManage,
  async (nextValue) => {
    if (nextValue && games.value.length === 0) {
      await loadGames();
    }
  },
  { flush: 'post' }
);
</script>

<style scoped>
.admin-catalog-page {
  gap: 0.9rem;
}

.admin-catalog-hero {
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  background:
    radial-gradient(circle at 12% 18%, rgba(20, 184, 166, 0.18), transparent 15rem),
    radial-gradient(circle at 88% 12%, rgba(245, 158, 11, 0.16), transparent 14rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.9)),
    url("data:image/svg+xml,%3Csvg width='184' height='112' viewBox='0 0 184 112' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%230f766e' stroke-opacity='.14' stroke-width='2'%3E%3Cpath d='M22 22h34v28H22zM76 18h34v28H76zM132 30h30v26h-30zM50 72h32v22H50zM106 68h34v26h-34z'/%3E%3Cpath d='M56 36h20M110 32h22M82 82h24M92 46v22'/%3E%3C/g%3E%3C/svg%3E");
  background-position: center, center, center, right 1rem center;
  background-repeat: no-repeat;
}

.admin-catalog-hero::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.25rem;
  background: linear-gradient(90deg, #14b8a6, #f59e0b, #2563eb);
}

.admin-catalog-hero > * {
  position: relative;
}

.admin-catalog-kicker {
  color: #0f766e;
  font-size: 0.74rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.admin-catalog-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
}

.admin-catalog-metric {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 0.05rem;
  border-color: rgba(148, 163, 184, 0.34);
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}

.admin-catalog-metric::after {
  content: '';
  position: absolute;
  right: -1.2rem;
  bottom: -1.35rem;
  width: 4.5rem;
  height: 4.5rem;
  border-radius: 1.1rem;
  background: rgba(37, 99, 235, 0.08);
  transform: rotate(18deg);
}

.admin-catalog-metric--draft::after {
  background: rgba(245, 158, 11, 0.16);
}

.admin-catalog-metric--ready::after {
  background: rgba(34, 197, 94, 0.12);
}

.admin-catalog-metric--archive::after {
  background: rgba(100, 116, 139, 0.12);
}

.admin-catalog-metric span {
  color: var(--agp-text-muted);
  font-size: 0.78rem;
  font-weight: 750;
}

.admin-catalog-metric strong {
  color: var(--agp-text);
  font-size: 1.45rem;
}

.admin-catalog-filter-panel {
  display: grid;
  grid-template-columns: minmax(16rem, 0.8fr) minmax(0, 1.6fr);
  gap: 1rem;
  align-items: end;
}

.admin-catalog-filter-grid {
  display: grid;
  grid-template-columns: minmax(9rem, 0.7fr) minmax(12rem, 1fr) auto;
  gap: 0.75rem;
  align-items: end;
}

.admin-catalog-filter-result {
  display: grid;
  gap: 0.05rem;
  border: 1px solid rgba(148, 163, 184, 0.34);
  border-radius: 0.75rem;
  background: #f8fafc;
  padding: 0.55rem 0.7rem;
}

.admin-catalog-filter-result span {
  color: var(--agp-text-muted);
  font-size: 0.72rem;
  font-weight: 750;
}

.admin-catalog-filter-result strong {
  color: var(--agp-text);
}

.admin-catalog-table-card,
.admin-catalog-editor {
  position: relative;
  overflow: hidden;
}

.admin-catalog-table-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 0.18rem;
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.72), rgba(37, 99, 235, 0.5), transparent);
}

.admin-catalog-table-card > * {
  position: relative;
}

.admin-catalog-table {
  --bs-table-bg: transparent;
  --bs-table-striped-bg: rgba(248, 250, 252, 0.82);
  border-color: rgba(148, 163, 184, 0.24);
}

.admin-catalog-table thead th {
  color: var(--agp-text-muted);
  font-size: 0.74rem;
  font-weight: 850;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.admin-catalog-status {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 0.16rem 0.55rem;
  font-size: 0.74rem;
  font-weight: 850;
  white-space: nowrap;
}

.admin-catalog-status--ready {
  border-color: #86efac;
  background: #dcfce7;
  color: #166534;
}

.admin-catalog-status--draft {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #9a3412;
}

.admin-catalog-status--archived {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #475569;
}

.admin-catalog-editor {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 0.85rem;
  background:
    radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.1), transparent 10rem),
    #f8fafc;
}

.catalog-active-filter-line {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  color: var(--agp-text-muted);
  font-size: 0.86rem;
}

.catalog-active-filter-line strong {
  color: var(--agp-text);
  font-weight: 600;
}

@media (max-width: 1100px) {
  .admin-catalog-filter-panel {
    grid-template-columns: 1fr;
  }

  .admin-catalog-metrics,
  .admin-catalog-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .admin-catalog-hero {
    flex-direction: column;
  }

  .admin-catalog-metrics,
  .admin-catalog-filter-grid {
    grid-template-columns: 1fr;
  }
}
</style>
