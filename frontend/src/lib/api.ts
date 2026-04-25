export type GameMode = 'single_task' | 'small_match' | 'massive_lobby';
export type CatalogMetadataStatus = 'draft' | 'ready' | 'archived';
export type UserRole = 'student' | 'teacher' | 'admin';
export type AuthProvider = 'dev' | 'geekclass';

export interface GameVersionDto {
  version_id: string;
  semver: string;
  required_slot_keys: string[];
  required_worker_labels: Record<string, string>;
}

export interface GameDto {
  game_id: string;
  slug: string;
  title: string;
  mode: GameMode;
  description: string | null;
  difficulty: string | null;
  topics: string[];
  catalog_metadata_status: CatalogMetadataStatus;
  active_version_id: string;
  versions: GameVersionDto[];
}

export interface GameTopicsDto {
  game_id: string;
  topics: string[];
}

export interface GameSlotTemplateDto {
  slot_key: string;
  language: string;
  code: string;
}

export interface GameDemoStrategyDto {
  strategy_id: string;
  slot_key: string;
  title: string;
  language: string;
  code: string;
  description: string | null;
}

export interface GameTemplatesDto {
  game_id: string;
  game_slug: string;
  code_api_mode: string;
  player_instruction: string | null;
  templates: GameSlotTemplateDto[];
  demo_strategies: GameDemoStrategyDto[];
}

export interface GameDocumentationLinkDto {
  title: string;
  path: string;
  content: string | null;
}

export interface GameDocumentationDto {
  game_id: string;
  slug: string;
  player_instruction: string | null;
  links: GameDocumentationLinkDto[];
}

export interface SingleTaskCatalogItemDto {
  game_id: string;
  slug: string;
  title: string;
  description: string | null;
  difficulty: string | null;
  topics: string[];
  catalog_metadata_status: CatalogMetadataStatus;
  attempts_finished: number;
  solved_users: number;
  has_score_model: boolean;
}

export interface SingleTaskCatalogGroupDto {
  topic: string;
  difficulty: string;
  items: SingleTaskCatalogItemDto[];
}

export interface SingleTaskSolvedSummaryEntryDto {
  place: number;
  user_id: string;
  solved_tasks_count: number;
  solved_game_ids: string[];
}

export interface SingleTaskSolvedSummaryDto {
  total_single_tasks: number;
  entries: SingleTaskSolvedSummaryEntryDto[];
}

export interface SingleTaskLeaderboardEntryDto {
  place: number;
  user_id: string;
  solved: boolean;
  solved_attempts: number;
  finished_attempts: number;
  best_score: number | null;
  best_run_id: string | null;
  last_finished_at: string | null;
}

export interface SingleTaskLeaderboardDto {
  game_id: string;
  leaderboard_kind: 'score' | 'solved';
  entries: SingleTaskLeaderboardEntryDto[];
}

export interface SingleTaskAttemptLogsDto {
  attempt_id: string;
  lines: string[];
}

export interface SlotStateDto {
  slot_key: string;
  state: 'filled' | 'empty' | 'dirty' | 'locked' | 'incompatible';
  required: boolean;
  code: string | null;
  revision: number | null;
}

export interface TeamWorkspaceDto {
  team_id: string;
  game_id: string;
  captain_user_id: string;
  version_id: string;
  slot_states: SlotStateDto[];
}

export interface TeamDto {
  team_id: string;
  game_id: string;
  name: string;
  captain_user_id: string;
}

export type GameSourceType = 'embedded' | 'git';
export type GameSourceStatus = 'active' | 'disabled';
export type GameSourceSyncStatus = 'never' | 'syncing' | 'finished' | 'failed';

export interface GameSourceDto {
  source_id: string;
  source_type: GameSourceType;
  repo_url: string;
  default_branch: string;
  status: GameSourceStatus;
  last_sync_status: GameSourceSyncStatus;
  last_synced_commit_sha: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface GameSourceSyncDto {
  sync_id: string;
  source_id: string;
  requested_by: string;
  status: GameSourceSyncStatus;
  build_id: string | null;
  image_digest: string | null;
  error_message: string | null;
  commit_sha: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface GameSourceSyncResultDto {
  source: GameSourceDto;
  sync: GameSourceSyncDto;
}

export type WorkerStatus = 'online' | 'offline' | 'draining' | 'disabled';

export interface WorkerDto {
  worker_id: string;
  hostname: string;
  capacity_total: number;
  capacity_available: number;
  status: WorkerStatus;
  labels: Record<string, string>;
}

export type LobbyKind = 'training' | 'competition';
export type LobbyAccess = 'public' | 'code';
export type LobbyStatus = 'draft' | 'open' | 'running' | 'paused' | 'updating' | 'closed';

export interface LobbyTeamStateDto {
  team_id: string;
  ready: boolean;
  blocker_reason: string | null;
}

export interface LobbyParticipantStatsDto {
  team_id: string;
  captain_user_id: string;
  display_name: string;
  matches_total: number;
  wins: number;
  average_score: number | null;
}

export interface LobbyDto {
  lobby_id: string;
  game_id: string;
  game_version_id: string;
  title: string;
  kind: LobbyKind;
  access: LobbyAccess;
  status: LobbyStatus;
  max_teams: number;
  teams: LobbyTeamStateDto[];
  last_scheduled_run_ids: string[];
  my_team_id: string | null;
  my_status: 'not_in_lobby' | 'preparing' | 'queued' | 'playing' | string | null;
  current_run_id: string | null;
  playing_team_ids: string[];
  queued_team_ids: string[];
  preparing_team_ids: string[];
  current_run_ids: string[];
  archived_run_ids: string[];
  participant_stats: LobbyParticipantStatsDto[];
}

export interface LobbyCurrentRunDto {
  lobby_id: string;
  team_id: string | null;
  run_id: string | null;
  status: string;
}

export interface LobbyCompetitionDto {
  competition_id: string;
  title: string;
  status: string;
}

export interface LobbyCompetitionArchiveDto {
  lobby_id: string;
  items: LobbyCompetitionDto[];
}

export type CompetitionFormat = 'single_elimination';
export type TieBreakPolicy = 'manual' | 'shared_advancement';
export type CompetitionCodePolicy =
  | 'locked_on_registration'
  | 'locked_on_start'
  | 'allowed_between_matches';
export type CompetitionStatus = 'draft' | 'running' | 'paused' | 'completed' | 'finished';
export type CompetitionRoundStatus = 'running' | 'finished';
export type CompetitionMatchStatus =
  | 'pending'
  | 'running'
  | 'finished'
  | 'awaiting_tiebreak'
  | 'auto_advanced';

export interface CompetitionEntrantDto {
  team_id: string;
  ready: boolean;
  banned: boolean;
  blocker_reason: string | null;
}

export interface CompetitionMatchDto {
  match_id: string;
  round_index: number;
  team_ids: string[];
  status: CompetitionMatchStatus;
  run_ids_by_team: Record<string, string>;
  scores_by_team: Record<string, number>;
  placements_by_team: Record<string, number>;
  advanced_team_ids: string[];
  tie_break_reason: string | null;
}

export interface CompetitionRoundDto {
  round_index: number;
  status: CompetitionRoundStatus;
  matches: CompetitionMatchDto[];
}

export interface CompetitionDto {
  competition_id: string;
  game_id: string;
  game_version_id: string;
  lobby_id: string | null;
  title: string;
  format: CompetitionFormat;
  tie_break_policy: TieBreakPolicy;
  code_policy: CompetitionCodePolicy;
  advancement_top_k: number;
  match_size: number;
  status: CompetitionStatus;
  entrants: CompetitionEntrantDto[];
  rounds: CompetitionRoundDto[];
  current_round_index: number | null;
  winner_team_ids: string[];
  pending_reason: string | null;
  last_scheduled_run_ids: string[];
}

export interface CompetitionRunItemDto {
  run_id: string;
  team_id: string;
  status: string;
  error_message: string | null;
}

export interface AntiplagiarismWarningDto {
  warning_id: string;
  competition_id: string;
  team_a_id: string;
  team_b_id: string;
  slot_key: string;
  similarity: number;
  algorithm: string;
  run_a_id: string;
  run_b_id: string;
  created_at: string;
}

export interface RunDto {
  run_id: string;
  team_id: string;
  game_id: string;
  requested_by: string;
  run_kind: 'single_task' | 'training_match' | 'competition_match';
  lobby_id: string | null;
  target_version_id: string | null;
  status: 'created' | 'queued' | 'running' | 'finished' | 'failed' | 'timeout' | 'canceled';
  snapshot_id: string | null;
  snapshot_version_id: string | null;
  worker_id: string | null;
  revisions_by_slot: Record<string, number>;
  result_payload: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunWatchContextDto {
  run_id: string;
  game_id: string;
  game_slug: string;
  run_kind: 'single_task' | 'training_match' | 'competition_match';
  status: 'created' | 'queued' | 'running' | 'finished' | 'failed' | 'timeout' | 'canceled';
  renderer_entrypoint: string | null;
  renderer_url: string | null;
  renderer_protocol: string;
}

export type StreamChannel = 'run' | 'lobby' | 'lobbies' | 'competition';
export type StreamKind = 'snapshot' | 'terminal' | 'keepalive';

export interface StreamEnvelopeDto<TPayload = Record<string, unknown>> {
  channel: StreamChannel;
  entity_id: string;
  kind: StreamKind;
  emitted_at: string;
  status?: string;
  payload?: TPayload;
}

export interface ReplayDto {
  replay_id: string;
  run_id: string;
  game_id: string;
  run_kind: 'single_task' | 'training_match' | 'competition_match';
  status: 'created' | 'queued' | 'running' | 'finished' | 'failed' | 'timeout' | 'canceled';
  visibility: 'public' | 'private';
  frames: Record<string, unknown>[];
  events: Record<string, unknown>[];
  summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AuthOptionsDto {
  dev_login_enabled: boolean;
  geekclass_enabled: boolean;
}

export interface SessionDto {
  session_id: string;
  external_user_id: string;
  nickname: string;
  role: UserRole;
  provider: AuthProvider;
}

const API_BASE = '/api/v1';
const SESSION_STORAGE_KEY = 'agp_session_id';

class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export function getStoredSessionId(): string {
  return localStorage.getItem(SESSION_STORAGE_KEY) ?? '';
}

export function storeSessionId(sessionId: string): void {
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

export function clearStoredSessionId(): void {
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const sessionId = getStoredSessionId();
  const headers = new Headers(init?.headers ?? undefined);
  headers.set('Content-Type', 'application/json');
  if (sessionId) {
    headers.set('X-Session-Id', sessionId);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    let details = response.statusText;
    try {
      const payload = await response.json();
      const errorBlock = payload?.error;
      if (errorBlock?.message) {
        details = String(errorBlock.message);
      } else if (payload?.detail) {
        details = String(payload.detail);
      }
    } catch {
      // ignore parse errors and keep default status text
    }
    throw new ApiError(`API ${response.status}: ${details}`);
  }
  return (await response.json()) as T;
}

export function listGames(): Promise<GameDto[]> {
  return request<GameDto[]>('/games');
}

export function listSingleTaskCatalog(): Promise<SingleTaskCatalogItemDto[]> {
  return request<SingleTaskCatalogItemDto[]>('/catalog/single-tasks');
}

export function listSingleTaskCatalogGrouped(): Promise<SingleTaskCatalogGroupDto[]> {
  return request<SingleTaskCatalogGroupDto[]>('/catalog/single-tasks/grouped');
}

export function getSingleTaskSolvedSummary(limit = 10): Promise<SingleTaskSolvedSummaryDto> {
  return request<SingleTaskSolvedSummaryDto>(
    `/catalog/single-tasks/solved-summary?limit=${encodeURIComponent(String(limit))}`
  );
}

export function getSingleTaskLeaderboard(gameId: string, limit = 10): Promise<SingleTaskLeaderboardDto> {
  return request<SingleTaskLeaderboardDto>(
    `/single-tasks/${encodeURIComponent(gameId)}/leaderboard?limit=${encodeURIComponent(String(limit))}`
  );
}

export function listGameSources(): Promise<GameSourceDto[]> {
  return request<GameSourceDto[]>('/game-sources');
}

export function createGameSource(payload: {
  repo_url: string;
  default_branch: string;
  created_by: string;
}): Promise<GameSourceDto> {
  return request<GameSourceDto>('/game-sources', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function setGameSourceStatus(payload: {
  source_id: string;
  status: GameSourceStatus;
}): Promise<GameSourceDto> {
  return request<GameSourceDto>(`/game-sources/${encodeURIComponent(payload.source_id)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status: payload.status }),
  });
}

export function triggerGameSourceSync(payload: {
  source_id: string;
  requested_by: string;
}): Promise<GameSourceSyncResultDto> {
  return request<GameSourceSyncResultDto>(`/game-sources/${encodeURIComponent(payload.source_id)}/sync`, {
    method: 'POST',
    body: JSON.stringify({ requested_by: payload.requested_by }),
  });
}

export function listGameSourceSyncHistory(sourceId: string): Promise<GameSourceSyncDto[]> {
  return request<GameSourceSyncDto[]>(`/game-sources/${encodeURIComponent(sourceId)}/sync-history`);
}

export function listWorkers(): Promise<WorkerDto[]> {
  return request<WorkerDto[]>('/workers');
}

export function setWorkerStatus(payload: {
  worker_id: string;
  status: WorkerStatus;
}): Promise<WorkerDto> {
  return request<WorkerDto>(`/workers/${encodeURIComponent(payload.worker_id)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status: payload.status }),
  });
}

export function getAuthOptions(): Promise<AuthOptionsDto> {
  return request<AuthOptionsDto>('/auth/options');
}

export function devLogin(payload: { nickname: string; role: UserRole }): Promise<SessionDto> {
  return request<SessionDto>('/auth/dev-login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function me(): Promise<SessionDto> {
  return request<SessionDto>('/me');
}

export function logout(): Promise<{ status: string }> {
  return request<{ status: string }>('/auth/logout', {
    method: 'POST',
  });
}

export function getGame(gameId: string): Promise<GameDto> {
  return request<GameDto>(`/games/${encodeURIComponent(gameId)}`);
}

export function patchGame(payload: {
  game_id: string;
  title?: string | null;
  description?: string | null;
  difficulty?: string | null;
  topics?: string[] | null;
  catalog_metadata_status?: CatalogMetadataStatus | null;
}): Promise<GameDto> {
  const body: Record<string, unknown> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.description !== undefined) body.description = payload.description;
  if (payload.difficulty !== undefined) body.difficulty = payload.difficulty;
  if (payload.topics !== undefined) body.topics = payload.topics;
  if (payload.catalog_metadata_status !== undefined) body.catalog_metadata_status = payload.catalog_metadata_status;
  return request<GameDto>(`/games/${encodeURIComponent(payload.game_id)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export function listGameVersions(gameId: string): Promise<GameVersionDto[]> {
  return request<GameVersionDto[]>(`/games/${encodeURIComponent(gameId)}/versions`);
}

export function getGameVersion(gameId: string, versionId: string): Promise<GameVersionDto> {
  return request<GameVersionDto>(`/games/${encodeURIComponent(gameId)}/versions/${encodeURIComponent(versionId)}`);
}

export function getGameTopics(gameId: string): Promise<GameTopicsDto> {
  return request<GameTopicsDto>(`/games/${encodeURIComponent(gameId)}/topics`);
}

export function getGameTemplates(gameId: string): Promise<GameTemplatesDto> {
  return request<GameTemplatesDto>(`/games/${encodeURIComponent(gameId)}/templates`);
}

export function getGameDocs(gameId: string): Promise<GameDocumentationDto> {
  return request<GameDocumentationDto>(`/games/${encodeURIComponent(gameId)}/docs`);
}

export function updateGameCatalogMetadata(payload: {
  game_id: string;
  description: string | null;
  difficulty: string | null;
  topics: string[];
  catalog_metadata_status: CatalogMetadataStatus;
}): Promise<GameDto> {
  return request<GameDto>(`/games/${encodeURIComponent(payload.game_id)}/catalog-metadata`, {
    method: 'PATCH',
    body: JSON.stringify({
      description: payload.description,
      difficulty: payload.difficulty,
      topics: payload.topics,
      catalog_metadata_status: payload.catalog_metadata_status,
    }),
  });
}

export function createTeam(payload: {
  game_id: string;
  name: string;
  captain_user_id: string;
}): Promise<TeamDto> {
  return request<TeamDto>('/teams', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listTeamsByGame(gameId: string): Promise<TeamDto[]> {
  return request<TeamDto[]>(`/teams?game_id=${encodeURIComponent(gameId)}`);
}

export function getWorkspace(teamId: string): Promise<TeamWorkspaceDto> {
  return request<TeamWorkspaceDto>(`/teams/${encodeURIComponent(teamId)}/workspace`);
}

export function updateSlotCode(payload: {
  team_id: string;
  slot_key: string;
  actor_user_id: string;
  code: string;
}): Promise<TeamDto> {
  return request<TeamDto>(`/teams/${encodeURIComponent(payload.team_id)}/slots/${encodeURIComponent(payload.slot_key)}`, {
    method: 'PUT',
    body: JSON.stringify({
      actor_user_id: payload.actor_user_id,
      code: payload.code,
    }),
  });
}

export function createRun(payload: {
  team_id: string;
  game_id: string;
  requested_by: string;
  run_kind: 'single_task' | 'training_match' | 'competition_match';
  lobby_id?: string | null;
}): Promise<RunDto> {
  return request<RunDto>('/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function startSingleTaskRun(payload: {
  game_id: string;
  team_id: string;
  requested_by: string;
}): Promise<RunDto> {
  return request<RunDto>(`/single-tasks/${encodeURIComponent(payload.game_id)}/run`, {
    method: 'POST',
    body: JSON.stringify({
      team_id: payload.team_id,
      requested_by: payload.requested_by,
    }),
  });
}

export function stopSingleTaskRun(payload: {
  game_id: string;
  run_id: string;
}): Promise<RunDto> {
  return request<RunDto>(`/single-tasks/${encodeURIComponent(payload.game_id)}/stop`, {
    method: 'POST',
    body: JSON.stringify({ run_id: payload.run_id }),
  });
}

export function listSingleTaskAttempts(payload: {
  game_id: string;
  requested_by?: string;
  status?: 'created' | 'queued' | 'running' | 'finished' | 'failed' | 'timeout' | 'canceled';
  limit?: number;
  offset?: number;
}): Promise<RunDto[]> {
  const query = new URLSearchParams();
  if (payload.requested_by) query.set('requested_by', payload.requested_by);
  if (payload.status) query.set('status', payload.status);
  if (typeof payload.limit === 'number') query.set('limit', String(payload.limit));
  if (typeof payload.offset === 'number') query.set('offset', String(payload.offset));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<RunDto[]>(`/single-tasks/${encodeURIComponent(payload.game_id)}/attempts${suffix}`);
}

export function getSingleTaskAttempt(attemptId: string): Promise<RunDto> {
  return request<RunDto>(`/single-task-attempts/${encodeURIComponent(attemptId)}`);
}

export function getSingleTaskAttemptLogs(attemptId: string): Promise<SingleTaskAttemptLogsDto> {
  return request<SingleTaskAttemptLogsDto>(`/single-task-attempts/${encodeURIComponent(attemptId)}/logs`);
}

export function queueRun(runId: string): Promise<RunDto> {
  return request<RunDto>(`/runs/${encodeURIComponent(runId)}/queue`, {
    method: 'POST',
  });
}

export function getRun(runId: string): Promise<RunDto> {
  return request<RunDto>(`/runs/${encodeURIComponent(runId)}`);
}

export function getRunWatchContext(runId: string): Promise<RunWatchContextDto> {
  return request<RunWatchContextDto>(`/runs/${encodeURIComponent(runId)}/watch-context`);
}

export function getRunReplay(runId: string): Promise<ReplayDto> {
  return request<ReplayDto>(`/replays/runs/${encodeURIComponent(runId)}`);
}

export function listReplays(filters: {
  game_id?: string;
  run_kind?: 'single_task' | 'training_match' | 'competition_match';
  limit?: number;
} = {}): Promise<ReplayDto[]> {
  const query = new URLSearchParams();
  if (filters.game_id) query.set('game_id', filters.game_id);
  if (filters.run_kind) query.set('run_kind', filters.run_kind);
  if (typeof filters.limit === 'number') query.set('limit', String(filters.limit));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<ReplayDto[]>(`/replays${suffix}`);
}

export function listRuns(filters: {
  team_id?: string;
  game_id?: string;
  lobby_id?: string;
  run_kind?: 'single_task' | 'training_match' | 'competition_match';
  status?: 'created' | 'queued' | 'running' | 'finished' | 'failed' | 'timeout' | 'canceled';
} = {}): Promise<RunDto[]> {
  const query = new URLSearchParams();
  if (filters.team_id) query.set('team_id', filters.team_id);
  if (filters.game_id) query.set('game_id', filters.game_id);
  if (filters.lobby_id) query.set('lobby_id', filters.lobby_id);
  if (filters.run_kind) query.set('run_kind', filters.run_kind);
  if (filters.status) query.set('status', filters.status);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<RunDto[]>(`/runs${suffix}`);
}

export function cancelRun(runId: string): Promise<RunDto> {
  return request<RunDto>(`/runs/${encodeURIComponent(runId)}/cancel`, {
    method: 'POST',
  });
}

export function listLobbies(): Promise<LobbyDto[]> {
  return request<LobbyDto[]>('/lobbies');
}

export function getLobby(lobbyId: string): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(lobbyId)}`);
}

export function joinLobbyAsUser(payload: {
  lobby_id: string;
  access_code?: string | null;
}): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(payload.lobby_id)}/join`, {
    method: 'POST',
    body: JSON.stringify({ access_code: payload.access_code ?? null }),
  });
}

export function playLobby(payload: {
  lobby_id: string;
  access_code?: string | null;
}): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(payload.lobby_id)}/play`, {
    method: 'POST',
    body: JSON.stringify({ access_code: payload.access_code ?? null }),
  });
}

export function stopLobby(lobbyId: string): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(lobbyId)}/stop`, {
    method: 'POST',
  });
}

export function getLobbyCurrentRun(lobbyId: string): Promise<LobbyCurrentRunDto> {
  return request<LobbyCurrentRunDto>(`/lobbies/${encodeURIComponent(lobbyId)}/current-run`);
}

export function createLobby(payload: {
  game_id: string;
  title: string;
  kind: LobbyKind;
  access: LobbyAccess;
  access_code?: string | null;
  max_teams: number;
}): Promise<LobbyDto> {
  return request<LobbyDto>('/lobbies', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function joinLobby(payload: {
  lobby_id: string;
  team_id: string;
  access_code?: string | null;
}): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(payload.lobby_id)}/teams/${encodeURIComponent(payload.team_id)}/join`, {
    method: 'POST',
    body: JSON.stringify({
      access_code: payload.access_code ?? null,
    }),
  });
}

export function leaveLobby(payload: {
  lobby_id: string;
  team_id: string;
}): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(payload.lobby_id)}/teams/${encodeURIComponent(payload.team_id)}/leave`, {
    method: 'POST',
  });
}

export function setLobbyReady(payload: {
  lobby_id: string;
  team_id: string;
  ready: boolean;
}): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(payload.lobby_id)}/teams/${encodeURIComponent(payload.team_id)}/ready`, {
    method: 'POST',
    body: JSON.stringify({ ready: payload.ready }),
  });
}

export function setLobbyStatus(payload: {
  lobby_id: string;
  status: Extract<LobbyStatus, 'open' | 'paused' | 'closed'>;
}): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(payload.lobby_id)}/status`, {
    method: 'POST',
    body: JSON.stringify({ status: payload.status }),
  });
}

export function runLobbyMatchmakingTick(payload: {
  lobby_id: string;
  requested_by: string;
}): Promise<LobbyDto> {
  return request<LobbyDto>(`/lobbies/${encodeURIComponent(payload.lobby_id)}/matchmaking/tick`, {
    method: 'POST',
    body: JSON.stringify({ requested_by: payload.requested_by }),
  });
}

export function startLobbyCompetition(payload: {
  lobby_id: string;
  title: string;
  format?: CompetitionFormat;
  tie_break_policy?: TieBreakPolicy;
  code_policy?: CompetitionCodePolicy;
  advancement_top_k?: number;
  match_size?: number;
}): Promise<LobbyCompetitionDto> {
  return request<LobbyCompetitionDto>(`/lobbies/${encodeURIComponent(payload.lobby_id)}/competitions/start`, {
    method: 'POST',
    body: JSON.stringify({
      title: payload.title,
      format: payload.format ?? 'single_elimination',
      tie_break_policy: payload.tie_break_policy ?? 'manual',
      code_policy: payload.code_policy ?? 'locked_on_start',
      advancement_top_k: payload.advancement_top_k ?? 1,
      match_size: payload.match_size ?? 2,
    }),
  });
}

export function finishLobbyCompetition(payload: {
  lobby_id: string;
  competition_id: string;
}): Promise<LobbyCompetitionDto> {
  return request<LobbyCompetitionDto>(
    `/lobbies/${encodeURIComponent(payload.lobby_id)}/competitions/${encodeURIComponent(payload.competition_id)}/finish`,
    { method: 'POST' }
  );
}

export function listLobbyCompetitionArchive(lobbyId: string): Promise<LobbyCompetitionArchiveDto> {
  return request<LobbyCompetitionArchiveDto>(`/lobbies/${encodeURIComponent(lobbyId)}/competitions/archive`);
}

export function listCompetitions(): Promise<CompetitionDto[]> {
  return request<CompetitionDto[]>('/competitions');
}

export function getCompetition(competitionId: string): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(competitionId)}`);
}

export function patchCompetition(payload: {
  competition_id: string;
  title?: string | null;
  tie_break_policy?: TieBreakPolicy | null;
  code_policy?: CompetitionCodePolicy | null;
  advancement_top_k?: number | null;
  match_size?: number | null;
}): Promise<CompetitionDto> {
  const body: Record<string, unknown> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.tie_break_policy !== undefined) body.tie_break_policy = payload.tie_break_policy;
  if (payload.code_policy !== undefined) body.code_policy = payload.code_policy;
  if (payload.advancement_top_k !== undefined) body.advancement_top_k = payload.advancement_top_k;
  if (payload.match_size !== undefined) body.match_size = payload.match_size;
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(payload.competition_id)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export function registerCompetitionTeam(payload: {
  competition_id: string;
  team_id: string;
}): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(payload.competition_id)}/register`, {
    method: 'POST',
    body: JSON.stringify({ team_id: payload.team_id }),
  });
}

export function unregisterCompetitionTeam(payload: {
  competition_id: string;
  team_id: string;
}): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(payload.competition_id)}/unregister`, {
    method: 'POST',
    body: JSON.stringify({ team_id: payload.team_id }),
  });
}

export function startCompetition(payload: {
  competition_id: string;
  requested_by: string;
}): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(payload.competition_id)}/start`, {
    method: 'POST',
    body: JSON.stringify({ requested_by: payload.requested_by }),
  });
}

export function advanceCompetition(payload: {
  competition_id: string;
  requested_by: string;
}): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(payload.competition_id)}/advance`, {
    method: 'POST',
    body: JSON.stringify({ requested_by: payload.requested_by }),
  });
}

export function resolveCompetitionMatchTie(payload: {
  competition_id: string;
  round_index: number;
  match_id: string;
  advanced_team_ids: string[];
}): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(payload.competition_id)}/matches/resolve`, {
    method: 'POST',
    body: JSON.stringify({
      round_index: payload.round_index,
      match_id: payload.match_id,
      advanced_team_ids: payload.advanced_team_ids,
    }),
  });
}

export function setCompetitionEntrantNotReady(payload: {
  competition_id: string;
  team_id: string;
  reason?: string;
}): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(payload.competition_id)}/moderation/not-ready`, {
    method: 'POST',
    body: JSON.stringify({
      team_id: payload.team_id,
      reason: payload.reason ?? null,
    }),
  });
}

export function setCompetitionEntrantBan(payload: {
  competition_id: string;
  team_id: string;
  banned: boolean;
  reason?: string;
}): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(payload.competition_id)}/moderation/ban`, {
    method: 'POST',
    body: JSON.stringify({
      team_id: payload.team_id,
      banned: payload.banned,
      reason: payload.reason ?? null,
    }),
  });
}

export function pauseCompetition(competitionId: string): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(competitionId)}/pause`, {
    method: 'POST',
  });
}

export function finishCompetition(competitionId: string): Promise<CompetitionDto> {
  return request<CompetitionDto>(`/competitions/${encodeURIComponent(competitionId)}/finish`, {
    method: 'POST',
  });
}

export function listCompetitionRuns(competitionId: string): Promise<CompetitionRunItemDto[]> {
  return request<CompetitionRunItemDto[]>(`/competitions/${encodeURIComponent(competitionId)}/runs`);
}

export function getCompetitionBracket(competitionId: string): Promise<CompetitionRoundDto[]> {
  return request<CompetitionRoundDto[]>(`/competitions/${encodeURIComponent(competitionId)}/bracket`);
}

export function getCompetitionRounds(competitionId: string): Promise<CompetitionRoundDto[]> {
  return request<CompetitionRoundDto[]>(`/competitions/${encodeURIComponent(competitionId)}/rounds`);
}

export function getCompetitionMatches(competitionId: string): Promise<CompetitionMatchDto[]> {
  return request<CompetitionMatchDto[]>(`/competitions/${encodeURIComponent(competitionId)}/matches`);
}

export function checkCompetitionAntiplagiarism(payload: {
  competition_id: string;
  similarity_threshold?: number;
  min_token_count?: number;
}): Promise<AntiplagiarismWarningDto[]> {
  const query = new URLSearchParams();
  if (typeof payload.similarity_threshold === 'number') {
    query.set('similarity_threshold', String(payload.similarity_threshold));
  }
  if (typeof payload.min_token_count === 'number') {
    query.set('min_token_count', String(payload.min_token_count));
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return request<AntiplagiarismWarningDto[]>(
    `/competitions/${encodeURIComponent(payload.competition_id)}/antiplagiarism/warnings${suffix}`
  );
}
