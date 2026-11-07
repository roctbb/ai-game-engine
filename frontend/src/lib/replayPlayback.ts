export const REPLAY_SPEEDS = [
  { delay: 2000, label: '0,5×' },
  { delay: 1000, label: '1×' },
  { delay: 500, label: '2×' },
  { delay: 250, label: '4×' },
];

const SPEED_KEY = 'agp_replay_speed_ms';

export function loadReplayDelay(): number {
  try {
    const value = Number(localStorage.getItem(SPEED_KEY));
    if (REPLAY_SPEEDS.some((speed) => speed.delay === value)) return value;
    // Migrate the old task player's speed presets.
    return ({ 1800: 2000, 1200: 1000, 700: 1000, 350: 500 } as Record<number, number>)[value] ?? 1000;
  } catch {
    return 1000;
  }
}

export function saveReplayDelay(delay: number): void {
  try {
    localStorage.setItem(SPEED_KEY, String(delay));
  } catch {
    // Playback also works when persistent storage is unavailable.
  }
}

/** One logical step at a time; never rush through missed turns after a hidden tab. */
export function createReplayClock(step: () => void, delay: () => number) {
  let handle: number | null = null;
  let previous: number | null = null;

  function tick(timestamp: number): void {
    handle = requestAnimationFrame(tick);
    if (document.hidden) {
      previous = null;
      return;
    }
    const interval = Math.max(16, delay());
    if (previous === null || timestamp - previous > interval * 2) previous = timestamp;
    if (timestamp - previous < interval) return;
    previous += interval;
    step();
  }

  function stop(): void {
    if (handle !== null) cancelAnimationFrame(handle);
    handle = null;
    previous = null;
  }

  function start(): void {
    stop();
    handle = requestAnimationFrame(tick);
  }

  return { start, stop };
}
