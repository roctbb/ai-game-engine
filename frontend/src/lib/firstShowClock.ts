export interface FirstShowTimeline { started_at: string | null; frame_ms: number }
export interface FirstShowSample {
  timeline: FirstShowTimeline;
  serverAtReceipt: number;
  receivedAt: number;
}

/** Anchor server time to a monotonic clock; browser wall-clock settings are irrelevant. */
export function sampleFirstShow(timeline: FirstShowTimeline | null | undefined, serverNow: string | undefined,
  requestedAt: number, receivedAt: number, serverReceivedAt?: string): FirstShowSample | null {
  if (!timeline || !serverNow || !Number.isFinite(Date.parse(serverNow))) return null;
  if (timeline.started_at !== null && !Number.isFinite(Date.parse(timeline.started_at))) return null;
  const serverWork = serverReceivedAt && Number.isFinite(Date.parse(serverReceivedAt))
    ? Math.max(0, Date.parse(serverNow) - Date.parse(serverReceivedAt)) : 0;
  const networkRoundTrip = Math.max(0, receivedAt - requestedAt - serverWork);
  return { timeline, serverAtReceipt: Date.parse(serverNow) + networkRoundTrip / 2, receivedAt };
}

export function firstShowPosition(sample: FirstShowSample, frameCount: number, now: number) {
  if (sample.timeline.started_at === null) return { waiting: true, following: true, frame: 0 };
  const elapsed = Math.max(0, sample.serverAtReceipt + Math.max(0, now - sample.receivedAt) - Date.parse(sample.timeline.started_at));
  const interval = Number.isFinite(sample.timeline.frame_ms) && sample.timeline.frame_ms > 0 ? sample.timeline.frame_ms : 500;
  const last = Math.max(0, frameCount - 1);
  const frame = Math.min(last, Math.floor(elapsed / interval));
  return { waiting: false, following: frameCount > 1 && frame < last, frame };
}
