<template>
  <span :class="['agp-pill', toneClass]">{{ stateLabel }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue';

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

const toneClass = computed(() => {
  if (props.slotState === 'empty') return 'agp-pill--warning';
  if (props.slotState === 'incompatible') return 'agp-pill--danger';
  if (props.slotState === 'locked') return 'agp-pill--neutral';
  return 'agp-pill--primary';
});
</script>
