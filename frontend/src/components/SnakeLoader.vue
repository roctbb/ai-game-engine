<template>
  <span class="arena-loading" role="status"
    ><span class="arena-snake" aria-hidden="true"
      ><i v-for="n in 7" :key="n" :style="{ '--i': n - 1 }"></i></span
    ><span v-if="label">{{ label }}</span
    ><span v-else class="visually-hidden">Загрузка</span></span
  >
</template>
<script setup lang="ts">
defineProps<{ label?: string }>();
</script>
<style>
.arena-loading {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--agp-text-muted);
  font-size: 12px;
}
.arena-snake {
  position: relative;
  display: inline-block;
  width: 20px;
  height: 20px;
  flex: none;
  color: var(--agp-primary);
}
.arena-snake i {
  position: absolute;
  width: 4px;
  height: 4px;
  background: currentColor;
  animation: arena-snake 1.2s ease-in-out infinite;
  animation-delay: calc(var(--i) * 0.14s);
}
.arena-snake i:nth-child(2) {
  left: 5px;
}
.arena-snake i:nth-child(3) {
  left: 5px;
  top: 5px;
}
.arena-snake i:nth-child(4) {
  left: 5px;
  top: 10px;
}
.arena-snake i:nth-child(5) {
  left: 10px;
  top: 10px;
}
.arena-snake i:nth-child(6) {
  left: 10px;
  top: 15px;
}
.arena-snake i:nth-child(7) {
  left: 15px;
  top: 15px;
  background: var(--arena-yellow);
}
@keyframes arena-snake {
  0%,
  100% {
    opacity: 0.25;
  }
  45% {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .arena-snake i {
    animation: none;
    opacity: 1;
  }
}
</style>
