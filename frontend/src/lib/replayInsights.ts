export type ReplayRecord = Record<string, unknown>;
export interface ReplayMoment { id: string; tick: number; frame: number; label: string; detail: string; tone: 'event' | 'error'; line?: number; role?: string; count?: number; endTick?: number }
export const record = (value: unknown): ReplayRecord => value && typeof value === 'object' && !Array.isArray(value) ? value as ReplayRecord : {};
const labels: Record<string, string> = {
  key: 'Подобран ключ', gate_opened: 'Открыты ворота', locked_gate: 'Нужен ключ', escaped: 'Выход достигнут',
  blocked_move: 'Путь заблокирован', invalid_action: 'Недопустимая команда', invalid_move: 'Недопустимый ход',
  bot_error: 'Ошибка Python', compile_error: 'Ошибка Python', runtime_error: 'Ошибка Python',
  respawn: 'Возрождение', crash: 'Змейка погибла', reverse_blocked: 'Разворот заблокирован', death: 'Игрок выбыл', eliminated: 'Игрок выбыл', collision: 'Столкновение', food: 'Подобрана еда',
  apple: 'Подобрано яблоко', coin: 'Подобрана монета', collected: 'Подобран предмет', goal: 'Цель достигнута',
  win: 'Победа', winner: 'Победа', finish: 'Завершение', shot: 'Выстрел', hit: 'Попадание',
  gate: 'Открыты ворота', refill: 'Запас пополнен', oxygen: 'Кислород пополнен', debug_limit: 'Отладочная запись ограничена',
};
export function frameForTick(frames: ReplayRecord[], tick: number): number {
  const index = frames.findIndex((frame, i) => Number(frame.tick ?? i) >= tick);
  return index < 0 ? Math.max(0, frames.length - 1) : index;
}
export function replayMoments(events: ReplayRecord[], frames: ReplayRecord[]): ReplayMoment[] {
  const moments = events.flatMap((event, i) => {
    const type = String(event.type ?? event.kind ?? '');
    if (['bot_print', 'print', 'stdout', 'debug_snapshot', 'log'].includes(type)) return [];
    const message = typeof event.message === 'string' ? event.message : '';
    const label = labels[type] ?? (message ? 'Событие игры' : '');
    if (!label) return [];
    const tick = Number.isFinite(Number(event.tick)) ? Number(event.tick) : 0;
    const actor = event.role ?? event.slot ?? event.actor ?? event.team_id;
    const action = typeof event.action === 'string' ? event.action : '';
    const coords = typeof event.x === 'number' && typeof event.y === 'number' ? `Клетка (${event.x}, ${event.y})` : '';
    return [{ id: String(i), tick, frame: frameForTick(frames, tick), label,
      detail: [action && `Команда: ${action}`, message, coords].filter(Boolean).join(' · '),
      tone: /error|invalid|blocked|locked|death|crash|collision|eliminat/.test(type) ? 'error' as const : 'event' as const,
      line: typeof event.line === 'number' && event.line > 0 ? event.line : undefined,
      role: typeof actor === 'string' || typeof actor === 'number' ? String(actor) : undefined }];
  }).sort((a, b) => a.tick - b.tick);
  const grouped: ReplayMoment[] = [];
  const lastByKind = new Map<string, ReplayMoment>();
  for (const moment of moments) {
    const key = `${moment.label}:${moment.detail}:${moment.role ?? ''}:${moment.line ?? ''}`;
    const previous = lastByKind.get(key);
    if (previous && moment.tick === (previous.endTick ?? previous.tick) + 1 && !moment.line) {
      previous.count = (previous.count ?? 1) + 1;
      previous.endTick = moment.tick;
    } else {
      grouped.push(moment);
      lastByKind.set(key, moment);
    }
  }
  return grouped.map(moment => moment.count ? { ...moment, label: `${moment.label} · ${moment.count} раз`, detail: `${moment.detail} · Ходы ${moment.tick}–${moment.endTick}` } : moment);
}
/** Keep the full timeline represented, giving problem markers priority. */
export function thinReplayMoments(moments: ReplayMoment[], limit = 150): ReplayMoment[] {
  if (moments.length <= limit) return moments;
  if (limit <= 0) return [];
  const selected = new Set<ReplayMoment>([moments[0]]);
  if (limit > 1) selected.add(moments[moments.length - 1]);
  const sample = (items: ReplayMoment[], count: number) => {
    for (let i = 0; i < count && items.length; i += 1) {
      selected.add(items[Math.round(i * (items.length - 1) / Math.max(1, count - 1))]);
    }
  };
  const errors = moments.filter(m => m.tone === 'error' && !selected.has(m));
  sample(errors, Math.min(errors.length, limit - selected.size));
  const others = moments.filter(m => !selected.has(m));
  sample(others, limit - selected.size);
  return moments.filter(m => selected.has(m));
}
export const metricLabels: Record<string, string> = {
  turns: 'Ходов', score: 'Счёт', keys: 'Ключей с собой', keys_collected: 'Собрано ключей', gates_opened: 'Открыто ворот',
  invalid_moves: 'Недопустимых ходов', bot_errors: 'Разных ошибок Python', oxygen: 'Кислород', battery: 'Заряд',
  water: 'Вода', fuel: 'Топливо', coins: 'Монеты', coins_collected: 'Собрано монет', collected: 'Собрано',
  apples: 'Яблоки', food_eaten: 'Съедено', length: 'Длина', lamps_lit: 'Зажжено ламп', lamps_left: 'Осталось ламп',
  ore_mined: 'Добыто руды', delivered: 'Доставлено', planks: 'Доски', planks_collected: 'Собрано досок',
  rescued: 'Спасено', cleaned: 'Убрано', lives: 'Жизни', health: 'Здоровье', shield: 'Щит', tick: 'Ход',
};
export function readableMetrics(value: unknown): { key: string; label: string; value: string }[] {
  return Object.entries(record(value)).flatMap(([key, raw]) => metricLabels[key] && typeof raw === 'number'
    ? [{ key, label: metricLabels[key], value: raw.toLocaleString('ru-RU', { maximumFractionDigits: 1 }) }] : []);
}
export function boundedPreview(value: unknown): unknown {
  const visit = (v: unknown, depth: number): unknown => {
    if (depth > 2) return '…';
    if (Array.isArray(v)) return [...v.slice(0, 8).map(x => visit(x, depth + 1)), ...(v.length > 8 ? ['…'] : [])];
    if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).slice(0, 16).map(([k, x]) => [k, visit(x, depth + 1)]));
    return typeof v === 'string' ? v.slice(0, 300) : v;
  };
  return visit(value, 0);
}
