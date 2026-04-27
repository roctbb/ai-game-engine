const OMIT_POST_MESSAGE_FIELD = Symbol('omit-post-message-field');

export function sanitizeForPostMessage(value: unknown): unknown {
  const seen = new WeakSet<object>();

  const visit = (current: unknown): unknown | typeof OMIT_POST_MESSAGE_FIELD => {
    if (current === null) return null;
    if (current === undefined) return OMIT_POST_MESSAGE_FIELD;
    if (typeof current === 'string' || typeof current === 'boolean') return current;
    if (typeof current === 'number') return Number.isFinite(current) ? current : null;
    if (typeof current === 'bigint') return current.toString();
    if (typeof current === 'function' || typeof current === 'symbol') return OMIT_POST_MESSAGE_FIELD;
    if (current instanceof Date) return current.toISOString();
    if (Array.isArray(current)) return current.map((item) => {
      const sanitized = visit(item);
      return sanitized === OMIT_POST_MESSAGE_FIELD ? null : sanitized;
    });
    if (typeof current !== 'object') return null;
    if (seen.has(current)) return null;

    seen.add(current);
    const plain: Record<string, unknown> = {};
    for (const [key, nested] of Object.entries(current)) {
      const sanitized = visit(nested);
      if (sanitized !== OMIT_POST_MESSAGE_FIELD) plain[key] = sanitized;
    }
    seen.delete(current);
    return plain;
  };

  const sanitized = visit(value);
  return sanitized === OMIT_POST_MESSAGE_FIELD ? {} : sanitized;
}
