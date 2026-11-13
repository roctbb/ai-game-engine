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
});
