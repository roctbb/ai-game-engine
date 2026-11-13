import type { LobbyParticipantStatsDto } from './api';

export type LobbyParticipantSort = 'score' | 'name';

export function sortLobbyParticipants(
  participants: LobbyParticipantStatsDto[],
  sort: LobbyParticipantSort,
  nameFor: (teamId: string) => string,
): LobbyParticipantStatsDto[] {
  const names = new Intl.Collator('ru-RU', { sensitivity: 'base', numeric: true });
  const hasScore = (participant: LobbyParticipantStatsDto) =>
    participant.matches_total > 0 && participant.average_score !== null && Number.isFinite(participant.average_score);

  return [...participants].sort((left, right) => {
    if (sort === 'score') {
      const leftScored = hasScore(left), rightScored = hasScore(right);
      if (leftScored !== rightScored) return leftScored ? -1 : 1;
      if (leftScored && rightScored && left.average_score !== right.average_score) {
        return right.average_score! - left.average_score!;
      }
    }
    return names.compare(nameFor(left.team_id), nameFor(right.team_id)) || left.team_id.localeCompare(right.team_id);
  });
}
