<template>
  <span :class="['agp-pill', toneClass]">{{ slotState }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  slotState: 'filled' | 'empty' | 'dirty' | 'locked' | 'incompatible';
}>();

const toneClass = computed(() => {
  if (props.slotState === 'empty') return 'agp-pill--warning';
  if (props.slotState === 'incompatible') return 'agp-pill--danger';
  return 'agp-pill--primary';
});
</script>
