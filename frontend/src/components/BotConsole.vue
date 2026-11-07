<template>
  <section class="agp-bot-console" :class="{ 'agp-bot-console--expanded': expanded }" :aria-label="label">
    <div v-if="!collapsed && !expanded" class="agp-console-resize" role="separator" tabindex="0" aria-label="Высота консоли" aria-orientation="horizontal" :aria-valuenow="height" :aria-valuemin="64" :aria-valuemax="maxHeight" title="Перетащите, чтобы изменить высоту консоли" @pointerdown="startResize" @pointermove="resize" @pointerup="stopResize" @lostpointercapture="stopResize" @keydown.up.prevent="setHeight(height + 16)" @keydown.down.prevent="setHeight(height - 16)"></div>
    <div class="agp-bot-console-head">
      <button type="button" class="agp-console-toggle" :aria-label="expanded ? label : `${collapsed ? 'Развернуть' : 'Свернуть'}: ${label}`" :aria-expanded="!collapsed || expanded" :disabled="expanded" @click="collapsed = !collapsed">
        <AppIcon name="console" /><strong>{{ label }}</strong><span v-if="!expanded" aria-hidden="true">{{ collapsed ? '+' : '−' }}</span>
      </button>
      <span v-if="position" class="mono">{{ position }}</span>
    </div>
    <div v-show="!collapsed || expanded" class="agp-bot-console-body" :style="expanded ? undefined : { height: `${height}px`, maxHeight: '40dvh' }"><slot /></div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import AppIcon from './AppIcon.vue';

withDefaults(defineProps<{ label?: string; position?: string; expanded?: boolean }>(), { label: 'Вывод запуска', position: '', expanded: false });
const STORAGE_KEY = 'agp_console_layout';
function readLayout(): { height: number; collapsed: boolean } {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}');
    return { height: Math.min(320, Math.max(64, Number(stored.height) || 112)), collapsed: stored.collapsed === true };
  } catch { return { height: 112, collapsed: false }; }
}
const initial = readLayout();
const height = ref(initial.height);
const collapsed = ref(initial.collapsed);
const maxHeight = computed(() => Math.min(320, Math.floor(window.innerHeight * .4)));
let drag: { y: number; height: number } | null = null;
function setHeight(value: number) { height.value = Math.min(maxHeight.value, Math.max(64, value)); }
function startResize(event: PointerEvent) {
  event.preventDefault();
  drag = { y: event.clientY, height: height.value };
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}
function resize(event: PointerEvent) { if (drag) setHeight(drag.height + drag.y - event.clientY); }
function stopResize() { drag = null; }
watch([height, collapsed], () => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ height: height.value, collapsed: collapsed.value })); } catch { /* The current layout remains usable without storage. */ }
});
</script>
