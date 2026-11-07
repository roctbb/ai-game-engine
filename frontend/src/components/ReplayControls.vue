<template>
  <div class="agp-replay-player" role="group" aria-label="Управление повтором">
    <div class="agp-replay-transport">
      <button type="button" class="agp-icon-button agp-icon-button--replay" :disabled="!canPlay" :title="playing ? 'Пауза (Space)' : 'Воспроизвести повтор (Space)'" :aria-label="playing ? 'Пауза повтора' : 'Воспроизвести повтор'" @click="$emit('toggle')">
        <AppIcon :name="playing ? 'pause' : 'play'" />
      </button>
      <button type="button" class="agp-icon-button agp-icon-button--ghost" :disabled="!canStepBackward" title="Предыдущий кадр (←)" aria-label="Предыдущий кадр" @click="$emit('step', -1)"><AppIcon name="previous" /></button>
      <button type="button" class="agp-icon-button agp-icon-button--ghost" :disabled="!canStepForward" title="Следующий кадр (→)" aria-label="Следующий кадр" @click="$emit('step', 1)"><AppIcon name="next" /></button>
    </div>
    <span class="agp-replay-position mono">{{ frameCount ? `${frameIndex + 1} / ${frameCount}` : 'Нет повтора' }}</span>
    <input class="form-range agp-player-range" type="range" min="0" :max="Math.max(0, frameCount - 1)" :value="frameIndex" :disabled="seekDisabled || frameCount < 2" aria-label="Кадр повтора" :aria-valuetext="frameCount ? `Кадр ${frameIndex + 1} из ${frameCount}` : 'Повтор недоступен'" @input="$emit('update:frameIndex', Number(($event.target as HTMLInputElement).value))" />
    <label class="agp-speed-control">
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
import AppIcon from './AppIcon.vue';
import { REPLAY_SPEEDS } from '../lib/replayPlayback';

withDefaults(defineProps<{
  frameIndex: number;
  frameCount: number;
  playing: boolean;
  delay: number;
  canPlay: boolean;
  canStepBackward: boolean;
  canStepForward: boolean;
  seekDisabled?: boolean;
}>(), { seekDisabled: false });

defineEmits<{
  (event: 'update:frameIndex', value: number): void;
  (event: 'update:delay', value: number): void;
  (event: 'toggle'): void;
  (event: 'step', direction: -1 | 1): void;
}>();
</script>
