<template>
  <section class="agp-grid">
    <header class="d-flex flex-column flex-lg-row justify-content-between align-items-lg-end gap-3">
      <div>
        <h1 class="h3 mb-1">Каталог повторов</h1>
        <p class="text-muted mb-0">
          Повторы завершенных запусков для преподавателя и администратора.
        </p>
      </div>
      <button v-if="canManage" class="btn btn-outline-dark" :disabled="isLoading" @click="loadReplays">
        {{ isLoading ? 'Обновление...' : 'Обновить' }}
      </button>
    </header>

    <article v-if="!canManage" class="agp-card p-4 text-muted">
      Каталог повторов доступен только преподавателю или администратору.
    </article>

    <article v-if="canManage" class="agp-card p-3">
      <div class="row g-2">
        <div class="col-md-3">
          <label class="form-label small">Игра</label>
          <select v-model="gameIdFilter" class="form-select">
            <option value="">Все игры</option>
            <option v-for="game in games" :key="game.game_id" :value="game.game_id">
              {{ game.title }}
            </option>
          </select>
        </div>
        <div class="col-md-3">
          <label class="form-label small">Тип запуска</label>
          <select v-model="runKindFilter" class="form-select">
            <option value="">Любой</option>
            <option value="single_task">Задача</option>
            <option value="training_match">Лобби</option>
            <option value="competition_match">Соревнование</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small">Лимит</label>
          <input v-model.number="limitFilter" min="1" max="200" class="form-control mono" type="number" />
        </div>
        <div class="col-md-4">
          <label class="form-label small">Поиск по ID запуска</label>
          <input v-model.trim="runIdQuery" class="form-control mono" placeholder="run_..." />
        </div>
      </div>
    </article>

    <article v-if="canManage && errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <article v-if="canManage" class="agp-card p-3">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h2 class="h6 mb-0">Результаты</h2>
        <div class="small text-muted">
          Показано: <span class="mono">{{ filteredReplays.length }}</span>
        </div>
      </div>
      <div v-if="isLoading" class="text-muted small">Загрузка...</div>
      <table v-else class="table align-middle mb-0">
        <thead>
          <tr>
            <th>ID запуска</th>
            <th>Игра</th>
            <th>Тип и статус</th>
            <th>Кадры/события</th>
            <th>Обновлен</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in filteredReplays" :key="item.replay_id">
            <td>
              <div class="mono small">{{ item.run_id }}</div>
              <div class="small text-muted mono">{{ item.replay_id }}</div>
            </td>
            <td>
              <div>{{ gameTitle(item.game_id) }}</div>
              <div class="small text-muted mono">{{ item.game_id }}</div>
            </td>
            <td>
              <div>{{ runKindLabel(item.run_kind) }}</div>
              <div class="small text-muted">{{ statusLabel(item.status) }}</div>
            </td>
            <td class="mono small">{{ item.frames.length }} / {{ item.events.length }}</td>
            <td class="mono small">{{ formatIso(item.updated_at) }}</td>
            <td class="text-end">
              <RouterLink :to="`/runs/${item.run_id}/watch`" class="btn btn-sm btn-outline-secondary">Открыть</RouterLink>
            </td>
          </tr>
          <tr v-if="filteredReplays.length === 0">
            <td colspan="6" class="text-muted small">Повторы по текущим фильтрам не найдены.</td>
          </tr>
        </tbody>
      </table>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import { listGames, listReplays, type GameDto, type ReplayDto } from '../lib/api';
import { useSessionStore } from '../stores/session';

const route = useRoute();
const sessionStore = useSessionStore();

const games = ref<GameDto[]>([]);
const replays = ref<ReplayDto[]>([]);
const isLoading = ref(false);
const errorMessage = ref('');

const gameIdFilter = ref('');
const runKindFilter = ref<'single_task' | 'training_match' | 'competition_match' | ''>('');
const limitFilter = ref(50);
const runIdQuery = ref('');
const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');

const filteredReplays = computed(() => {
  const query = runIdQuery.value.toLowerCase();
  if (!query) return replays.value;
  return replays.value.filter((item) => item.run_id.toLowerCase().includes(query));
});

function applyFiltersFromQuery(): void {
  const gameQuery = route.query.game_id;
  if (typeof gameQuery === 'string' && gameQuery.trim()) {
    gameIdFilter.value = gameQuery.trim();
  }

  const runKindQuery = route.query.run_kind;
  if (
    runKindQuery === 'single_task' ||
    runKindQuery === 'training_match' ||
    runKindQuery === 'competition_match'
  ) {
    runKindFilter.value = runKindQuery;
  }

  const limitQuery = route.query.limit;
  if (typeof limitQuery === 'string') {
    const parsed = Number(limitQuery);
    if (Number.isFinite(parsed)) {
      limitFilter.value = Math.max(1, Math.min(200, parsed));
    }
  }

  const runIdQueryRaw = route.query.run_id;
  if (typeof runIdQueryRaw === 'string' && runIdQueryRaw.trim()) {
    runIdQuery.value = runIdQueryRaw.trim();
  }
}

function gameTitle(gameId: string): string {
  const item = games.value.find((game) => game.game_id === gameId);
  return item?.title ?? gameId;
}

function runKindLabel(kind: ReplayDto['run_kind']): string {
  const labels: Record<ReplayDto['run_kind'], string> = {
    single_task: 'Задача',
    training_match: 'Лобби',
    competition_match: 'Соревнование',
  };
  return labels[kind] ?? kind;
}

function statusLabel(status: ReplayDto['status']): string {
  const labels: Record<ReplayDto['status'], string> = {
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

function formatIso(value: string): string {
  const time = Date.parse(value);
  if (Number.isNaN(time)) return value;
  return new Date(time).toLocaleString('ru-RU');
}

async function loadReplays(): Promise<void> {
  if (!canManage.value) return;
  isLoading.value = true;
  errorMessage.value = '';
  try {
    replays.value = await listReplays({
      game_id: gameIdFilter.value || undefined,
      run_kind: runKindFilter.value || undefined,
      limit: Math.max(1, Math.min(200, Number(limitFilter.value) || 50)),
    });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить каталог повторов';
  } finally {
    isLoading.value = false;
  }
}

watch([gameIdFilter, runKindFilter, limitFilter], () => {
  void loadReplays();
});

onMounted(async () => {
  if (!canManage.value) return;
  applyFiltersFromQuery();
  try {
    games.value = await listGames();
  } catch {
    // Каталог игр не блокирует отображение таблицы повторов.
  }
  await loadReplays();
});
</script>
