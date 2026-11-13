import type { LobbyParticipantStatsDto } from './api';

export type LobbyParticipantSort = 'score' | 'name';

export interface RankedLobbyParticipant extends LobbyParticipantStatsDto {
  place: number | null;
}

export function sortLobbyParticipants(
  participants: LobbyParticipantStatsDto[],
  sort: LobbyParticipantSort,
  nameFor: (teamId: string) => string,
): RankedLobbyParticipant[] {
  const names = new Intl.Collator('ru-RU', { sensitivity: 'base', numeric: true });
  const hasScore = (participant: LobbyParticipantStatsDto) =>
    participant.matches_total > 0 && participant.average_score !== null && Number.isFinite(participant.average_score);

  const compareNames = (left: LobbyParticipantStatsDto, right: LobbyParticipantStatsDto) =>
    names.compare(nameFor(left.team_id), nameFor(right.team_id)) || left.team_id.localeCompare(right.team_id);
  const byScore = [...participants].sort((left, right) => {
    const leftScored = hasScore(left), rightScored = hasScore(right);
    if (leftScored !== rightScored) return leftScored ? -1 : 1;
    if (leftScored && rightScored && left.average_score !== right.average_score) {
      return right.average_score! - left.average_score!;
    }
    return compareNames(left, right);
  });

  let place = 0;
  let previousScore: number | null = null;
  const ranked = byScore.map((participant, index) => {
    if (!hasScore(participant)) return { ...participant, place: null };
    if (participant.average_score !== previousScore) place = index + 1;
    previousScore = participant.average_score;
    return { ...participant, place };
  });
  return sort === 'name' ? ranked.sort(compareNames) : ranked;
}
