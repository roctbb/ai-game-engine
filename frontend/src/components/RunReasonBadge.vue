<template>
  <template v-if="reason">
    <span class="agp-pill" :class="runReasonToneClass(reason)">
      {{ runReasonLabel(reason) }}
    </span>
    <div v-if="showRaw" class="small text-muted mono mt-1">{{ reason }}</div>
  </template>
  <span v-else class="small text-muted">—</span>
</template>

<script setup lang="ts">
import { runReasonLabel, runReasonToneClass } from '../lib/runReason';

withDefaults(
  defineProps<{
    reason: string | null;
    showRaw?: boolean;
  }>(),
  {
    showRaw: true,
  },
);
</script>
