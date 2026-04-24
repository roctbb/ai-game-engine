const TEAM_MAPPING_STORAGE_KEY = 'agp_team_by_game';

function scopedKey(gameId: string, userId: string): string {
  return `${userId.trim()}::${gameId.trim()}`;
}

function readMap(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(TEAM_MAPPING_STORAGE_KEY) ?? '{}') as Record<string, string>;
  } catch {
    return {};
  }
}

function writeMap(map: Record<string, string>): void {
  localStorage.setItem(TEAM_MAPPING_STORAGE_KEY, JSON.stringify(map));
}

export function loadTeamMapping(gameId: string, userId: string): string {
  const key = scopedKey(gameId, userId);
  return readMap()[key] ?? '';
}

export function saveTeamMapping(gameId: string, userId: string, teamId: string): void {
  const map = readMap();
  map[scopedKey(gameId, userId)] = teamId;
  writeMap(map);
}
