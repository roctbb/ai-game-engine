import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createReplayClock, loadReplayDelay, saveReplayDelay } from './replayPlayback';

describe('replay clock', () => {
  let frames: Map<number, FrameRequestCallback>;
  let documentState: { hidden: boolean };
  let nextId: number;

  function frame(timestamp: number) {
    const callbacks = [...frames.values()];
    frames.clear();
    callbacks.forEach((callback) => callback(timestamp));
  }

  beforeEach(() => {
    frames = new Map(); nextId = 0; documentState = { hidden: false };
    vi.stubGlobal('document', documentState);
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.set(++nextId, callback); return nextId; });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id));
  });
  afterEach(() => vi.unstubAllGlobals());

  it('advances logical frames at the selected speed and cancels scheduled work', () => {
    const step = vi.fn();
    const clock = createReplayClock(step, () => 1000);
    clock.start();
    frame(0); frame(500); expect(step).not.toHaveBeenCalled();
    frame(1000); frame(2000); expect(step).toHaveBeenCalledTimes(2);
    clock.stop(); frame(3000); expect(step).toHaveBeenCalledTimes(2);
    expect(frames.size).toBe(0);
  });

  it('resumes without rushing through turns after a tab was hidden', () => {
    const step = vi.fn();
    const clock = createReplayClock(step, () => 500);
    clock.start(); frame(0); frame(500);
    documentState.hidden = true; frame(1000); frame(10000);
    documentState.hidden = false; frame(20000);
    expect(step).toHaveBeenCalledTimes(1);
    frame(20500); expect(step).toHaveBeenCalledTimes(2);
    clock.stop();
  });

  it('can stop itself on the last frame without leaving a running animation loop', () => {
    const clock = createReplayClock(() => clock.stop(), () => 250);
    clock.start(); frame(0); frame(250);
    expect(frames.size).toBe(0);
  });
});

describe('shared replay speed', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('migrates old presets and persists the shared selection', () => {
    const setItem = vi.fn();
    vi.stubGlobal('localStorage', { getItem: () => '1200', setItem });
    expect(loadReplayDelay()).toBe(1000);
    saveReplayDelay(500);
    expect(setItem).toHaveBeenCalledWith('agp_replay_speed_ms', '500');
  });
  it('falls back to normal speed when storage is restricted', () => {
    vi.stubGlobal('localStorage', { getItem() { throw new Error('restricted'); }, setItem() { throw new Error('restricted'); } });
    expect(loadReplayDelay()).toBe(1000);
    expect(() => saveReplayDelay(250)).not.toThrow();
  });
});
