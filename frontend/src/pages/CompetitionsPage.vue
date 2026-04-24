<template>
  <section class="agp-grid">
    <header class="d-flex justify-content-between align-items-start gap-3 flex-wrap">
      <div>
        <h1 class="h3 mb-1">Соревнования</h1>
        <p class="text-muted mb-0">Список соревнований и создание новых турнирных сущностей.</p>
      </div>
      <button class="btn btn-sm btn-outline-secondary" :disabled="isLoading" @click="loadData">
        {{ isLoading ? 'Обновление...' : 'Обновить' }}
      </button>
    </header>

    <article v-if="errorMessage" class="agp-card p-3 text-danger">{{ errorMessage }}</article>

    <article class="agp-card p-3">
      <h2 class="h6 mb-2">Создать соревнование</h2>
      <div v-if="!canManage" class="small text-warning-emphasis">
        Создание соревнований доступно только teacher/admin.
      </div>
      <div class="row g-2 align-items-end">
        <div class="col-md-4">
          <label class="form-label small">Игра</label>
          <select v-model="form.game_id" class="form-select" :disabled="!canManage || isCreating">
            <option value="">Выберите игру</option>
            <option v-for="game in competitionGames" :key="game.game_id" :value="game.game_id">
              {{ game.title }} ({{ game.mode }})
            </option>
          </select>
        </div>
        <div class="col-md-4">
          <label class="form-label small">Название</label>
          <input v-model.trim="form.title" class="form-control" :disabled="!canManage || isCreating" />
        </div>
        <div class="col-md-2">
          <label class="form-label small">format</label>
          <select v-model="form.format" class="form-select mono" :disabled="!canManage || isCreating">
            <option value="single_elimination">single_elimination</option>
            <option value="round_robin">round_robin</option>
            <option value="swiss">swiss</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small">tie_break</label>
          <select v-model="form.tie_break_policy" class="form-select mono" :disabled="!canManage || isCreating">
            <option value="manual">manual</option>
            <option value="shared_advancement">shared_advancement</option>
            <option value="tiebreak_match">tiebreak_match</option>
            <option value="game_defined">game_defined</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small">match_size</label>
          <input
            v-model.number="form.match_size"
            type="number"
            min="2"
            max="64"
            class="form-control mono"
            :disabled="!canManage || isCreating"
          />
        </div>
        <div class="col-md-2">
          <label class="form-label small">top_k</label>
          <input
            v-model.number="form.advancement_top_k"
            type="number"
            min="1"
            max="64"
            class="form-control mono"
            :disabled="!canManage || isCreating"
          />
        </div>
      </div>
      <div class="mt-3">
        <button class="btn btn-dark" :disabled="!canCreate" @click="createNewCompetition">
          {{ isCreating ? 'Создание...' : 'Создать соревнование' }}
        </button>
      </div>
    </article>

    <article class="agp-card p-3">
      <h2 class="h6 mb-2">Существующие соревнования</h2>
      <div v-if="isLoading && competitions.length === 0" class="small text-muted">Загрузка...</div>
      <div v-else-if="competitions.length === 0" class="small text-muted">Соревнования пока не созданы.</div>
      <div v-else class="table-responsive">
        <table class="table align-middle mb-0">
          <thead>
            <tr>
              <th>title</th>
              <th>status</th>
              <th>format</th>
              <th>game_id</th>
              <th>entrants</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="competition in competitions" :key="competition.competition_id">
              <td>{{ competition.title }}</td>
              <td class="mono small">{{ competition.status }}</td>
              <td class="mono small">{{ competition.format }}</td>
              <td class="mono small">{{ competition.game_id }}</td>
              <td class="mono small">{{ competition.entrants.length }}</td>
              <td class="text-end">
                <RouterLink
                  class="btn btn-sm btn-outline-secondary"
                  :to="`/competitions/${competition.competition_id}`"
                >
                  Открыть
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import {
  createCompetition,
  listCompetitions,
  listGames,
  type CompetitionDto,
  type GameDto,
} from '../lib/api';
import { useSessionStore } from '../stores/session';

const router = useRouter();
const sessionStore = useSessionStore();
const canManage = computed(() => sessionStore.role === 'teacher' || sessionStore.role === 'admin');

const isLoading = ref(false);
const isCreating = ref(false);
const errorMessage = ref('');
const games = ref<GameDto[]>([]);
const competitions = ref<CompetitionDto[]>([]);

const form = reactive({
  game_id: '',
  title: 'Новое соревнование',
  format: 'single_elimination' as 'single_elimination' | 'round_robin' | 'swiss',
  tie_break_policy: 'manual' as 'manual' | 'shared_advancement' | 'tiebreak_match' | 'game_defined',
  advancement_top_k: 1,
  match_size: 2,
});

const competitionGames = computed(() => games.value.filter((game) => game.mode !== 'single_task'));
const canCreate = computed(() => {
  if (!canManage.value || isCreating.value) return false;
  if (!form.game_id || !form.title.trim()) return false;
  if (form.match_size < 2 || form.match_size > 64) return false;
  if (form.advancement_top_k < 1 || form.advancement_top_k > form.match_size) return false;
  return true;
});

async function loadData(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const [fetchedGames, fetchedCompetitions] = await Promise.all([listGames(), listCompetitions()]);
    games.value = fetchedGames;
    competitions.value = fetchedCompetitions;
    if (!form.game_id && competitionGames.value[0]) {
      form.game_id = competitionGames.value[0].game_id;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось загрузить данные соревнований';
  } finally {
    isLoading.value = false;
  }
}

async function createNewCompetition(): Promise<void> {
  if (!canCreate.value) return;
  isCreating.value = true;
  errorMessage.value = '';
  try {
    const created = await createCompetition({
      game_id: form.game_id,
      title: form.title.trim(),
      format: form.format,
      tie_break_policy: form.tie_break_policy,
      advancement_top_k: form.advancement_top_k,
      match_size: form.match_size,
    });
    await loadData();
    await router.push(`/competitions/${created.competition_id}`);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Не удалось создать соревнование';
  } finally {
    isCreating.value = false;
  }
}

onMounted(async () => {
  await loadData();
});
</script>

