<template>
  <div class="agp-card p-3 d-flex flex-column flex-lg-row justify-content-between gap-3 align-items-start align-items-lg-center">
    <div>
      <div class="fw-semibold">Статус лобби: <span class="text-uppercase">{{ status }}</span></div>
      <div class="text-muted small">{{ message }}</div>
    </div>
    <span :class="['agp-pill', toneClass]">{{ toneText }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  status: 'draft' | 'open' | 'running' | 'paused' | 'updating' | 'closed';
}>();

const message = computed(() => {
  if (props.status === 'updating') return 'Лобби временно заблокировано: идет обновление версии игры.';
  if (props.status === 'paused') return 'Матчи приостановлены. Действия ready/join могут быть недоступны.';
  if (props.status === 'closed') return 'Лобби закрыто. Новые подключения отключены.';
  if (props.status === 'running') return 'Матчи запущены. Доступность действий зависит от режима.';
  if (props.status === 'draft') return 'Лобби в черновике. Админ может завершать настройку.';
  return 'Лобби открыто для действий по правилам текущего режима.';
});

const toneClass = computed(() => {
  if (props.status === 'updating' || props.status === 'paused') return 'agp-pill--warning';
  if (props.status === 'closed') return 'agp-pill--danger';
  return 'agp-pill--primary';
});

const toneText = computed(() => {
  if (props.status === 'updating') return 'Действия ограничены';
  if (props.status === 'closed') return 'Закрыто';
  if (props.status === 'paused') return 'На паузе';
  return 'Активно';
});
</script>
