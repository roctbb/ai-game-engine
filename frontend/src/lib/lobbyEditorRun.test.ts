import { describe, expect, it } from 'vitest';
import { ownTrainingEditorRun, ownCompetitionEditorRun } from './lobbyEditorRun';

const foreign = { runs: [{ run_id: 'foreign-run', team_id: 'other' }], started_at: '2026-11-13T12:00:00Z' };
const own = { runs: [{ run_id: 'opponent-run', team_id: 'other' }, { run_id: 'own-run', team_id: 'me' }], started_at: '2026-11-13T10:00:00Z' };

describe('own match beside the lobby code editor', () => {
  it('shows no match for a newly joined player despite other active and archived games', () => {
    expect(ownTrainingEditorRun('new-player', [foreign], [own])).toBe('');
    expect(ownTrainingEditorRun(null, [foreign, own], [])).toBe('');
  });
  it('selects the player snapshot in their current match, even if its primary run belongs to an opponent', () => {
    expect(ownTrainingEditorRun('me', [foreign, own], [])).toBe('own-run');
  });
  it('keeps the own last match while other players continue playing', () => {
    expect(ownTrainingEditorRun('me', [foreign], [own])).toBe('own-run');
  });
  it('uses the latest own archived match without depending on history sorting', () => {
    const newer = { ...own, runs: [{ run_id: 'new-own-run', team_id: 'me' }], started_at: '2026-11-13T11:00:00Z' };
    expect(ownTrainingEditorRun('me', [], [own, newer, foreign])).toBe('new-own-run');
  });
  it('prefers a live own match, but does not confuse an old current batch with the latest own duel', () => {
    const newer = { ...own, runs: [{ run_id: 'new-own-run', team_id: 'me' }], status: 'finished', started_at: '2026-11-13T11:00:00Z' };
    expect(ownTrainingEditorRun('me', [{ ...own, status: 'replay' }], [newer])).toBe('own-run');
    expect(ownTrainingEditorRun('me', [{ ...own, status: 'finished' }], [newer])).toBe('new-own-run');
  });
  it('does not show an unrelated competition match or jump ahead of its broadcast', () => {
    const matches = [
      { match_id: 'broadcast', status: 'running', run_ids_by_team: { other: 'foreign-run' } },
      { match_id: 'future', status: 'running', run_ids_by_team: { me: 'future-own-run' } },
    ];
    expect(ownCompetitionEditorRun('me', matches, 'broadcast')).toBe('');
    expect(ownCompetitionEditorRun('new-player', matches)).toBe('');
    expect(ownCompetitionEditorRun('me', matches, 'future')).toBe('future-own-run');
  });
  it('allows a revealed own match while a different competition match is broadcasting', () => {
    const matches = [
      { match_id: 'past', status: 'finished', run_ids_by_team: { me: 'past-own-run' } },
      { match_id: 'broadcast', status: 'running', run_ids_by_team: { other: 'foreign-run' } },
      { match_id: 'future', status: 'running', run_ids_by_team: { me: 'future-own-run' } },
    ];
    expect(ownCompetitionEditorRun('me', matches, 'broadcast')).toBe('past-own-run');
    expect(ownCompetitionEditorRun('me', matches, null)).toBe('past-own-run');
  });
});
