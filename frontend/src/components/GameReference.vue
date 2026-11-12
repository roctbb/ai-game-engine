<template>
  <section class="agp-game-reference" aria-label="Условие и API игры">
    <header><strong>Условие и справка</strong><button type="button" class="agp-panel-toggle" @click="$emit('close')">Вернуться к полю</button></header>
    <div class="agp-insight-tabs" role="tablist" aria-label="Справка по игре"><button v-for="tab in tabs" :key="tab.id" type="button" role="tab" :aria-selected="active === tab.id" :class="{ active: active === tab.id }" @click="active = tab.id">{{ tab.label }}</button></div>
    <div class="agp-reference-content">
      <template v-if="active === 'task'"><h2>{{ title }}</h2><p>{{ description }}</p><MarkdownContent v-if="instruction" class="agp-reference-callout" :source="instruction" /><pre v-if="signature">{{ signature }}</pre></template>
      <template v-else-if="active === 'api'"><pre v-if="signature">{{ signature }}</pre><MarkdownContent v-for="link in docs?.links.filter(l => l.content)" :key="link.path" :source="link.content!" /><p v-if="!docs?.links.some(l => l.content)">{{ instruction || 'Дополнительная справка пока не добавлена.' }}</p></template>
      <template v-else><p>Фрагмент входных данных {{ isActual ? 'на выбранном ходу' : 'из примера поля' }}. Большие массивы сокращены.</p><pre>{{ JSON.stringify(boundedPreview(argumentsPreview), null, 2) }}</pre></template>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue';
import MarkdownContent from './MarkdownContent.vue';
import { boundedPreview, record, type ReplayRecord } from '../lib/replayInsights';
import type { GameDocumentationDto } from '../lib/api';
const props = defineProps<{ title: string; description?: string | null; instruction?: string | null; template: string; docs: GameDocumentationDto | null; frame: ReplayRecord; arguments?: unknown; isActual: boolean }>();
defineEmits<{ (e: 'close'): void }>();
const active = ref('task');
const tabs = [{ id: 'task', label: 'Задание' }, { id: 'api', label: 'API' }, { id: 'input', label: 'Входные данные' }];
const signature = computed(() => props.template.match(/^def\s+[^\n]+/m)?.[0] ?? '');
const argumentsPreview = computed(() => {
  if (props.arguments) return props.arguments;
  const names = signature.value.match(/\((.*?)\)/)?.[1].split(',').map(n => n.trim().split('=')[0]) ?? [];
  const position = record(props.frame.position);
  const aliases: Record<string, unknown> = { x: position.x, y: position.y, maze: props.frame.board, state: props.frame, flags_left: props.frame.flags_left };
  return names.length ? Object.fromEntries(names.map(name => [name, aliases[name] ?? props.frame[name] ?? 'см. описание API'])) : props.frame;
});
</script>
