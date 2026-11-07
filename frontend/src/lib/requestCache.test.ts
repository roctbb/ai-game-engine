import { describe, expect, it, vi } from 'vitest';
import { createRequestCache } from './requestCache';

describe('catalog request cache', () => {
  it('deduplicates pending requests, expires results, and isolates sessions', async () => {
    let now = 0;
    const cache = createRequestCache(() => now);
    const load = vi.fn(async () => ['game']);
    await Promise.all([cache.get('student/games', load, 100), cache.get('student/games', load, 100)]);
    expect(load).toHaveBeenCalledTimes(1);
    await cache.get('student/games', load, 100);
    expect(load).toHaveBeenCalledTimes(1);
    await cache.get('teacher/games', load, 100);
    now = 101;
    await cache.get('student/games', load, 100);
    expect(load).toHaveBeenCalledTimes(3);
  });

  it('allows retries after a failed request', async () => {
    const cache = createRequestCache();
    await expect(cache.get('games', async () => { throw new Error('offline'); })).rejects.toThrow('offline');
    await expect(cache.get('games', async () => ['updated'])).resolves.toEqual(['updated']);
  });

  it('does not restore an invalidated entry when an older request finishes', async () => {
    const cache = createRequestCache();
    let finish!: (value: string) => void;
    const old = cache.get('games', () => new Promise<string>((resolve) => { finish = resolve; }));
    await Promise.resolve();
    cache.clear();
    await expect(cache.get('games', async () => 'new')).resolves.toBe('new');
    finish('old');
    await old;
    await expect(cache.get('games', async () => 'unexpected')).resolves.toBe('new');
  });
});
