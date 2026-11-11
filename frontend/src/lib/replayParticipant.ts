export interface ReplayParticipant {
  team_id: string;
  display_name: string;
  captain_user_id: string;
}

const normalizedName = (name: string) => name.trim().toLocaleLowerCase('ru-RU').replace(/ё/g, 'е');

export function replayParticipant<T extends ReplayParticipant>(
  player: { teamId: string; name: string }, participants: T[],
): T | undefined {
  const byId = participants.find(participant => participant.team_id === player.teamId);
  if (byId) return byId;
  const byName = participants.filter(participant => normalizedName(participant.display_name) === normalizedName(player.name));
  return byName.length === 1 ? byName[0] : undefined;
}
