import { describe, expect, it } from 'vitest';
import type { LobbyParticipantStatsDto } from './api';
import { sortLobbyParticipants } from './lobbyLeaderboard';

const row = (name: string, score: number | null, wins = 0, games = 10): LobbyParticipantStatsDto => ({
  team_id: name, captain_user_id: name, display_name: name,
  average_score: score, wins, matches_total: games,
});
const sortedNames = (rows: LobbyParticipantStatsDto[], sort: 'score' | 'name') =>
  sortLobbyParticipants(rows, sort, name => name).map(item => item.team_id);

describe('lobby participant leaderboard', () => {
  it('ranks by average score rather than wins or win rate', () => {
    const rows = [row('Анна', .5, 9), row('Борис', .75, 2), row('Вера', .15, 6, 40)];
    expect(sortedNames(rows, 'score')).toEqual(['Борис', 'Анна', 'Вера']);
    expect(rows.map(item => item.team_id)).toEqual(['Анна', 'Борис', 'Вера']);
  });
  it('puts missing results after scored participants, including zero and negative scores', () => {
    const rows = [row('Анна', null, 0, 0), row('Борис', -2), row('Вера', 0), row('Глеб', 99, 0, 0)];
    expect(sortedNames(rows, 'score')).toEqual(['Вера', 'Борис', 'Анна', 'Глеб']);
  });
  it('uses names for equal scores and stays stable when incoming order changes', () => {
    const rows = [row('Борис', .5, 9), row('Анна', .5, 1)];
    expect(sortedNames(rows, 'score')).toEqual(['Анна', 'Борис']);
    expect(sortedNames(rows.reverse(), 'score')).toEqual(['Анна', 'Борис']);
  });
  it('sorts the whole roster alphabetically when selected', () => {
    const rows = [row('Борис', 1), row('Вера', .5), row('Анна', null, 0, 0)];
    expect(sortedNames(rows, 'name')).toEqual(['Анна', 'Борис', 'Вера']);
  });
  it('shares places for equal averages and skips the occupied positions', () => {
    const rows = [row('Глеб', .5), row('Анна', .75), row('Вера', .75), row('Борис', .5), row('Даша', 0)];
    expect(sortLobbyParticipants(rows, 'score', name => name).map(item => [item.team_id, item.place]))
      .toEqual([['Анна', 1], ['Вера', 1], ['Борис', 3], ['Глеб', 3], ['Даша', 5]]);
  });
  it('keeps result places when sorting by name or filtering the list', () => {
    const rows = [row('Анна', 0), row('Борис', .75), row('Вера', .5), row('Глеб', .5)];
    const byName = sortLobbyParticipants(rows, 'name', name => name);
    expect(byName.map(item => item.place)).toEqual([4, 1, 2, 2]);
    expect(byName.filter(item => item.team_id === 'Вера')[0].place).toBe(2);
  });
  it('leaves unscored participants unranked while zero and negative results get places', () => {
    const rows = [row('Анна', null, 0, 0), row('Борис', -1), row('Вера', 0), row('Глеб', 99, 0, 0)];
    expect(sortLobbyParticipants(rows, 'score', name => name).map(item => [item.team_id, item.place]))
      .toEqual([['Вера', 1], ['Борис', 2], ['Анна', null], ['Глеб', null]]);
  });
});
