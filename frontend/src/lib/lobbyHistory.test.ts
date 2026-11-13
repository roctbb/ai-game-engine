import { describe, expect, it } from 'vitest';
import { matchesHistoryQuery, splitTrainingMatches } from './lobbyHistory';

describe('lobby history', () => {
  it('separates active simulation and first playback from completed and archived matches', () => {
    const rows = [
      { id: 1, archived: false, status: 'simulation' },
      { id: 2, archived: false, status: 'replay' },
      { id: 3, archived: false, status: 'result' },
      { id: 4, archived: true, status: 'finished' },
      { id: 5, archived: false, status: 'finished' },
      { id: 6, archived: false, status: 'queued' },
    ];
    const { current, history } = splitTrainingMatches(rows);
    expect(current.map(row => row.id)).toEqual([1, 2, 6]);
    expect(history.map(row => row.id)).toEqual([3, 4, 5]);
  });
  it('finds names regardless of case, word order and ё spelling', () => {
    expect(matchesHistoryQuery('Семён Иванов · 14:30', null, 'ИВАНОВ семен', '', '')).toBe(true);
    expect(matchesHistoryQuery('Семён Иванов · 14:30', null, '14:30 Петров', '', '')).toBe(false);
  });
  it('includes both boundary dates and excludes unknown dates from a date-filtered result', () => {
    expect(matchesHistoryQuery('', '2026-11-11T00:00:00', '', '2026-11-11', '2026-11-11')).toBe(true);
    expect(matchesHistoryQuery('', '2026-11-11T23:59:59', '', '2026-11-11', '2026-11-11')).toBe(true);
    expect(matchesHistoryQuery('', '2026-11-12T00:00:00', '', '2026-11-11', '2026-11-11')).toBe(false);
    expect(matchesHistoryQuery('', null, '', '2026-11-11', '')).toBe(false);
    expect(matchesHistoryQuery('', null, '', '', '')).toBe(true);
  });
});
