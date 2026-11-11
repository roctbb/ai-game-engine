<script lang="ts">
import type { RouteLocationRaw } from 'vue-router';
export interface ActionMenuItem {
  id: string;
  label: string;
  to?: RouteLocationRaw;
  disabled?: boolean;
  danger?: boolean;
}
</script>

<template>
  <button ref="trigger" class="btn btn-outline-secondary arena-menu-trigger" :class="{ 'arena-menu-trigger--compact': compact }" type="button" :aria-label="label" aria-haspopup="menu" :aria-expanded="open" @click="toggle" @keydown.down.prevent="show(true)" @keydown.up.prevent="show(true, true)">⋯</button>
  <Teleport to="body">
    <div v-if="open" ref="menu" class="arena-action-menu" role="menu" :aria-label="label" tabindex="-1" @keydown="navigate">
      <template v-for="item in items" :key="item.id">
        <RouterLink v-if="item.to && !item.disabled" :to="item.to" role="menuitem" @click="close(false)">{{ item.label }}</RouterLink>
        <button v-else type="button" role="menuitem" :disabled="item.disabled" :class="{ 'arena-menu-danger': item.danger }" @click="select(item)">{{ item.label }}</button>
      </template>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from 'vue';
import { RouterLink } from 'vue-router';

withDefaults(defineProps<{ items: ActionMenuItem[]; label?: string; compact?: boolean }>(), { label: 'Действия', compact: false });
const emit = defineEmits<{ select: [id: string] }>();
const trigger = ref<HTMLButtonElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const open = ref(false);

function place(): void {
  if (!trigger.value || !menu.value) return;
  const anchor = trigger.value.getBoundingClientRect();
  const bounds = menu.value.getBoundingClientRect();
  const left = Math.max(8, Math.min(anchor.right - bounds.width, window.innerWidth - bounds.width - 8));
  const top = anchor.bottom + bounds.height + 6 <= window.innerHeight - 8 ? anchor.bottom + 6 : Math.max(8, anchor.top - bounds.height - 6);
  Object.assign(menu.value.style, { left: `${left}px`, top: `${top}px` });
}

function entries(): HTMLElement[] {
  return Array.from(menu.value?.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)') ?? []);
}

async function show(focus = false, last = false): Promise<void> {
  if (open.value) return;
  open.value = true;
  document.addEventListener('pointerdown', outside);
  document.addEventListener('keydown', escape);
  window.addEventListener('resize', place);
  window.addEventListener('scroll', place, true);
  await nextTick();
  place();
  if (open.value && focus) ((last ? entries().at(-1) : entries()[0]) ?? menu.value)?.focus({ preventScroll: true });
}

function close(restore = true): void {
  if (!open.value) return;
  open.value = false;
  document.removeEventListener('pointerdown', outside);
  document.removeEventListener('keydown', escape);
  window.removeEventListener('resize', place);
  window.removeEventListener('scroll', place, true);
  if (restore) trigger.value?.focus({ preventScroll: true });
}

function toggle(event: MouseEvent): void { if (open.value) close(); else void show(event.detail === 0); }
function outside(event: PointerEvent): void {
  if (event.target instanceof Node && !trigger.value?.contains(event.target) && !menu.value?.contains(event.target)) close(false);
}
function escape(event: KeyboardEvent): void { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); } }
function navigate(event: KeyboardEvent): void {
  if (event.key === 'Tab') { close(false); return; }
  if (!['ArrowDown','ArrowUp','Home','End'].includes(event.key)) return;
  event.preventDefault();
  const items = entries();
  const current = items.indexOf(document.activeElement as HTMLElement);
  const index = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
  items[index]?.focus();
}
function select(item: ActionMenuItem): void { close(); emit('select', item.id); }
onBeforeUnmount(() => close(false));
</script>

<style scoped>
.arena-menu-trigger { flex: none; padding: 0; width: 36px; min-width: 36px; height: 36px; font-size: 22px; line-height: 20px; }
.arena-menu-trigger--compact { width: 32px; min-width: 32px; height: 32px; min-height: 32px; }
.arena-action-menu { position: fixed; z-index: 500; display: grid; gap: 4px; width: min(240px, calc(100vw - 16px)); max-height: calc(100dvh - 16px); overflow-y: auto; padding: 4px; background: var(--agp-surface); color: var(--agp-text); border: 1px solid var(--agp-border); border-radius: 8px; box-shadow: 0 8px 24px #10182718; }
.arena-action-menu > :is(button,a) { display: flex; align-items: center; min-height: 36px; padding: 8px 12px; border: 0; border-radius: 4px; background: transparent; color: var(--agp-text); font: inherit; font-size: 13px; line-height: 20px; text-align: left; text-decoration: none; }
.arena-action-menu > :is(button,a):is(:hover,:focus-visible) { color: var(--agp-primary); background: var(--agp-primary-soft); outline-offset: -2px; }
.arena-action-menu > button:disabled { color: var(--agp-text-muted); opacity: .65; }
.arena-action-menu > .arena-menu-danger { color: var(--agp-danger); }
.arena-action-menu > .arena-menu-danger:is(:hover,:focus-visible) { color: var(--agp-danger); background: var(--arena-error-soft); }
@media (max-width: 767px) { .arena-menu-trigger { width: 44px; height: 44px; min-width: 44px; } .arena-action-menu > :is(button,a) { min-height: 44px; } }
</style>
