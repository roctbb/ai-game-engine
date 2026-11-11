<template>
  <section v-if="competition.broadcast" class="agp-card arena-tournament-broadcast" aria-label="Показ матчей">
    <header>
      <div><strong>Раунд {{ competition.broadcast.round_index }} · Матч {{ competition.broadcast.match_number }} из {{ competition.broadcast.match_count }}</strong><span>{{ playerNames }}</span></div>
      <RouterLink class="btn btn-sm btn-outline-secondary" :to="{ name: 'run-watch', params: { runId: competition.broadcast.run_id }, query: { back: route.fullPath } }">Открыть матч</RouterLink>
    </header>
    <iframe :key="competition.broadcast.run_id" :src="watchUrl" title="Текущий матч соревнования" />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import type { CompetitionDto } from '../lib/api';
import { useSessionStore } from '../stores/session';

const props = defineProps<{ competition: CompetitionDto }>();
const route = useRoute();
const session = useSessionStore();
const playerNames = computed(() => props.competition.rounds.flatMap(round => round.matches)
  .find(match => match.match_id === props.competition.broadcast?.match_id)?.team_ids
  .map(id => props.competition.participant_names?.[id] || id).join(' · ') || '');
const watchUrl = computed(() => {
  const query = new URLSearchParams({ embed: '1', autoplay: '1', session_id: session.sessionId });
  return `/runs/${props.competition.broadcast?.run_id}/watch?${query}`;
});
</script>

<style scoped>
.arena-tournament-broadcast { overflow: hidden; }
.arena-tournament-broadcast header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; border-bottom: 1px solid var(--agp-border); }
.arena-tournament-broadcast header > div { display: grid; gap: 4px; min-width: 0; }
.arena-tournament-broadcast strong { font-size: 14px; line-height: 20px; }
.arena-tournament-broadcast span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--agp-text-muted); font-size: 12px; line-height: 16px; }
.arena-tournament-broadcast a { flex: none; }
.arena-tournament-broadcast iframe { display: block; width: 100%; height: clamp(280px, 48vw, 560px); border: 0; }
@media (max-width: 575px) { .arena-tournament-broadcast header { padding: 12px; flex-wrap: wrap; } }
</style>
