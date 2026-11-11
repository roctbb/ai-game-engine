<template>
  <div class="agp-replay-player" role="group" aria-label="Управление повтором">
    <span v-if="live" class="small text-muted">{{ liveLabel }}</span>
    <div v-else class="agp-replay-transport">
      <button type="button" class="agp-icon-button agp-icon-button--replay" :disabled="!canPlay" :title="playing ? 'Пауза (Space)' : 'Воспроизвести повтор (Space)'" :aria-label="playing ? 'Пауза повтора' : 'Воспроизвести повтор'" @click="$emit('toggle')">
        <AppIcon :name="playing ? 'pause' : 'play'" />
      </button>
      <button type="button" class="agp-icon-button agp-icon-button--ghost" :disabled="!canStepBackward" title="Предыдущий кадр (←)" aria-label="Предыдущий кадр" @click="$emit('step', -1)"><AppIcon name="previous" /></button>
      <button type="button" class="agp-icon-button agp-icon-button--ghost" :disabled="!canStepForward" title="Следующий кадр (→)" aria-label="Следующий кадр" @click="$emit('step', 1)"><AppIcon name="next" /></button>
    </div>
    <span class="agp-replay-position mono">{{ frameCount ? `${frameIndex + 1} / ${frameCount}` : 'Нет повтора' }}</span>
    <div class="agp-replay-track">
      <input class="form-range agp-player-range" type="range" min="0" :max="Math.max(0, frameCount - 1)" :value="frameIndex" :disabled="seekDisabled || frameCount < 2" aria-label="Кадр повтора" :aria-valuetext="frameCount ? `Кадр ${frameIndex + 1} из ${frameCount}` : 'Повтор недоступен'" @input="$emit('update:frameIndex', Number(($event.target as HTMLInputElement).value))" />
      <div v-if="markers.length && frameCount > 1" class="agp-replay-markers" aria-label="События на шкале"><button v-for="marker in visibleMarkers" :key="marker.id" type="button" :disabled="seekDisabled" :class="`agp-replay-marker agp-replay-marker--${marker.tone}`" :style="{ left: `${marker.frame * 100 / (frameCount - 1)}%` }" :title="`Ход ${marker.tick}: ${marker.label}`" :aria-label="`Ход ${marker.tick}: ${marker.label}`" @click="$emit('update:frameIndex', marker.frame)"></button></div>
    </div>
    <label v-if="!live" class="agp-speed-control">
      <span class="visually-hidden">Скорость повтора</span>
      <select class="form-select agp-speed-select" :value="delay" @change="$emit('update:delay', Number(($event.target as HTMLSelectElement).value))">
        <option v-if="!REPLAY_SPEEDS.some(speed => speed.delay === delay)" :value="delay">{{ (1000 / delay).toLocaleString('ru', { maximumFractionDigits: 2 }) }}×</option>
        <option v-for="speed in REPLAY_SPEEDS" :key="speed.delay" :value="speed.delay">{{ speed.label }}</option>
      </select>
    </label>
    <div v-if="$slots.default" class="agp-player-side-buttons"><slot /></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import AppIcon from './AppIcon.vue';
import { REPLAY_SPEEDS } from '../lib/replayPlayback';
import { thinReplayMoments, type ReplayMoment } from '../lib/replayInsights';

const props = withDefaults(defineProps<{
  frameIndex: number;
  frameCount: number;
  playing: boolean;
  delay: number;
  canPlay: boolean;
  canStepBackward: boolean;
  canStepForward: boolean;
  seekDisabled?: boolean;
  live?: boolean;
  liveLabel?: string;
  markers?: ReplayMoment[];
}>(), { seekDisabled: false, live: false, liveLabel: 'Первый показ', markers: () => [] });

const visibleMarkers = computed(() => thinReplayMoments(props.markers));

defineEmits<{
  (event: 'update:frameIndex', value: number): void;
  (event: 'update:delay', value: number): void;
  (event: 'toggle'): void;
  (event: 'step', direction: -1 | 1): void;
}>();
</script>
