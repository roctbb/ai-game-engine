<template>
  <section class="admin-catalog-page" :class="{ 'admin-catalog-page--focused': focusedGameId }">
    <header class="admin-catalog-header">
      <RouterLink class="btn btn-outline-secondary" :to="focusedGameId ? `/tasks/${focusedGameId}` : '/tasks'">← {{ focusedGameId ? 'К задаче' : 'Материалы' }}</RouterLink>
      <div class="admin-catalog-heading">
        <p v-if="focusedGameId">Настройки задачи</p>
        <h1>{{ focusedGameId ? (focusedGame?.title || 'Настройки задачи') : 'Каталог задач' }}</h1>
      </div>
      <RouterLink v-if="focusedGameId" class="btn btn-outline-secondary" to="/admin/catalog">Все задачи</RouterLink>
      <button v-else class="btn btn-outline-secondary" :disabled="isLoading || !canManage" @click="loadGames">Обновить</button>
    </header>

    <p v-if="!canManage" role="alert" class="text-danger">Недостаточно прав для редактирования.</p>
    <p v-if="errorMessage" role="alert" class="text-danger">{{ errorMessage }}</p>
    <template v-if="canManage">
      <div v-if="!focusedGameId" class="agp-card admin-catalog-filters">
        <label class="admin-catalog-search">Поиск<input v-model.trim="searchQuery" class="form-control" type="search" placeholder="Название задачи" /></label>
        <label>Статус<select v-model="statusFilter" class="form-select"><option value="">Все</option><option value="draft">Черновики</option><option value="ready">Опубликованные</option><option value="archived">Архив</option></select></label>
        <label>Видимость<select v-model="visibilityFilter" class="form-select"><option value="">Все</option><option value="visible">Доступные</option><option value="hidden">Скрытые</option></select></label>
        <span class="admin-catalog-count mono">{{ rows.length }} / {{ totalTaskCount }}</span>
      </div>
      <LoadingSkeleton v-if="isLoading" :count="2" layout="list" label="Загрузка задач" />
      <p v-else-if="!rows.length" class="text-muted">{{ focusedGameId ? 'Задача не найдена.' : 'Задачи не найдены.' }}</p>
      <div v-else class="admin-catalog-list">
        <article v-for="game in rows" :key="game.game_id" class="agp-card admin-catalog-item">
          <header v-if="!focusedGameId" class="admin-catalog-item-head">
            <div class="admin-catalog-item-title">
              <h2>{{ game.title }}</h2>
              <span class="text-muted">{{ [game.learning_section, difficultyLabel(game.difficulty) !== '—' ? difficultyLabel(game.difficulty) : ''].filter(Boolean).join(' · ') }}</span>
            </div>
            <div class="admin-catalog-badges">
              <span class="admin-catalog-status" :class="statusBadgeClass(game.catalog_metadata_status)">{{ statusLabel(game.catalog_metadata_status) }}</span>
              <span class="admin-catalog-status" :class="visibilityBadgeClass(game.is_hidden)">{{ visibilityLabel(game.is_hidden) }}</span>
            </div>
            <div class="admin-catalog-row-actions">
              <RouterLink class="btn btn-outline-secondary" :to="`/tasks/${game.game_id}`">Открыть</RouterLink>
              <button class="btn btn-outline-secondary" :aria-expanded="isExpanded(game.game_id)" @click="toggleExpanded(game.game_id)">{{ isExpanded(game.game_id) ? 'Свернуть' : 'Изменить' }}</button>
            </div>
          </header>
          <form v-if="isExpanded(game.game_id)" class="admin-catalog-editor" :class="{ 'admin-catalog-editor--nested': !focusedGameId }" @submit.prevent="saveCatalogMetadata(game.game_id)">
            <div class="admin-catalog-editor-grid">
              <label class="admin-catalog-description">Описание<textarea v-model="editorByGameId[game.game_id].description" class="form-control" rows="5" /></label>
              <label>Сложность<select v-model="editorByGameId[game.game_id].difficulty" class="form-select"><option value="">Не указана</option><option value="easy">Лёгкая</option><option value="medium">Средняя</option><option value="hard">Сложная</option></select></label>
              <label>Статус<select v-model="editorByGameId[game.game_id].status" class="form-select"><option value="draft">Черновик</option><option value="ready">Опубликовано</option><option value="archived">Архив</option></select></label>
              <label>Раздел<input v-model="editorByGameId[game.game_id].learningSection" class="form-control" /></label>
              <label>Темы через запятую<input v-model="editorByGameId[game.game_id].topicsCsv" class="form-control" /></label>
            </div>
            <label class="admin-catalog-visibility-toggle"><input v-model="editorByGameId[game.game_id].isHidden" class="form-check-input" type="checkbox" /><span>Скрыть задачу</span></label>
            <p v-if="editorByGameId[game.game_id].error" role="alert" class="text-danger">{{ editorByGameId[game.game_id].error }}</p>
            <footer class="admin-catalog-editor-footer">
              <button class="btn btn-primary" :disabled="editorByGameId[game.game_id].isSaving || !isDirty(game)" type="submit">{{ editorByGameId[game.game_id].isSaving ? 'Сохраняем…' : savedGameIds.has(game.game_id) && !isDirty(game) ? 'Сохранено' : 'Сохранить' }}</button>
              <span v-if="savedGameIds.has(game.game_id) && !isDirty(game)" class="admin-catalog-save-status" role="status">Изменения сохранены</span>
            </footer>
          </form>
        </article>
      </div>
      <details v-if="!focusedGameId && sectionVisibilityRows.length" class="agp-card admin-catalog-sections">
        <summary>Видимость разделов</summary>
        <div class="admin-section-list">
          <div v-for="section in sectionVisibilityRows" :key="section.name" class="admin-section-row">
            <div><strong>{{ section.name }}</strong><span class="text-muted">{{ section.visibleCount }} / {{ section.total }} доступны</span></div>
            <div class="admin-catalog-row-actions">
              <button class="btn btn-outline-secondary" :disabled="section.isSaving || section.allHidden" @click="setSectionHidden(section.name, true)">Скрыть</button>
              <button class="btn btn-outline-secondary" :disabled="section.isSaving || !section.hiddenCount" @click="setSectionHidden(section.name, false)">Показать</button>
            </div>
          </div>
        </div>
      </details>
    </template>
  </section>
</template>

<script setup lang="ts">
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import { listGames, type CatalogMetadataStatus, type GameDto, updateGameCatalogMetadata } from '../lib/api';
import { useSessionStore } from '../stores/session';

interface CatalogEditorState {
  description: string;
  difficulty: '' | 'easy' | 'medium' | 'hard';
  learningSection: string;
  topicsCsv: string;
  status: CatalogMetadataStatus;
  isHidden: boolean;
  isSaving: boolean;
  error: string;
}

const sessionStore = useSessionStore();
const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');

const isLoading = ref(false);
const errorMessage = ref('');
const route = useRoute();
const focusedGameId = computed(() => typeof route.query.game_id === 'string' ? route.query.game_id : '');
const focusedGame = computed(() => games.value.find(game => game.game_id === focusedGameId.value));
const games = ref<GameDto[]>([]);
const expandedGameIds = ref<Set<string>>(new Set());
const editorByGameId = ref<Record<string, CatalogEditorState>>({});
const sectionSavingByName = ref<Record<string, boolean>>({});
const savedGameIds = ref(new Set<string>());

function isDirty(game: GameDto): boolean {
  const editor = editorByGameId.value[game.game_id];
  return Boolean(editor && (editor.description.trim() !== (game.description ?? '') || editor.difficulty !== (game.difficulty ?? '') || editor.learningSection.trim() !== (game.learning_section ?? '') || JSON.stringify(parseTopics(editor.topicsCsv)) !== JSON.stringify(game.topics) || editor.status !== game.catalog_metadata_status || editor.isHidden !== game.is_hidden));
}

const statusFilter = ref<'' | CatalogMetadataStatus>('');
const visibilityFilter = ref<'' | 'visible' | 'hidden'>('');
const searchQuery = ref('');

const rows = computed(() => {
  const query = searchQuery.value.toLowerCase();
  return games.value
    .filter((game) => game.mode === 'single_task')
    .filter((game) => !focusedGameId.value || game.game_id === focusedGameId.value)
    .filter((game) => (statusFilter.value ? game.catalog_metadata_status === statusFilter.value : true))
    .filter((game) => {
      if (visibilityFilter.value === 'visible') return !game.is_hidden;
      if (visibilityFilter.value === 'hidden') return game.is_hidden;
      return true;
    })
    .filter((game) => {
      if (!query) return true;
      return game.title.toLowerCase().includes(query) || game.slug.toLowerCase().includes(query);
    })
    .sort((left, right) => left.title.localeCompare(right.title, 'ru'));
});

const totalTaskCount = computed(() => games.value.filter((game) => game.mode === 'single_task').length);
const sectionVisibilityRows = computed(() => {
  const groups = new Map<string, GameDto[]>();
  for (const game of games.value) {
    if (game.mode !== 'single_task') continue;
    const section = game.learning_section || 'Другое';
    const items = groups.get(section) ?? [];
    items.push(game);
    groups.set(section, items);
  }

  return Array.from(groups.entries())
    .map(([name, items]) => {
      const hiddenCount = items.filter((game) => game.is_hidden).length;
      const total = items.length;
      return {
        name,
        total,
        hiddenCount,
        visibleCount: total - hiddenCount,
        allHidden: total > 0 && hiddenCount === total,
        isSaving: Boolean(sectionSavingByName.value[name]),
      };
    })
    .sort((left, right) => left.name.localeCompare(right.name, 'ru'));
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

function visibilityBadgeClass(isHidden: boolean): string {
  return isHidden ? 'admin-catalog-status--hidden' : 'admin-catalog-status--visible';
}

function visibilityLabel(isHidden: boolean): string {
  return isHidden ? 'Скрыта' : 'Доступна';
}

function difficultyLabel(difficulty: GameDto['difficulty']): string {
  if (difficulty === 'easy') return 'легкая';
  if (difficulty === 'medium') return 'средняя';
  if (difficulty === 'hard') return 'сложная';
  return '—';
}

function isExpanded(gameId: string): boolean {
  return focusedGameId.value === gameId || expandedGameIds.value.has(gameId);
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
    isHidden: game?.is_hidden ?? false,
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
        isHidden: existing?.isHidden ?? game.is_hidden,
        isSaving: false,
        error: '',
      };
    }
    editorByGameId.value = nextEditors;
    if (focusedGameId.value) expandedGameIds.value.add(focusedGameId.value);
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
      is_hidden: editor.isHidden,
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
    editor.isHidden = updated.is_hidden;
    savedGameIds.value.add(gameId);
  } catch (error) {
    editor.error = error instanceof Error ? error.message : 'Не удалось сохранить метаданные';
  } finally {
    editor.isSaving = false;
  }
}

async function setTaskHidden(gameId: string, isHidden: boolean): Promise<void> {
  if (!canManage.value) return;
  const game = games.value.find((item) => item.game_id === gameId);
  if (!game) return;
  const editor = editorByGameId.value[gameId];
  if (editor) {
    editor.error = '';
    editor.isSaving = true;
  }
  errorMessage.value = '';
  try {
    const updated = await updateGameCatalogMetadata({
      game_id: gameId,
      description: game.description,
      difficulty: game.difficulty,
      learning_section: game.learning_section,
      topics: game.topics,
      catalog_metadata_status: game.catalog_metadata_status,
      is_hidden: isHidden,
    });
    applyUpdatedGame(updated);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось обновить видимость';
    if (editor) {
      editor.error = message;
    } else {
      errorMessage.value = message;
    }
  } finally {
    if (editor) {
      editor.isSaving = false;
    }
  }
}

async function setSectionHidden(sectionName: string, isHidden: boolean): Promise<void> {
  if (!canManage.value) return;
  const targets = games.value.filter(
    (game) => game.mode === 'single_task' && (game.learning_section || 'Другое') === sectionName && game.is_hidden !== isHidden
  );
  if (targets.length === 0) return;
  sectionSavingByName.value = { ...sectionSavingByName.value, [sectionName]: true };
  errorMessage.value = '';
  try {
    for (const game of targets) {
      await setTaskHidden(game.game_id, isHidden);
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось обновить раздел';
  } finally {
    sectionSavingByName.value = { ...sectionSavingByName.value, [sectionName]: false };
  }
}

function applyUpdatedGame(updated: GameDto): void {
  const index = games.value.findIndex((game) => game.game_id === updated.game_id);
  if (index >= 0) {
    games.value[index] = updated;
  }
  const editor = editorByGameId.value[updated.game_id];
  if (!editor) return;
  editor.description = updated.description ?? '';
  editor.difficulty = ((updated.difficulty ?? '') as CatalogEditorState['difficulty']);
  editor.learningSection = updated.learning_section ?? '';
  editor.topicsCsv = updated.topics.join(', ');
  editor.status = updated.catalog_metadata_status;
  editor.isHidden = updated.is_hidden;
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
.admin-catalog-page { display: grid; align-content: start; gap: 16px; min-width: 0; }
.admin-catalog-page--focused { max-width: 1040px; margin-inline: auto; }
.admin-catalog-header { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 16px; padding-bottom: 8px; }
.admin-catalog-heading { min-width: 0; }
.admin-catalog-heading h1 { margin: 0; overflow-wrap: anywhere; }
.admin-catalog-heading p { margin: 0 0 4px; color: var(--agp-text-muted); font-size: 12px; line-height: 16px; }
.admin-catalog-header .btn, .admin-catalog-row-actions .btn { white-space: nowrap; }
.admin-catalog-filters { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(150px, 200px) minmax(150px, 200px) auto; gap: 16px; align-items: end; padding: 16px; }
.admin-catalog-filters label, .admin-catalog-editor-grid label { display: grid; align-content: start; gap: 8px; min-width: 0; font-size: 13px; font-weight: 500; }
.admin-catalog-count { color: var(--agp-text-muted); padding-block: 8px; white-space: nowrap; }
.admin-catalog-list { display: grid; gap: 12px; }
.admin-catalog-item-head { display: flex; align-items: center; flex-wrap: wrap; gap: 12px 16px; padding: 16px; }
.admin-catalog-item-title { flex: 1 1 240px; min-width: 0; }
.admin-catalog-item-title h2 { margin: 0 0 4px; }
.admin-catalog-item-title > span { font-size: 12px; }
.admin-catalog-badges, .admin-catalog-row-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.admin-catalog-status { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border-radius: 6px; background: var(--agp-surface-soft); color: var(--agp-text-muted); font-size: 12px; white-space: nowrap; }
.admin-catalog-status--ready { color: var(--agp-success); background: var(--arena-success-soft); }
.admin-catalog-status--visible { color: var(--agp-primary); background: var(--agp-primary-soft); }
.admin-catalog-editor { display: grid; gap: 20px; padding: 24px; }
.admin-catalog-editor--nested { border-top: 1px solid var(--agp-border); }
.admin-catalog-editor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.admin-catalog-description { grid-column: 1 / -1; }
.admin-catalog-description textarea { resize: vertical; min-height: 128px; line-height: 22px; }
.admin-catalog-visibility-toggle { display: flex; align-items: center; gap: 8px; min-height: 24px; }
.admin-catalog-visibility-toggle .form-check-input { margin: 0; flex-shrink: 0; }
.admin-catalog-editor-footer { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding-top: 16px; border-top: 1px solid var(--agp-border); }
.admin-catalog-editor-footer .btn { min-width: 128px; }
.admin-catalog-save-status { color: var(--agp-text-muted); font-size: 12px; }
.admin-catalog-page p { margin-bottom: 0; }
.admin-catalog-sections { padding: 16px; }
.admin-catalog-sections summary { cursor: pointer; font-weight: 500; }
.admin-section-list { display: grid; gap: 12px; padding-top: 16px; }
.admin-section-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding-top: 12px; border-top: 1px solid var(--agp-border); }
.admin-section-row > div:first-child { display: grid; gap: 4px; }
.admin-section-row .text-muted { font-size: 12px; }
@media (max-width: 767px) {
  .admin-catalog-header { gap: 12px; }
  .admin-catalog-heading { grid-row: 2; grid-column: 1 / -1; }
  .admin-catalog-header > :last-child { grid-column: 3; }
  .admin-catalog-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .admin-catalog-search { grid-column: 1 / -1; }
  .admin-catalog-count { grid-column: 1 / -1; padding-block: 0; }
  .admin-catalog-editor { gap: 16px; padding: 16px; }
  .admin-catalog-editor-grid { gap: 16px; grid-template-columns: 1fr; }
  .admin-catalog-item-title { flex-basis: 100%; }
  .admin-catalog-item-head { gap: 12px; }
  .admin-catalog-row-actions { margin-left: auto; }
}
</style>
