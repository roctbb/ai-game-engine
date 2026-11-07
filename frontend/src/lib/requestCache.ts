/** Short-lived, session-scoped catalog reads. Live runs and lobbies are never cached. */
export function createRequestCache(now: () => number = Date.now) {
  const entries = new Map<string, { expiresAt: number; pending: boolean; promise: Promise<unknown> }>();

  function get<T>(key: string, load: () => Promise<T>, ttlMs = 30_000): Promise<T> {
    const existing = entries.get(key);
    if (existing && (existing.pending || existing.expiresAt > now())) return existing.promise as Promise<T>;
    const entry = { expiresAt: 0, pending: true, promise: Promise.resolve() as Promise<unknown> };
    entry.promise = Promise.resolve().then(load).then((value) => {
      entry.pending = false;
      entry.expiresAt = now() + ttlMs;
      return value;
    }, (error: unknown) => {
      if (entries.get(key) === entry) entries.delete(key);
      throw error;
    });
    entries.set(key, entry);
    return entry.promise as Promise<T>;
  }

  return { get, clear: () => entries.clear() };
}
