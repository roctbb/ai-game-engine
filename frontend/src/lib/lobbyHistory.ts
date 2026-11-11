export function splitTrainingMatches<T extends { archived: boolean; status: string }>(matches: T[]): { current: T[]; history: T[] } {
  const current: T[] = [], history: T[] = [];
  for (const match of matches) {
    (!match.archived && ['simulation', 'replay'].includes(match.status) ? current : history).push(match);
  }
  return { current, history };
}

export function matchesHistoryQuery(text: string, timestamp: string | null, query: string, from: string, to: string): boolean {
  const normalize = (value: string) => value.toLocaleLowerCase('ru-RU').replace(/ё/g, 'е');
  if (!normalize(query).trim().split(/\s+/).every(word => normalize(text).includes(word))) return false;
  if (!from && !to) return true;
  const date = timestamp ? new Date(timestamp) : null;
  if (!date || !Number.isFinite(date.getTime())) return false;
  const day = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  return (!from || day >= from) && (!to || day <= to);
}
