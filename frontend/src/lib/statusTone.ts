/** Status colors express state, while the accompanying label carries its meaning. */
export function statusPillClass(status: string): string {
  if (['open', 'ready', 'filled', 'finished', 'completed'].includes(status)) return 'agp-pill--success';
  if (['running', 'queued', 'syncing', 'active'].includes(status)) return 'agp-pill--primary';
  if (['paused', 'updating', 'blocked', 'dirty', 'empty', 'awaiting_tiebreak'].includes(status)) return 'agp-pill--warning';
  if (['failed', 'error', 'timeout', 'incompatible', 'banned'].includes(status)) return 'agp-pill--danger';
  return 'agp-pill--neutral';
}
