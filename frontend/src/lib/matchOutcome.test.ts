import { describe, expect, it } from 'vitest';
import { isMatchDraw, matchScoreLabel } from './matchOutcome';

describe('connect-five match draws', () => {
  it('recognizes half a point each even without legacy draw metadata', () => {
    expect(isMatchDraw('ttt_connect5_v1', ['a', 'b'], { a: .5, b: .5 })).toBe(true);
    expect(isMatchDraw('ttt_connect5_v1', ['b', 'a'], { a: .5, b: .5 }, { draw: false })).toBe(true);
  });
  it('requires results for the full roster', () => {
    expect(isMatchDraw('ttt_connect5_v1', ['a', 'b'], { a: .5 })).toBe(false);
    expect(isMatchDraw('ttt_connect5_v1', ['a', 'b'], { a: .5, foreign: .5 })).toBe(false);
    expect(isMatchDraw('ttt_connect5_v1', ['a', 'a'], { a: .5 })).toBe(false);
  });
  it('keeps a decisive result and other games distinct', () => {
    expect(isMatchDraw('ttt_connect5_v1', ['a', 'b'], { a: 1, b: 0 })).toBe(false);
    expect(isMatchDraw('tank_arena_v1', ['a', 'b'], { a: .5, b: .5 })).toBe(false);
  });
  it('honors explicit draws in older replays', () => {
    expect(isMatchDraw('ttt_connect5_v1', ['a', 'b'], { a: 0, b: 0 }, { draw: true })).toBe(true);
  });
  it('preserves fractional points in scoreboards', () => {
    expect(matchScoreLabel(.5)).toBe('0,5');
    expect(matchScoreLabel(6 / 40)).toBe('0,15');
    expect(matchScoreLabel(0)).toBe('0');
    expect(matchScoreLabel(1)).toBe('1');
    expect(matchScoreLabel(null)).toBe('—');
  });
});
