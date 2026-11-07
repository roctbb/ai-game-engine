<template>
  <div class="agp-skeleton-region" :class="`agp-skeleton-region--${layout}`" role="status" aria-live="polite" :aria-label="label" aria-busy="true">
    <span class="visually-hidden">{{ label }}</span>
    <div v-for="index in count" :key="index" class="agp-skeleton-card" aria-hidden="true">
      <span class="agp-skeleton agp-skeleton--eyebrow"></span>
      <span class="agp-skeleton agp-skeleton--title"></span>
      <span class="agp-skeleton"></span>
      <span class="agp-skeleton agp-skeleton--short"></span>
      <span class="agp-skeleton agp-skeleton--action"></span>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ count?: number; layout?: 'cards' | 'list' | 'workspace'; label?: string }>(), {
  count: 6,
  layout: 'cards',
  label: 'Загрузка…',
});
</script>
