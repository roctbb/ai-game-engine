<template>
  <svg class="agp-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path v-for="(path, index) in paths[name] ?? paths.code" :key="index" :d="path" />
  </svg>
</template>

<script setup lang="ts">
defineProps<{ name: string }>();

const paths: Record<string, string[]> = {
  play: ['m8 5 11 7-11 7Z'],
  pause: ['M8 5v14M16 5v14'],
  stop: ['M6 6h12v12H6Z'],
  previous: ['m14 6-6 6 6 6'],
  next: ['m10 6 6 6-6 6'],
  back: ['M19 12H5m6-6-6 6 6 6'],
  close: ['m6 6 12 12M6 18 18 6'],
  code: ['m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16'],
  split: ['M3 5h18v14H3ZM12 5v14'],
  viewer: ['M3 4h18v14H3Zm5 18h8m-4-4v4'],
  console: ['m5 7 5 5-5 5m8 0h6'],
  expand: ['M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5'],
  restore: ['M3 8h5V3m8 0v5h5M8 21v-5H3m18 0h-5v5'],
  refresh: ['M20 7a9 9 0 1 0 1 8M20 3v5h-5'],
  tasks: ['M8 4h12v16H4V4h4m0-2h8v4H8Zm0 9h8m-8 4h5'],
  games: ['M7 8h10a5 5 0 0 1 5 5v3a3 3 0 0 1-5 2l-2-2H9l-2 2a3 3 0 0 1-5-2v-3a5 5 0 0 1 5-5Zm0 3v4m-2-2h4m7-1h.01m3 2h.01'],
  trophy: ['M7 3h10v6a5 5 0 0 1-10 0Zm0 2H3v2a5 5 0 0 0 5 5m9-7h4v2a5 5 0 0 1-5 5m-4 2v5m-4 2h8'],
  settings: ['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2'],
  check: ['m5 12 4 4L19 6'],
  history: ['M3 11a9 9 0 1 1 3 8M3 4v7h7m2-5v6l4 2'],
};
</script>
