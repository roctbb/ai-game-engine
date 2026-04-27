/**
 * Creates a resilient EventSource that reconnects with exponential backoff.
 * Falls back to polling only after max retries are exhausted.
 */
export interface ResilientSSEOptions {
  url: string;
  /** Called with the new EventSource so the caller can attach listeners */
  onOpen: (source: EventSource) => void;
  /** Called when SSE permanently fails and caller should start polling */
  onFallbackToPolling: () => void;
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
}

export function createResilientSSE(options: ResilientSSEOptions): { close: () => void } {
  const {
    url,
    onOpen,
    onFallbackToPolling,
    maxRetries = 5,
    baseDelayMs = 1000,
    maxDelayMs = 30000,
  } = options;

  let source: EventSource | null = null;
  let retryCount = 0;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  function connect(): void {
    if (closed) return;
    source = new EventSource(url);

    source.addEventListener('open', () => {
      retryCount = 0;
    });

    onOpen(source);

    source.onerror = () => {
      if (closed) return;
      source?.close();
      source = null;

      if (retryCount >= maxRetries) {
        onFallbackToPolling();
        return;
      }

      const delay = Math.min(baseDelayMs * 2 ** retryCount, maxDelayMs);
      retryCount++;
      retryTimer = setTimeout(connect, delay);
    };
  }

  connect();

  return {
    close(): void {
      closed = true;
      if (retryTimer !== null) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
      if (source) {
        source.close();
        source = null;
      }
    },
  };
}
