interface EditorMatch {
  runs: { run_id: string; team_id: string }[];
  status?: string;
  started_at?: string | null;
  finished_at?: string | null;
}

// Editing a bot must never inherit the spectator's selected match or fallback.
export function ownTrainingEditorRun(teamId: string | null | undefined, current: EditorMatch[], history: EditorMatch[]): string {
  if (!teamId) return '';
  const live = (match: EditorMatch) => ['simulation', 'replay', 'result'].includes(match.status || '');
  const sorted = [...current, ...history].sort((left, right) =>
    Number(live(right)) - Number(live(left)) ||
    (Date.parse(right.started_at || right.finished_at || '') || 0) -
    (Date.parse(left.started_at || left.finished_at || '') || 0));
  for (const match of sorted) {
    const own = match.runs.find(run => run.team_id === teamId);
    if (own) return own.run_id;
  }
  return '';
}

interface EditorCompetitionMatch {
  match_id: string;
  status: string;
  run_ids_by_team: Record<string, string | undefined>;
}

export function ownCompetitionEditorRun(teamId: string | null | undefined, matches: EditorCompetitionMatch[], broadcastMatchId?: string | null): string {
  if (!teamId) return '';
  const match = [...matches].reverse().find(item => item.run_ids_by_team[teamId] &&
    (broadcastMatchId === undefined || item.match_id === broadcastMatchId || item.status === 'finished'));
  return match?.run_ids_by_team[teamId] || '';
}
