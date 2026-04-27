import { describe, expect, it } from 'vitest';

import { sanitizeForPostMessage } from './postMessage';

describe('sanitizeForPostMessage', () => {
  it('keeps score nulls and strips only unclonable fields', () => {
    const payload = {
      score: null,
      nested: {
        value: 10,
        ignored: undefined,
        callback: () => undefined,
      },
      list: [1, undefined, () => undefined, null],
    };

    expect(sanitizeForPostMessage(payload)).toEqual({
      score: null,
      nested: { value: 10 },
      list: [1, null, null, null],
    });
  });

  it('does not drop the whole payload when one nested value is circular', () => {
    const payload: Record<string, unknown> = { runId: 'run_1' };
    payload.self = payload;

    expect(sanitizeForPostMessage(payload)).toEqual({
      runId: 'run_1',
      self: null,
    });
  });

  it('normalizes non-json scalar values', () => {
    expect(sanitizeForPostMessage({
      nan: Number.NaN,
      infinite: Number.POSITIVE_INFINITY,
      big: 42n,
      createdAt: new Date('2026-04-27T00:00:00.000Z'),
    })).toEqual({
      nan: null,
      infinite: null,
      big: '42',
      createdAt: '2026-04-27T00:00:00.000Z',
    });
  });

  it('returns payloads that can be structured-cloned by postMessage', () => {
    const payload = {
      players: [
        { id: 'team-1', score: 10, callback: () => undefined },
        { id: 'team-2', score: Number.NaN, circular: null as unknown },
      ],
      map: new Map([['ignored-by-plain-object-copy', 1]]),
    };
    payload.players[1].circular = payload.players;

    const sanitized = sanitizeForPostMessage(payload);

    expect(() => structuredClone(sanitized)).not.toThrow();
  });
});
