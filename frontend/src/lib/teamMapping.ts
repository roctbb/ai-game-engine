const TEAM_MAPPING_STORAGE_KEY = 'agp_team_by_game';

function scopedKey(gameId: string, userId: string): string {
  return `${userId.trim()}::${gameId.trim()}`;
}

function readMap(): Record<string, string> {
  try {
    const raw = JSON.parse(localStorage.getItem(TEAM_MAPPING_STORAGE_KEY) ?? '{}') as unknown;
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
    return Object.fromEntries(
      Object.entries(raw)
        .filter((entry): entry is [string, string] => typeof entry[0] === 'string' && typeof entry[1] === 'string'),
    );
  } catch {
    return {};
  }
}

function writeMap(map: Record<string, string>): void {
  try {
    localStorage.setItem(TEAM_MAPPING_STORAGE_KEY, JSON.stringify(map));
  } catch {
    // Mapping is only a convenience cache; API data remains the source of truth.
  }
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
