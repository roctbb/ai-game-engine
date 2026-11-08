import { describe, expect, it } from 'vitest';
import { boundedPreview, frameForTick, readableMetrics, replayMoments, thinReplayMoments } from './replayInsights';
describe('replay analysis', () => {
  it('maps event ticks to frames, including sparse and terminal frames', () => {
    const frames = [{ tick: 0 }, { tick: 5 }, { tick: 12 }];
    expect([0, 3, 5, 100].map(t => frameForTick(frames, t))).toEqual([0, 1, 1, 2]);
    expect(frameForTick([], 5)).toBe(0);
  });
  it('keeps errors actionable without treating debug snapshots or prints as game events', () => {
    const moments = replayMoments([{ type: 'debug_snapshot', tick: 1 }, { type: 'bot_print', tick: 2 }, { type: 'bot_error', tick: 4, line: 7, role: 'agent', message: 'NameError' }, { type: 'key', tick: 0 }], [{ tick: 0 }, { tick: 4 }]);
    expect(moments).toHaveLength(2);
    expect(moments[0].label).toBe('Подобран ключ');
    expect(moments[1]).toMatchObject({ frame: 1, line: 7, role: 'agent', tone: 'error' });
  });
  it('shows only available numeric metrics and bounds large state previews', () => {
    expect(readableMetrics({ keys: 0, score: 25, unknown: 7, turns: null }).map(m => m.label)).toEqual(['Ключей с собой', 'Счёт']);
    expect((boundedPreview(Array(40).fill(0)) as unknown[])).toHaveLength(9);
  });
  it('groups consecutive repeated problems while retaining actionable Python errors', () => {
    const moments = replayMoments([{ type: 'blocked_move', tick: 0 }, { type: 'bot_error', tick: 0, line: 2 }, { type: 'blocked_move', tick: 1 }, { type: 'blocked_move', tick: 2 }], [{ tick: 0 }, { tick: 1 }, { tick: 2 }]);
    expect(moments).toHaveLength(2);
    expect(moments[0]).toMatchObject({ tick: 0, endTick: 2, count: 3, frame: 0 });
    expect(moments[1].line).toBe(2);
  });
});

describe('timeline density', () => {
  it('covers the whole timeline and preserves sparse problems', () => {
    const moments = replayMoments(Array.from({ length: 400 }, (_, tick) => ({ type: tick === 277 ? 'crash' : 'food', tick: tick * 2, slot: 'blue' })), []);
    const thinned = thinReplayMoments(moments, 20);
    expect(thinned).toHaveLength(20);
    expect(thinned[0].tick).toBe(0);
    expect(thinned.at(-1)?.tick).toBe(798);
    expect(thinned.some(m => m.tick === 554 && m.tone === 'error' && m.role === 'blue')).toBe(true);
  });
});
