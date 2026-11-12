/** A match draw is separate from a tournament decision about who advances. */
export function isMatchDraw(
  gameSlug: string | undefined,
  teamIds: readonly string[],
  scores: Readonly<Record<string, number>>,
  metrics?: Readonly<Record<string, unknown>>,
): boolean {
  if (metrics?.draw === true) return true;
  const participants = [...new Set(teamIds.filter(Boolean))];
  return gameSlug === 'ttt_connect5_v1' && participants.length > 1 &&
    participants.every(teamId => scores[teamId] === 0.5);
}

export function matchScoreLabel(score: number | null): string {
  return score === null ? '—' : score.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
}
