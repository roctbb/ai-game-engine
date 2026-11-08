<template>
  <section class="agp-replay-insights" aria-label="Разбор хода">
    <div class="agp-insight-tabs" role="tablist" aria-label="Данные повтора">
      <button v-for="tab in tabs" :key="tab.id" type="button" role="tab" :aria-selected="active === tab.id" :class="{ active: active === tab.id }" @click="active = tab.id; $emit('pause')">{{ tab.label }}</button>
      <span class="agp-insight-tick">Ход {{ currentTick }}</span>
    </div>
    <div v-if="active === 'events'" class="agp-insight-body">
      <div class="agp-insight-filter"><label><input v-model="errorsOnly" type="checkbox" /> Только проблемы</label><span>{{ eventCountLabel }}</span></div>
      <p v-if="!filtered.length" class="agp-insight-empty">{{ errorsOnly ? 'Проблем не отмечено.' : 'В этой записи нет событий. Состояние поля доступно во вкладке «Состояние».' }}</p>
      <div class="agp-moment-list">
        <div v-for="moment in visible" :key="moment.id" class="agp-moment" :class="{ 'agp-moment--current': moment.frame === frameIndex, 'agp-moment--error': moment.tone === 'error' }">
          <button type="button" :disabled="locked" @click="$emit('seek', moment.frame)"><span class="mono">{{ moment.tick }}</span><span><strong>{{ moment.label }}</strong><small v-if="moment.role && actorNames[moment.role]">{{ actorNames[moment.role] }}</small><small v-if="moment.detail">{{ moment.detail }}</small></span></button>
          <button v-if="moment.line" class="agp-error-line" type="button" @click="$emit('line', { line: moment.line!, role: moment.role })">Строка {{ moment.line }}</button>
        </div>
      </div>
      <button v-if="visible.length < filtered.length" class="agp-panel-toggle" @click="limit += 50">Показать ещё</button>
    </div>
    <div v-else-if="active === 'state'" class="agp-insight-body">
      <div v-if="metrics.length" class="agp-insight-metrics"><span v-for="metric in metrics" :key="metric.key">{{ metric.label }} <strong>{{ metric.value }}</strong></span></div>
      <p v-if="position" class="agp-insight-empty">Позиция бота: <strong>({{ position.x }}, {{ position.y }})</strong></p>
      <details><summary>Данные текущего кадра</summary><pre>{{ JSON.stringify(boundedPreview(frame), null, 2) }}</pre></details>
    </div>
    <div v-else class="agp-insight-body">
      <p v-if="!snapshot" class="agp-insight-empty">{{ hasDebug ? 'Для этого хода нет снимка переменных.' : 'Для записи аргументов и переменных включите «Записать отладку» перед запуском задачи.' }}</p>
      <template v-else>
        <div class="agp-insight-filter"><strong>{{ snapshot.function }} · ход {{ snapshot.tick }}</strong><button v-if="Number(snapshot.line) > 0" type="button" class="agp-error-line" @click="$emit('line', { line: Number(snapshot.line), role: String(snapshot.role || '') })">Строка {{ snapshot.line }}</button></div>
        <div class="agp-debug-values"><div v-for="[name, value] in Object.entries(record(snapshot.arguments))" :key="name"><strong>{{ name }}</strong><details v-if="value !== null && typeof value === 'object'"><summary>{{ Array.isArray(value) ? 'Массив · фрагмент' : 'Объект · фрагмент' }}</summary><pre>{{ JSON.stringify(value, null, 2) }}</pre></details><code v-else>{{ value === null ? 'None' : JSON.stringify(value) }}</code></div></div>
        <div v-if="snapshot.exception" class="agp-debug-exception">Вызов завершился ошибкой: {{ snapshot.exception }}</div>
        <details v-else open><summary>Вернул бот</summary><pre>{{ snapshot.returned === null ? 'None' : JSON.stringify(snapshot.returned, null, 2) }}</pre></details>
        <details><summary>Переменные перед возвратом</summary><pre>{{ JSON.stringify(snapshot.locals, null, 2) }}</pre></details>
      </template>
      <p v-if="events.some(e => e.type === 'debug_limit')" class="agp-insight-empty">Запись ограничена первыми 500 вызовами и размером 1 МБ. Большие структуры показаны фрагментами.</p>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue';
import { boundedPreview, readableMetrics, record, replayMoments, type ReplayRecord } from '../lib/replayInsights';
const props = withDefaults(defineProps<{ frames: ReplayRecord[]; events: ReplayRecord[]; frameIndex: number; locked?: boolean; actorNames?: Record<string, string> }>(), { locked: false, actorNames: () => ({}) });
defineEmits<{ (e: 'seek', frame: number): void; (e: 'line', location: { line: number; role?: string }): void; (e: 'pause'): void }>();
const active = ref('events');
const errorsOnly = ref(false);
const limit = ref(50);
const tabs = [{ id: 'events', label: 'События' }, { id: 'state', label: 'Состояние' }, { id: 'debug', label: 'Переменные' }];
const currentTick = computed(() => Number(props.frames[props.frameIndex]?.tick ?? props.frameIndex));
const frame = computed(() => record(props.frames[props.frameIndex]?.frame));
const position = computed(() => typeof record(frame.value.position).x === 'number' ? record(frame.value.position) : null);
const metrics = computed(() => readableMetrics(frame.value));
const moments = computed(() => replayMoments(props.events.filter(e => !props.locked || Number(e.tick ?? 0) <= currentTick.value), props.frames));
const filtered = computed(() => moments.value.filter(m => (!props.locked || m.frame <= props.frameIndex) && (!errorsOnly.value || m.tone === 'error')));
const eventCountLabel = computed(() => `${filtered.value.length} ${{ one: 'событие', few: 'события', many: 'событий', other: 'события', zero: 'событий', two: 'события' }[new Intl.PluralRules('ru').select(filtered.value.length)]}`);
const visible = computed(() => filtered.value.slice(0, limit.value));
const hasDebug = computed(() => props.events.some(e => e.type === 'debug_snapshot'));
const snapshot = computed(() => props.events.filter(e => e.type === 'debug_snapshot' && Number(e.tick) <= currentTick.value).sort((a, b) => Number(b.tick) - Number(a.tick))[0] ?? null);
</script>
