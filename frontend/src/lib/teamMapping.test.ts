import { beforeEach, describe, expect, it, vi } from 'vitest';

import { loadTeamMapping, saveTeamMapping } from './teamMapping';

const storage = new Map<string, string>();

beforeEach(() => {
  storage.clear();
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key: string) => storage.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      storage.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      storage.delete(key);
    }),
  });
});

describe('team mapping storage', () => {
  it('ignores malformed cached values', () => {
    storage.set('agp_team_by_game', '{not-json');

    expect(loadTeamMapping('game_1', 'student')).toBe('');
  });

  it('keeps only string mappings from old cache formats', () => {
    storage.set('agp_team_by_game', JSON.stringify({
      'student::game_1': 'team_1',
      'student::game_2': 42,
      nested: { team_id: 'team_3' },
    }));

    expect(loadTeamMapping('game_1', 'student')).toBe('team_1');
    expect(loadTeamMapping('game_2', 'student')).toBe('');
  });

  it('does not throw when storage write is unavailable', () => {
    vi.mocked(localStorage.setItem).mockImplementation(() => {
      throw new Error('quota');
    });

    expect(() => saveTeamMapping('game_1', 'student', 'team_1')).not.toThrow();
  });
});
