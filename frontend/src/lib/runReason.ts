const KNOWN_REASON_LABELS: Record<string, string> = {
  canceled_by_game_update: 'Отменен из-за обновления игры',
  manual_moderation_ban: 'Отменен модератором (бан)',
  manual_stop_single_task: 'Остановлен пользователем',
  manual_cancel: 'Остановлен пользователем',
};

const KNOWN_REASON_TONES: Record<string, 'warning' | 'danger' | 'primary'> = {
  canceled_by_game_update: 'warning',
  manual_moderation_ban: 'danger',
  manual_stop_single_task: 'primary',
  manual_cancel: 'primary',
};

export function runReasonLabel(reason: string | null): string {
  if (!reason) return '—';
  return KNOWN_REASON_LABELS[reason] ?? 'Служебная причина';
}

export function runReasonToneClass(reason: string | null): string {
  if (!reason) return 'agp-pill--neutral';
  const tone = KNOWN_REASON_TONES[reason];
  if (tone === 'warning') return 'agp-pill--warning';
  if (tone === 'danger') return 'agp-pill--danger';
  if (tone === 'primary') return 'agp-pill--primary';
  return 'agp-pill--neutral';
}
