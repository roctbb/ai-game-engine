import { describe, expect, it, vi } from 'vitest';
import { firstShowPosition, sampleFirstShow } from './firstShowClock';

const start = '2026-11-11T12:00:00Z';
const timeline = { started_at: start, frame_ms: 500 };

describe('shared first-show clock', () => {
  it('joins an ongoing match at the elapsed frame, including network transit', () => {
    const sample = sampleFirstShow(timeline, '2026-11-11T12:00:10Z', 100, 300)!;
    expect(firstShowPosition(sample, 200, 800)).toEqual({ waiting: false, following: true, frame: 21 });
  });
  it('catches up after a hidden tab instead of playing missed frames', () => {
    const sample = sampleFirstShow(timeline, start, 0, 0)!;
    expect(firstShowPosition(sample, 200, 1000).frame).toBe(2);
    expect(firstShowPosition(sample, 200, 25000).frame).toBe(50);
  });
  it('does not mistake slow server processing for time spent on the network', () => {
    const sample = sampleFirstShow(timeline, '2026-11-11T12:00:10Z', 100, 3300, '2026-11-11T12:00:07Z')!;
    expect(firstShowPosition(sample, 200, 3800).frame).toBe(21);
  });
  it('does not use the viewer wall clock or personal replay speed', () => {
    const sample = sampleFirstShow(timeline, '2026-11-11T12:00:05Z', 0, 0)!;
    vi.spyOn(Date, 'now').mockReturnValue(0);
    expect(firstShowPosition(sample, 200, 500).frame).toBe(11);
    vi.restoreAllMocks();
  });
  it('holds the first frame until the whole batch is ready', () => {
    const sample = sampleFirstShow({ ...timeline, started_at: null }, start, 0, 0)!;
    expect(firstShowPosition(sample, 200, 10000)).toEqual({ waiting: true, following: true, frame: 0 });
  });
  it('waits for its scheduled turn in a tournament and starts on the common clock', () => {
    const sample = sampleFirstShow(timeline, '2026-11-11T11:59:50Z', 0, 0)!;
    expect(firstShowPosition(sample, 200, 9000)).toEqual({ waiting: true, following: true, frame: 0 });
    expect(firstShowPosition(sample, 200, 11500)).toEqual({ waiting: false, following: true, frame: 3 });
  });
  it('finishes at the last frame without wrapping to the start', () => {
    const sample = sampleFirstShow(timeline, start, 0, 0)!;
    expect(firstShowPosition(sample, 10, 50000)).toEqual({ waiting: false, following: false, frame: 9 });
  });
  it('does not manufacture a live clock for an unavailable or malformed timeline', () => {
    expect(sampleFirstShow(null, start, 0, 0)).toBeNull();
    expect(sampleFirstShow(timeline, 'invalid', 0, 0)).toBeNull();
    expect(sampleFirstShow({ ...timeline, started_at: 'invalid' }, start, 0, 0)).toBeNull();
  });
});
