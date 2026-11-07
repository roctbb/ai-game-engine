<template>
  <span :class="['agp-pill', toneClass]">{{ stateLabel }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { statusPillClass } from '../lib/statusTone';

const props = defineProps<{
  slotState: 'filled' | 'empty' | 'dirty' | 'locked' | 'incompatible';
}>();

const stateLabel = computed(() => {
  const labels: Record<typeof props.slotState, string> = {
    filled: 'код заполнен',
    empty: 'нужен код',
    dirty: 'есть изменения',
    locked: 'заблокировано',
    incompatible: 'нужно обновить',
  };
  return labels[props.slotState];
});

const toneClass = computed(() => statusPillClass(props.slotState));
</script>
