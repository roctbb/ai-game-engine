<template>
  <section class="agp-grid">
    <header class="d-flex justify-content-between align-items-start gap-3 flex-wrap">
      <div>
        <h1 class="h3 mb-1">Каталог задач</h1>
        <p class="text-muted mb-0">Подготовка учебных задач: черновик → опубликовано → архив.</p>
      </div>
      <button class="btn btn-sm btn-outline-secondary" :disabled="isLoading || !canManage" @click="loadGames">
        {{ isLoading ? 'Обновление...' : 'Обновить' }}
      </button>
    </header>

    <article class="agp-card p-3" v-if="!canManage">
      <div class="text-warning-emphasis fw-semibold">Требуется роль преподавателя или администратора</div>
      <div class="small text-muted">У текущего пользователя нет прав редактирования каталога.</div>
    </article>

    <article class="agp-card p-3">
      <div class="row g-2 align-items-end">
        <div class="col-md-3">
          <label class="form-label small">Статус</label>
          <select v-model="statusFilter" class="form-select mono">
            <option value="">Все</option>
            <option value="draft">Черновики</option>
            <option value="ready">Опубликованные</option>
            <option value="archived">Архив</option>
          </select>
        </div>
        <div class="col-md-4">
          <label class="form-label small">Поиск</label>
          <input v-model.trim="searchQuery" class="form-control" placeholder="Название или технический код" />
        </div>
        <div class="col-md-5 small text-muted catalog-summary">
          Показано: <span class="mono">{{ rows.length }}</span>
          из <span class="mono">{{ totalTaskCount }}</span>
          · черновиков: <span class="mono">{{ draftCount }}</span>
          · опубликовано: <span class="mono">{{ readyCount }}</span>
          · архив: <span class="mono">{{ archivedCount }}</span>
        </div>
      </div>
    </article>

    <div v-if="hasActiveFilters" class="catalog-active-filter-line">
      <span>Фильтр:</span>
      <strong>{{ activeFilterSummary }}</strong>
    </div>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <article class="agp-card p-3">
      <div v-if="isLoading" class="small text-muted">Загрузка задач...</div>
      <div v-else-if="rows.length === 0" class="small text-muted">Задачи не найдены.</div>
      <div v-else class="table-responsive">
        <table class="table align-middle mb-0">
          <thead>
            <tr>
              <th>Игра</th>
              <th>Статус</th>
              <th>Сложность</th>
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
                <td><span class="badge" :class="statusBadgeClass(game.catalog_metadata_status)">{{ statusLabel(game.catalog_metadata_status) }}</span></td>
                <td class="small">{{ difficultyLabel(game.difficulty) }}</td>
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
                <td colspan="5">
                  <div class="agp-card-soft p-3 d-flex flex-column gap-2">
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
                      <label class="form-label small">Темы (через запятую)</label>
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
  if (status === 'ready') return 'text-bg-success';
  if (status === 'draft') return 'text-bg-warning';
  return 'text-bg-secondary';
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
.catalog-summary {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
  align-items: center;
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
</style>
