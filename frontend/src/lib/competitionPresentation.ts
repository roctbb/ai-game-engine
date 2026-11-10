import type { CompetitionMatchDto, CompetitionRunItemDto } from './api';

/** Older manually resolved ties may only have scores in their frozen run payload. */
export function competitionMatchScores(match: CompetitionMatchDto, runs: CompetitionRunItemDto[]): Record<string, number> {
  const result: Record<string, number> = {};
  const runIds = new Set(Object.values(match.run_ids_by_team));
  for (const run of runs) {
    if (!runIds.has(run.run_id)) continue;
    const scores = run.result_payload?.scores;
    if (!scores || typeof scores !== 'object' || Array.isArray(scores)) continue;
    for (const [teamId, score] of Object.entries(scores)) {
      if (match.team_ids.includes(teamId) && typeof score === 'number' && Number.isFinite(score)) result[teamId] = score;
    }
  }
  return { ...result, ...match.scores_by_team };
}
