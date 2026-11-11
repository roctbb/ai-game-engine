<template>
  <table v-if="players.length" class="table mb-0 arena-live-scoreboard">
    <thead><tr><th v-if="players.some(p => p.place !== undefined)">#</th><th>Участник</th><th class="text-end">Очки</th></tr></thead>
    <tbody><tr v-for="player in players" :key="player.team_id" :class="{ 'arena-live-scoreboard-self': player.isSelf }"><td v-if="players.some(p => p.place !== undefined)" class="text-muted">{{ player.place }}</td><td><strong>{{ player.display_name }}</strong><span>{{ player.status }}<template v-if="player.meta"> · {{ player.meta }}</template></span></td><td class="text-end font-monospace">{{ player.score }}</td></tr></tbody>
  </table>
  <p v-else class="small text-muted mb-0">Результаты появятся с первым ходом.</p>
</template>
<script setup lang="ts">
defineProps<{ players: Array<{ team_id: string; display_name: string; status: string; score: string; isSelf: boolean; meta?: string; place?: string }> }>();
</script>
<style scoped>
.arena-live-scoreboard td:first-child { min-width: 0; overflow-wrap: anywhere; }
.arena-live-scoreboard strong { font-weight: 500; font-size: 13px; }
.arena-live-scoreboard td span { display: block; font-size: 11px; line-height: 16px; color: var(--agp-text-muted); }
.arena-live-scoreboard-self > td { background: var(--agp-primary-soft); }
</style>
