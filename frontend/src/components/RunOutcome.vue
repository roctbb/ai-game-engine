<template>
  <section v-if="run" class="agp-outcome" :class="{ 'agp-outcome--expanded': detailsOpen }" role="status" aria-label="Результат запуска">
    <div class="agp-outcome-main"><strong>{{ title }}</strong><button type="button" class="agp-outcome-toggle" :aria-expanded="detailsOpen" @click="detailsOpen = !detailsOpen">{{ detailsOpen ? 'Свернуть' : 'Детали' }}</button><span v-if="revision">Код v{{ revision }}</span><span v-if="bestScore !== null && bestScore !== undefined">Лучший счёт: {{ bestScore }}</span><span v-if="comparison">{{ comparison }}</span><button v-if="problem" class="agp-panel-toggle" @click="$emit('problem', problem.frame)">К проблемному ходу</button><slot /></div>
    <p v-if="reason" class="agp-outcome-detail">{{ reason }}</p>
    <div class="agp-outcome-metrics agp-outcome-detail"><span v-for="metric in metrics" :key="metric.key">{{ metric.label }} <strong>{{ metric.value }}</strong></span></div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue';
import { readableMetrics, record, replayMoments } from '../lib/replayInsights';
import type { ReplayDto, RunDto } from '../lib/api';
import { runOutcomeTitle, runOutcomeReason } from '../lib/runOutcome';
const props = defineProps<{ run: RunDto | null; replay: ReplayDto | null; bestScore?: number | null; revision?: number; previous?: RunDto | null }>();
defineEmits<{ (e: 'problem', frame: number): void }>();
const detailsOpen = ref(false);
const raw = computed(() => record(props.run?.result_payload?.metrics ?? props.replay?.summary?.metrics ?? props.replay?.summary));
const metrics = computed(() => readableMetrics(raw.value).slice(0, 8));
const comparison = computed(() => {
  const before = record(props.previous?.result_payload?.metrics).score;
  const after = raw.value.score;
  if (typeof before !== 'number' || typeof after !== 'number') return '';
  const delta = after - before;
  return `На том же поле: ${delta > 0 ? '+' : ''}${delta} к прошлому счёту`;
});
const problem = computed(() => {
  const moments = replayMoments(props.replay?.events ?? [], props.replay?.frames ?? []);
  return moments.find(m => m.line) ?? moments.find(m => m.tone === 'error');
});
const title = computed(() => runOutcomeTitle(props.run?.status, raw.value));
const reason = computed(() => runOutcomeReason(props.run?.status, raw.value, props.run?.error_message));
</script>
