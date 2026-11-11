<template>
  <div class="agp-skeleton-region" :class="`agp-skeleton-region--${layout}`" :aria-label="label" aria-busy="true" :style="{ '--agp-skeleton-count': count }">
    <div class="agp-skeleton-status"><SnakeLoader :label="label" /></div>
    <div class="agp-skeleton-grid" aria-hidden="true">
      <div v-for="index in count" :key="index" class="agp-skeleton-card">
        <span class="agp-skeleton agp-skeleton--eyebrow"></span>
        <span class="agp-skeleton agp-skeleton--title"></span>
        <span class="agp-skeleton"></span>
        <span class="agp-skeleton agp-skeleton--short"></span>
        <span class="agp-skeleton agp-skeleton--action"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import SnakeLoader from './SnakeLoader.vue';
withDefaults(defineProps<{ count?: number; layout?: 'cards' | 'list' | 'workspace'; label?: string }>(), {
  count: 6,
  layout: 'cards',
  label: 'Загрузка…',
});
</script>

<style scoped>
.agp-skeleton-region { position: relative; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.agp-skeleton-status { display: flex; align-items: center; min-height: 24px; }
.agp-skeleton-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr)); gap: 16px; min-width: 0; }
.agp-skeleton-card { display: flex; flex-direction: column; gap: 12px; min-width: 0; min-height: 208px; padding: 16px; border: 1px solid var(--agp-border); border-radius: 10px; background: var(--agp-surface); overflow: hidden; }
.agp-skeleton { display: block; flex: none; width: 100%; height: 10px; border-radius: 4px; background: var(--agp-surface-soft); animation: agp-skeleton-breathe 1.8s ease-in-out infinite alternate; }
.agp-skeleton--eyebrow { width: 25%; }
.agp-skeleton--title { width: 70%; height: 18px; margin: 4px 0; }
.agp-skeleton--short { width: 60%; }
.agp-skeleton--action { height: 32px; margin-top: auto; }
.agp-skeleton-region--list .agp-skeleton-grid { grid-template-columns: minmax(0, 1fr); }
.agp-skeleton-region--list .agp-skeleton-card { min-height: 96px; }
.agp-skeleton-region--list .agp-skeleton--action { display: none; }
.agp-skeleton-region--workspace { flex: 1; min-height: 0; }
.agp-skeleton-region--workspace .agp-skeleton-grid { flex: 1; min-height: 0; gap: 8px; grid-template-columns: var(--agp-skeleton-workspace-columns, repeat(var(--agp-skeleton-count), minmax(0, 1fr))); }
.agp-skeleton-region--workspace .agp-skeleton-card { min-height: 0; }
.agp-skeleton-region--workspace .agp-skeleton--action { display: none; }
.agp-skeleton-region--workspace .agp-skeleton-status { position: absolute; inset: 0; z-index: 1; display: grid; place-items: center; }
.agp-skeleton-region--workspace .agp-skeleton-status > * { padding: 12px 16px; border-radius: 8px; background: var(--agp-surface); }
@keyframes agp-skeleton-breathe { to { opacity: .45; } }
@media (max-width: 900px) {
  .agp-skeleton-region--workspace .agp-skeleton-grid { grid-template-columns: minmax(0, 1fr); }
  .agp-skeleton-region--workspace .agp-skeleton-card + .agp-skeleton-card { display: none; }
}
@media (prefers-reduced-motion: reduce) { .agp-skeleton { animation: none; } }
</style>
