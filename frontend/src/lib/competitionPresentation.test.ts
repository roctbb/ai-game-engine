import { describe, expect, it } from 'vitest';
import { competitionMatchScores } from './competitionPresentation';
import type { CompetitionMatchDto, CompetitionRunItemDto } from './api';
const match: CompetitionMatchDto = { match_id: 'm', round_index: 1, team_ids: ['a', 'b'], status: 'finished', run_ids_by_team: { a: 'r1', b: 'r2' }, scores_by_team: {}, placements_by_team: {}, advanced_team_ids: ['a'], tie_break_reason: null };
const run = (id: string, scores: Record<string, number>): CompetitionRunItemDto => ({ run_id: id, team_id: 'a', status: 'finished', error_message: null, result_payload: { scores } });
describe('archived tournament scores', () => {
  it('recovers scores from the original run after a legacy manual tie decision', () => expect(competitionMatchScores(match, [run('r1', { a: 12, b: 12 })])).toEqual({ a: 12, b: 12 }));
  it('uses the resolved match result before the legacy payload', () => expect(competitionMatchScores({ ...match, scores_by_team: { a: 20 } }, [run('r1', { a: 12, b: 12 })])).toEqual({ a: 20, b: 12 }));
  it('ignores scores from another match or participant', () => expect(competitionMatchScores(match, [run('other', { a: 99 }), run('r1', { foreign: 100 })])).toEqual({}));
});
