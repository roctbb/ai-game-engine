from __future__ import annotations

from typing import Protocol
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

from execution.application.service import CreateRunInput, ExecutionService
from execution.domain.model import Run, RunKind, RunStatus
from game_catalog.application.service import GameCatalogService
from game_catalog.domain.model import CatalogMetadataStatus
from team_workspace.application.service import TeamWorkspaceService
from training_lobby.application.repositories import LobbyRepository
from training_lobby.domain.model import Lobby, LobbyAccess, LobbyKind, LobbyStatus
from shared.config.settings import settings
from shared.kernel import ExternalServiceError, InvariantViolationError, NotFoundError, utc_now


@dataclass(slots=True)
class CreateLobbyInput:
    game_id: str
    title: str
    kind: LobbyKind
    access: LobbyAccess
    access_code: str | None
    max_teams: int


_ACTIVE_RUN_STATUSES = {RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING}
_TERMINAL_RUN_STATUSES = {RunStatus.FINISHED, RunStatus.FAILED, RunStatus.TIMEOUT, RunStatus.CANCELED}
_REPLAYABLE_RUN_STATUSES = {RunStatus.FINISHED}
_LOBBY_REPLAY_FRAME_MS = 500
_LOBBY_RESULT_SECONDS = 5
_LOBBY_ONLINE_VIEWER_TTL_SECONDS = 20
_LOBBY_LIVE_CACHE_TTL_SECONDS = 0.75
_TRAINING_LOBBY_ARCHIVED_MATCH_LIMIT = 30
_LOBBY_VIEWER_PRESENCE_KEY_PREFIX = "ai-game:training-lobby:viewer-presence:"


class _DistributedLock(Protocol):
    def acquire(self, blocking: bool = True) -> bool:
        ...

    def release(self) -> None:
        ...


class _DistributedLockClient(Protocol):
    def lock(
        self,
        name: str,
        timeout: float | None = None,
        blocking_timeout: float | None = None,
    ) -> _DistributedLock:
        ...


def _can_change_participation(lobby: Lobby) -> bool:
    if lobby.status in {LobbyStatus.OPEN, LobbyStatus.DRAFT}:
        return True
    return lobby.kind is LobbyKind.TRAINING and lobby.status is LobbyStatus.RUNNING


def _partition_match_groups(
    *,
    ready_team_ids: list[str],
    min_players: int,
    max_players: int,
) -> list[list[str]]:
    team_count = len(ready_team_ids)
    if team_count < min_players:
        return []

    for scheduled_count in range(team_count, min_players - 1, -1):
        min_group_count = (scheduled_count + max_players - 1) // max_players
        max_group_count = scheduled_count // min_players
        for group_count in range(min_group_count, max_group_count + 1):
            if group_count * min_players <= scheduled_count <= group_count * max_players:
                sizes = _distribute_match_sizes(
                    total=scheduled_count,
                    group_count=group_count,
                    min_players=min_players,
                    max_players=max_players,
                )
                groups: list[list[str]] = []
                cursor = 0
                for size in sizes:
                    groups.append(ready_team_ids[cursor : cursor + size])
                    cursor += size
                return groups
    return []


def _distribute_match_sizes(
    *,
    total: int,
    group_count: int,
    min_players: int,
    max_players: int,
) -> list[int]:
    sizes = [min_players for _ in range(group_count)]
    remaining = total - group_count * min_players
    index = 0
    while remaining > 0:
        capacity = max_players - sizes[index]
        delta = min(capacity, remaining)
        sizes[index] += delta
        remaining -= delta
        index = (index + 1) % group_count
    return sizes


def _datetime_or_none(value: object | None) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=utc_now().tzinfo)
    return value


@dataclass(frozen=True, slots=True)
class LobbyParticipantStats:
    team_id: str
    captain_user_id: str
    display_name: str
    matches_total: int
    wins: int
    average_score: float | None


@dataclass(frozen=True, slots=True)
class LobbyMatchGroupView:
    group_id: str
    batch_id: str
    run_ids: tuple[str, ...]
    team_ids: tuple[str, ...]
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    replay_frame_count: int
    replay_frame_index: int
    winner_team_ids: tuple[str, ...]
    scores_by_team: dict[str, float]


@dataclass(frozen=True, slots=True)
class _LobbyCycleState:
    phase: str
    phase_label: str
    message: str
    started_at: datetime | None
    replay_started_at: datetime | None
    replay_until: datetime | None
    result_until: datetime | None
    replay_frame_index: int
    replay_frame_count: int
    winner_team_ids: tuple[str, ...]
    current_match_groups: tuple[LobbyMatchGroupView, ...]


@dataclass(frozen=True, slots=True)
class _CachedLobbyLiveState:
    expires_at: datetime
    lobby_signature: object
    runs: tuple[Run, ...]
    active_runs: tuple[Run, ...]
    cycle: _LobbyCycleState


@dataclass(frozen=True, slots=True)
class LobbyLiveView:
    lobby: Lobby
    my_team_id: str | None
    my_status: str
    current_run_id: str | None
    playing_team_ids: tuple[str, ...]
    queued_team_ids: tuple[str, ...]
    preparing_team_ids: tuple[str, ...]
    current_run_ids: tuple[str, ...]
    archived_run_ids: tuple[str, ...]
    participant_stats: tuple[LobbyParticipantStats, ...]
    cycle_phase: str
    cycle_phase_label: str
    cycle_message: str
    cycle_started_at: datetime | None
    replay_started_at: datetime | None
    replay_until: datetime | None
    result_until: datetime | None
    cycle_frame_ms: int
    cycle_replay_frame_index: int
    cycle_replay_frame_count: int
    cycle_winner_team_ids: tuple[str, ...]
    current_match_groups: tuple[LobbyMatchGroupView, ...]
    archived_match_groups: tuple[LobbyMatchGroupView, ...]


class TrainingLobbyService:
    def __init__(
        self,
        repository: LobbyRepository,
        game_catalog: GameCatalogService,
        team_workspace: TeamWorkspaceService,
        execution: ExecutionService,
        matchmaking_lock_client: _DistributedLockClient | None = None,
    ) -> None:
        self._repository = repository
        self._game_catalog = game_catalog
        self._team_workspace = team_workspace
        self._execution = execution
        self._matchmaking_lock_client = matchmaking_lock_client
        self._matchmaking_locks: dict[str, Lock] = {}
        self._participant_stats_cache: dict[
            str,
            tuple[object, tuple[LobbyParticipantStats, ...]],
        ] = {}
        self._archived_match_groups_cache: dict[
            str,
            tuple[object, tuple[LobbyMatchGroupView, ...]],
        ] = {}
        self._finished_runs_payload_cache: dict[str, tuple[object, list[Run]]] = {}
        self._live_state_cache: dict[str, _CachedLobbyLiveState] = {}
        self._viewer_last_seen_by_lobby: dict[str, dict[str, datetime]] = {}

    def create_lobby(self, data: CreateLobbyInput) -> Lobby:
        game = self._game_catalog.get_game(data.game_id)
        if not game.is_multiplayer:
            raise InvariantViolationError("Лобби можно создать только для игры, а не для задачи")
        if game.catalog_metadata_status is not CatalogMetadataStatus.READY:
            raise InvariantViolationError("Лобби можно создать только для опубликованной игры")
        lobby = Lobby.create(
            game_id=game.game_id,
            game_version_id=game.active_version.version_id,
            title=data.title,
            kind=data.kind,
            access=data.access,
            access_code=data.access_code,
            max_teams=data.max_teams,
        )
        self._repository.save(lobby)
        return lobby

    def list_lobbies(self) -> list[Lobby]:
        return self._repository.list()

    def get_lobby(self, lobby_id: str) -> Lobby:
        lobby = self._repository.get(lobby_id)
        if lobby is None:
            raise NotFoundError(f"Лобби {lobby_id} не найдено")
        return lobby

    def find_user_team_in_lobby(self, lobby_id: str, user_id: str) -> str | None:
        lobby = self.get_lobby(lobby_id)
        game_teams = self._team_workspace.list_teams_by_game_and_captain(
            game_id=lobby.game_id,
            captain_user_id=user_id,
        )
        team_ids = {team.team_id for team in game_teams}
        for team_id in lobby.teams:
            if team_id in team_ids:
                return team_id
        return None

    def mark_viewer_online(self, lobby_id: str, user_id: str) -> None:
        now = utc_now()
        if self._mark_viewer_online_in_redis(lobby_id=lobby_id, user_id=user_id, now=now):
            return
        viewers = self._viewer_last_seen_by_lobby.setdefault(lobby_id, {})
        viewers[user_id] = now
        self._prune_online_viewers(lobby_id=lobby_id, now=now)

    def ensure_user_joined(self, lobby_id: str, user_id: str, access_code: str | None, *, bypass_access_code: bool = False) -> tuple[Lobby, str]:
        lobby = self.get_lobby(lobby_id)
        existing_team_id = self.find_user_team_in_lobby(lobby_id=lobby_id, user_id=user_id)
        if existing_team_id is not None:
            return lobby, existing_team_id
        if not _can_change_participation(lobby):
            raise InvariantViolationError("В текущем статусе нельзя присоединиться к лобби")
        if len(lobby.teams) >= lobby.max_teams:
            raise InvariantViolationError("Лобби заполнено")
        if not bypass_access_code and lobby.access == LobbyAccess.CODE and lobby.access_code != access_code:
            raise InvariantViolationError("Неверный код доступа к лобби")
        team = self._team_workspace.get_or_create_personal_team(game_id=lobby.game_id, captain_user_id=user_id)
        lobby.join_team(team_id=team.team_id, access_code=access_code, bypass_access_code=bypass_access_code)
        self._repository.save(lobby)
        return lobby, team.team_id

    def set_ready_for_user(self, lobby_id: str, user_id: str, ready: bool) -> Lobby:
        team_id = self.find_user_team_in_lobby(lobby_id=lobby_id, user_id=user_id)
        if team_id is None:
            raise NotFoundError("Пользователь не состоит в лобби")
        return self.set_ready(lobby_id=lobby_id, team_id=team_id, ready=ready)

    def stop_for_user(self, lobby_id: str, user_id: str) -> Lobby:
        team_id = self.find_user_team_in_lobby(lobby_id=lobby_id, user_id=user_id)
        if team_id is None:
            raise NotFoundError("Пользователь не состоит в лобби")
        lobby = self.get_lobby(lobby_id)
        if lobby.status not in {LobbyStatus.OPEN, LobbyStatus.RUNNING, LobbyStatus.DRAFT}:
            raise InvariantViolationError("В текущем статусе нельзя нажать Stop")
        canceled_run_ids = self._cancel_active_training_runs_for_team(
            lobby=lobby,
            team_id=team_id,
            message="manual_stop_lobby",
        )
        if team_id in lobby.teams and lobby.teams[team_id].ready:
            lobby.mark_ready(team_id=team_id, ready=False)
        if canceled_run_ids:
            self._remove_canceled_groups_from_lobby(lobby=lobby, canceled_run_ids=canceled_run_ids)
            self._clear_lobby_derived_caches(lobby_id)
            self._repository.save(lobby)
        elif team_id in lobby.teams:
            self._repository.save(lobby)
        lobby = self.reconcile_training_lobby_status(lobby_id=lobby_id)
        return lobby

    def get_live_view(self, lobby_id: str, user_id: str) -> LobbyLiveView:
        lobby = self.get_lobby(lobby_id)
        runs, active_runs, cycle = self._get_cached_lobby_live_state(lobby)
        my_team_id = self.find_user_team_in_lobby(lobby_id=lobby_id, user_id=user_id)
        current_group_run_ids = {
            run_id
            for group in cycle.current_match_groups
            for run_id in group.run_ids
        }
        current_group_team_ids = {
            team_id
            for group in cycle.current_match_groups
            for team_id in group.team_ids
        }
        playing_team_ids_set = {run.team_id for run in active_runs if run.status is RunStatus.RUNNING}
        if cycle.phase in {"simulation", "replay", "result"}:
            playing_team_ids_set.update(current_group_team_ids)
        playing_team_ids = tuple(sorted(playing_team_ids_set))
        queued_team_ids = set(
            run.team_id for run in active_runs if run.status in {RunStatus.CREATED, RunStatus.QUEUED}
        )
        queued_team_ids.update(
            team_id
            for team_id, team_state in lobby.teams.items()
            if team_state.ready and team_id not in playing_team_ids
        )
        queued_team_ids_tuple = tuple(sorted(queued_team_ids))

        current_run_id = None
        if my_team_id is not None:
            for run in sorted(runs, key=lambda item: item.created_at, reverse=True):
                if run.run_id not in current_group_run_ids and run.status not in _ACTIVE_RUN_STATUSES:
                    continue
                if run.team_id == my_team_id:
                    current_run_id = run.run_id
                    break

        preparing_team_ids: list[str] = []
        for team_id, team_state in lobby.teams.items():
            if team_id in playing_team_ids or team_id in queued_team_ids_tuple:
                continue
            preparing_team_ids.append(team_id)
        preparing_team_ids = sorted(set(preparing_team_ids))

        my_status = "not_in_lobby"
        if my_team_id is not None:
            if my_team_id in playing_team_ids:
                my_status = "playing"
            elif my_team_id in queued_team_ids_tuple:
                my_status = "queued"
            else:
                my_status = "preparing"

        finished_runs = [
            run
            for run in runs
            if run.status in _REPLAYABLE_RUN_STATUSES
        ]
        finished_runs.sort(key=lambda item: item.created_at, reverse=True)
        archived_run_ids = tuple(run.run_id for run in finished_runs if run.run_id not in current_group_run_ids)[
            : _TRAINING_LOBBY_ARCHIVED_MATCH_LIMIT * 8
        ]
        current_run_ids = tuple(
            run_id
            for group in cycle.current_match_groups
            for run_id in group.run_ids
        ) or tuple(run.run_id for run in sorted(active_runs, key=lambda item: item.created_at, reverse=True))
        participant_stats = self._collect_participant_stats_cached(lobby=lobby, runs=finished_runs)
        archived_match_groups = self._build_archived_match_group_views_cached(
            lobby=lobby,
            runs=[run for run in finished_runs if run.run_id not in current_group_run_ids],
            limit=_TRAINING_LOBBY_ARCHIVED_MATCH_LIMIT,
        )

        return LobbyLiveView(
            lobby=lobby,
            my_team_id=my_team_id,
            my_status=my_status,
            current_run_id=current_run_id,
            playing_team_ids=playing_team_ids,
            queued_team_ids=queued_team_ids_tuple,
            preparing_team_ids=tuple(preparing_team_ids),
            current_run_ids=current_run_ids,
            archived_run_ids=archived_run_ids,
            participant_stats=participant_stats,
            cycle_phase=cycle.phase,
            cycle_phase_label=cycle.phase_label,
            cycle_message=cycle.message,
            cycle_started_at=cycle.started_at,
            replay_started_at=cycle.replay_started_at,
            replay_until=cycle.replay_until,
            result_until=cycle.result_until,
            cycle_frame_ms=_LOBBY_REPLAY_FRAME_MS,
            cycle_replay_frame_index=cycle.replay_frame_index,
            cycle_replay_frame_count=cycle.replay_frame_count,
            cycle_winner_team_ids=cycle.winner_team_ids,
            current_match_groups=cycle.current_match_groups,
            archived_match_groups=archived_match_groups,
        )

    def join_team(
        self,
        lobby_id: str,
        team_id: str,
        access_code: str | None,
        *,
        bypass_access_code: bool = False,
    ) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        team = self._team_workspace.get_team(team_id)

        if team.game_id != lobby.game_id:
            raise InvariantViolationError("Команда может вступать только в лобби своей игры")
        for existing_team_id in lobby.teams:
            existing_team = self._team_workspace.get_team(existing_team_id)
            if existing_team.captain_user_id == team.captain_user_id:
                if existing_team.team_id == team.team_id:
                    return lobby
                raise InvariantViolationError("У пользователя уже есть игрок в этом лобби")

        lobby.join_team(team_id=team_id, access_code=access_code, bypass_access_code=bypass_access_code)
        self._repository.save(lobby)
        return lobby

    def leave_team(self, lobby_id: str, team_id: str) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        self._ensure_team_can_leave(lobby=lobby, team_id=team_id)
        canceled_run_ids = self._cancel_active_training_runs_for_team(
            lobby=lobby,
            team_id=team_id,
            message="team_left_lobby",
        )
        lobby.leave_team(team_id)
        if canceled_run_ids:
            self._remove_canceled_groups_from_lobby(lobby=lobby, canceled_run_ids=canceled_run_ids)
            self._clear_lobby_derived_caches(lobby_id)
        self._repository.save(lobby)
        return lobby

    def _ensure_team_can_leave(self, *, lobby: Lobby, team_id: str) -> None:
        if team_id not in lobby.teams:
            raise NotFoundError("Команда не состоит в лобби")
        if lobby.kind == LobbyKind.COMPETITION and lobby.status == LobbyStatus.RUNNING:
            raise InvariantViolationError("Во время соревнования выход запрещен")

    def set_ready(self, lobby_id: str, team_id: str, ready: bool) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        if not _can_change_participation(lobby):
            raise InvariantViolationError("В текущем статусе нельзя менять ready-состояние")
        if ready:
            compatibility = self._team_workspace.evaluate_compatibility(
                team_id=team_id,
                game_id=lobby.game_id,
                version_id=lobby.game_version_id,
            )
            if not compatibility.compatible:
                reason = (
                    "Команда не готова: не заполнены обязательные слоты "
                    + ", ".join(compatibility.missing_required_slots)
                )
                lobby.mark_ready(team_id=team_id, ready=False, blocker_reason=reason)
                self._repository.save(lobby)
                raise InvariantViolationError(reason)

        lobby.mark_ready(team_id=team_id, ready=ready)
        self._repository.save(lobby)
        return lobby

    def set_status(self, lobby_id: str, status: LobbyStatus) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        if status == LobbyStatus.PAUSED:
            lobby.pause()
        elif status == LobbyStatus.OPEN:
            lobby.reopen()
            self._prepare_reopened_lobby(lobby)
        elif status == LobbyStatus.STOPPED:
            self._cancel_active_training_runs(lobby_id=lobby_id, message="lobby_stopped")
            lobby.stop()
        elif status == LobbyStatus.CLOSED:
            self._cancel_active_training_runs(lobby_id=lobby_id, message="lobby_closed")
            lobby.close()
        else:
            raise InvariantViolationError("Разрешены только статусы open, paused, stopped и closed")
        self._repository.save(lobby)
        return lobby

    def _prepare_reopened_lobby(self, lobby: Lobby) -> None:
        compatibility_by_team: dict[str, tuple[bool, str | None]] = {}
        demo_bot_team_ids: set[str] = set()
        for team_id in lobby.teams:
            try:
                team = self._team_workspace.get_team(team_id)
                compatibility = self._team_workspace.evaluate_compatibility(
                    team_id=team_id,
                    game_id=lobby.game_id,
                    version_id=lobby.game_version_id,
                )
            except NotFoundError:
                compatibility_by_team[team_id] = (False, "Команда не найдена")
                continue

            if team.captain_user_id.startswith("bot:"):
                demo_bot_team_ids.add(team_id)
            if compatibility.compatible:
                compatibility_by_team[team_id] = (True, None)
            else:
                reason = "Не заполнены обязательные слоты: " + ", ".join(compatibility.missing_required_slots)
                compatibility_by_team[team_id] = (False, reason)

        lobby.revalidate_ready_states(compatibility_by_team=compatibility_by_team)
        for team_id in demo_bot_team_ids:
            state = lobby.teams.get(team_id)
            compatible, _reason = compatibility_by_team.get(team_id, (False, None))
            if state is not None and compatible:
                state.ready = True
                state.blocker_reason = None

    def stop_current_training_games_for_competition(self, lobby_id: str) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        if lobby.kind is not LobbyKind.TRAINING:
            raise InvariantViolationError("Соревнование можно запускать только в training-лобби")
        self._cancel_active_training_runs(lobby_id=lobby_id, message="competition_started")
        lobby.set_last_scheduled_runs([])
        self._clear_lobby_derived_caches(lobby_id)
        self._repository.save(lobby)
        return lobby

    def update_lobby_settings(
        self,
        lobby_id: str,
        *,
        title: str | None = None,
        access: LobbyAccess | None = None,
        access_code: str | None = None,
        max_teams: int | None = None,
    ) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        lobby.update_settings(
            title=title,
            access=access,
            access_code=access_code,
            max_teams=max_teams,
        )
        self._repository.save(lobby)
        self.cleanup_training_match_archive(lobby_id=lobby_id)
        return lobby

    def delete_lobby(self, lobby_id: str) -> None:
        lobby = self.get_lobby(lobby_id)
        self._cancel_active_training_runs(lobby_id=lobby_id, message="lobby_deleted")
        self._execution.delete_lobby_runs(lobby_id=lobby.lobby_id, run_kind=RunKind.TRAINING_MATCH)
        self._viewer_last_seen_by_lobby.pop(lobby_id, None)
        self._clear_lobby_derived_caches(lobby_id)
        self._repository.delete(lobby_id)

    def cleanup_training_match_archive(self, lobby_id: str) -> list[str]:
        try:
            lobby = self.get_lobby(lobby_id)
        except NotFoundError:
            return []
        runs = self._execution.list_runs(
            lobby_id=lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        current_run_ids = {run_id for group in self._current_match_groups(lobby) for run_id in group}
        finished_runs = [
            run
            for run in runs
            if run.status in _REPLAYABLE_RUN_STATUSES and run.run_id not in current_run_ids
        ]
        if len(finished_runs) <= _TRAINING_LOBBY_ARCHIVED_MATCH_LIMIT:
            return []

        finished_runs_with_payload = self._finished_runs_with_payload_cached(lobby=lobby, runs=finished_runs)
        groups = self._archived_match_run_id_groups(lobby=lobby, runs=finished_runs_with_payload)
        groups_to_delete = groups[_TRAINING_LOBBY_ARCHIVED_MATCH_LIMIT:]
        if not groups_to_delete:
            return []

        runs_by_id = {run.run_id: run for run in finished_runs_with_payload}
        self._add_cumulative_stats_for_match_groups(lobby=lobby, groups=groups_to_delete, runs_by_id=runs_by_id)
        deleted = sorted({run_id for group in groups_to_delete for run_id in group})
        self._execution.delete_runs(deleted)
        self._repository.save(lobby)
        if deleted:
            self._clear_lobby_derived_caches(lobby_id)
        return deleted

    def _cancel_active_training_runs(self, lobby_id: str, message: str) -> None:
        runs = self._execution.list_runs(
            lobby_id=lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        for run in runs:
            if run.status in _ACTIVE_RUN_STATUSES:
                self._execution.cancel_run(run.run_id, message=message)

    def _cancel_active_training_runs_for_team(self, *, lobby: Lobby, team_id: str, message: str) -> set[str]:
        runs = self._execution.list_runs(
            lobby_id=lobby.lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        active_by_id = {run.run_id: run for run in runs if run.status in _ACTIVE_RUN_STATUSES}
        target_run_ids = {run.run_id for run in active_by_id.values() if run.team_id == team_id}
        if not target_run_ids:
            return set()

        current_groups = self._current_match_groups(lobby)
        group_run_ids = {
            run_id
            for group in current_groups
            if target_run_ids.intersection(group)
            for run_id in group
        }
        run_ids_to_cancel = group_run_ids or target_run_ids
        canceled: set[str] = set()
        for run_id in run_ids_to_cancel:
            run = active_by_id.get(run_id)
            if run is None:
                continue
            try:
                self._execution.cancel_run(run_id, message=message)
            except InvariantViolationError:
                continue
            canceled.add(run_id)
        return canceled

    @staticmethod
    def _remove_canceled_groups_from_lobby(*, lobby: Lobby, canceled_run_ids: set[str]) -> None:
        if not lobby.last_scheduled_match_groups:
            if set(lobby.last_scheduled_run_ids).intersection(canceled_run_ids):
                lobby.set_last_scheduled_runs([])
            return
        remaining_groups = [
            list(group)
            for group in lobby.last_scheduled_match_groups
            if not set(group).intersection(canceled_run_ids)
        ]
        lobby.set_last_scheduled_match_groups(remaining_groups)

    def reconcile_training_lobby_status(self, lobby_id: str) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        if lobby.kind is not LobbyKind.TRAINING:
            return lobby
        if lobby.status not in {LobbyStatus.OPEN, LobbyStatus.RUNNING}:
            return lobby

        runs = self._execution.list_runs(
            lobby_id=lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        active_runs = [run for run in runs if run.status in _ACTIVE_RUN_STATUSES]
        cycle = self._compute_cycle_state(lobby=lobby, runs=runs)
        if active_runs:
            lobby.set_running()
        elif cycle.phase in {"replay", "result"}:
            lobby.set_running()
        else:
            lobby.set_open()
            if lobby.last_scheduled_run_ids:
                lobby.set_last_scheduled_match_groups([])
        self._repository.save(lobby)
        self._clear_lobby_derived_caches(lobby_id)
        return lobby

    def run_matchmaking_cycle(self, lobby_id: str, requested_by: str) -> Lobby:
        lock = self._matchmaking_locks.setdefault(lobby_id, Lock())
        with lock:
            if self._matchmaking_lock_client is not None:
                return self._run_matchmaking_cycle_with_distributed_lock(
                    lobby_id=lobby_id,
                    requested_by=requested_by,
                )
            return self._run_matchmaking_cycle_locked(lobby_id=lobby_id, requested_by=requested_by)

    def _run_matchmaking_cycle_with_distributed_lock(self, lobby_id: str, requested_by: str) -> Lobby:
        distributed_lock = self._matchmaking_lock_client.lock(
            f"ai-game:training-lobby:{lobby_id}:matchmaking",
            timeout=max(settings.matchmaking_lock_ttl_seconds, 1.0),
            blocking_timeout=max(settings.matchmaking_lock_blocking_timeout_seconds, 0.1),
        )
        acquired = distributed_lock.acquire(blocking=True)
        if not acquired:
            raise InvariantViolationError("Matchmaking уже выполняется для этого лобби")
        try:
            return self._run_matchmaking_cycle_locked(lobby_id=lobby_id, requested_by=requested_by)
        finally:
            try:
                distributed_lock.release()
            except Exception:
                pass

    def run_due_matchmaking_cycles(self, requested_by: str = "system") -> tuple[Lobby, ...]:
        advanced: list[Lobby] = []
        for lobby in self._repository.list():
            if lobby.kind is not LobbyKind.TRAINING:
                continue
            if lobby.status not in {LobbyStatus.OPEN, LobbyStatus.RUNNING}:
                continue
            if not lobby.last_scheduled_run_ids and not any(state.ready for state in lobby.teams.values()):
                continue
            if not lobby.last_scheduled_run_ids and not self._has_online_ready_viewer(lobby):
                continue
            try:
                advanced.append(self.run_matchmaking_cycle(lobby_id=lobby.lobby_id, requested_by=requested_by))
            except InvariantViolationError:
                continue
        return tuple(advanced)

    def _run_matchmaking_cycle_locked(self, lobby_id: str, requested_by: str) -> Lobby:
        if requested_by != "system":
            self.mark_viewer_online(lobby_id=lobby_id, user_id=requested_by)
        lobby = self.get_lobby(lobby_id)
        if lobby.kind is not LobbyKind.TRAINING:
            raise InvariantViolationError("Matchmaking cycle доступен только для training лобби")
        if lobby.status in {LobbyStatus.PAUSED, LobbyStatus.STOPPED, LobbyStatus.UPDATING, LobbyStatus.CLOSED, LobbyStatus.DRAFT}:
            raise InvariantViolationError("В текущем статусе лобби матчмейкинг недоступен")

        game = self._game_catalog.get_game(lobby.game_id)
        runs = self._execution.list_runs(
            lobby_id=lobby.lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        active_runs = [run for run in runs if run.status in _ACTIVE_RUN_STATUSES]
        cycle = self._compute_cycle_state(lobby=lobby, runs=runs)
        busy_team_ids = {run.team_id for run in active_runs}
        if active_runs or cycle.phase in {"replay", "result"}:
            if active_runs:
                self._queue_recoverable_created_runs(lobby=lobby, active_runs=active_runs)
            lobby.set_running()
            self._repository.save(lobby)
            return lobby
        if lobby.last_scheduled_run_ids:
            lobby.set_last_scheduled_match_groups([])

        ready_team_ids = [
            state.team_id
            for state in lobby.teams.values()
            if state.ready
        ]
        ready_team_ids = [team_id for team_id in ready_team_ids if team_id not in busy_team_ids]

        scheduled_team_groups: list[list[str]] = []

        if game.is_multiplayer:
            min_players, max_players = game.match_player_bounds
            scheduled_team_groups = _partition_match_groups(
                ready_team_ids=ready_team_ids,
                min_players=min_players,
                max_players=max_players,
            )
        else:
            # single_task не должен работать через lobby matchmaking.
            raise InvariantViolationError("single_task игра не поддерживает lobby matchmaking")

        if scheduled_team_groups and not self._has_online_ready_viewer(lobby):
            lobby.set_open()
            self._repository.save(lobby)
            return lobby

        scheduled_run_ids: list[str] = []
        scheduled_match_groups: list[list[str]] = []
        for team_ids in scheduled_team_groups:
            group_run_ids = self._create_training_match_runs(
                lobby=lobby,
                team_ids=team_ids,
                requested_by=requested_by,
            )
            scheduled_match_groups.append(group_run_ids)
            scheduled_run_ids.extend(group_run_ids)

        if scheduled_run_ids:
            lobby.set_running()
            lobby.set_last_scheduled_match_groups(scheduled_match_groups)
            self._repository.save(lobby)
            self._queue_scheduled_match_groups(lobby=lobby, match_groups=scheduled_match_groups)
        else:
            if active_runs:
                lobby.set_running()
                self._repository.save(lobby)
                return lobby
            else:
                lobby.set_open()
                lobby.set_last_scheduled_match_groups([])
            self._repository.save(lobby)

        return lobby

    def _queue_scheduled_match_groups(self, *, lobby: Lobby, match_groups: list[list[str]]) -> None:
        run_ids = [run_id for group in match_groups for run_id in group]
        try:
            for group in match_groups:
                if not group:
                    continue
                self._execution.queue_match_group(group)
        except (ExternalServiceError, InvariantViolationError) as exc:
            self._cancel_unqueued_batch_runs(run_ids=run_ids, message=f"matchmaking_queue_failed: {exc}")
            lobby.set_last_scheduled_match_groups([])
            lobby.set_open()
            self._repository.save(lobby)
            raise InvariantViolationError("Не удалось поставить матчи лобби в очередь выполнения") from exc

    def _queue_recoverable_created_runs(self, *, lobby: Lobby, active_runs: list[Run]) -> None:
        current_run_ids = set(lobby.last_scheduled_run_ids)
        if not current_run_ids:
            return
        created_current_runs = [
            run
            for run in active_runs
            if run.run_id in current_run_ids and run.status is RunStatus.CREATED
        ]
        if not created_current_runs:
            return
        non_created_current_active = [
            run
            for run in active_runs
            if run.run_id in current_run_ids and run.status is not RunStatus.CREATED
        ]
        if non_created_current_active:
            return
        created_run_ids = {run.run_id for run in created_current_runs}
        match_groups = [
            [run_id for run_id in group if run_id in created_run_ids]
            for group in self._current_match_groups(lobby)
        ]
        self._queue_scheduled_match_groups(
            lobby=lobby,
            match_groups=[group for group in match_groups if group],
        )

    def finish_shadow_match_runs(self, primary_run: Run, payload: dict[str, object]) -> list[Run]:
        if primary_run.run_kind is not RunKind.TRAINING_MATCH or primary_run.lobby_id is None:
            return []
        shadow_runs = self._shadow_match_runs(primary_run)
        finished: list[Run] = []
        for shadow_run in shadow_runs:
            if shadow_run.status not in _ACTIVE_RUN_STATUSES:
                continue
            if not self._execution.is_shadow_of(shadow_run, primary_run.run_id):
                continue
            try:
                finished.append(self._execution.finish_run(shadow_run.run_id, _compact_shadow_payload(payload)))
            except InvariantViolationError:
                continue
        if finished:
            self._clear_lobby_derived_caches(primary_run.lobby_id)
        return finished

    def fail_shadow_match_runs(self, primary_run: Run, message: str) -> list[Run]:
        if primary_run.run_kind is not RunKind.TRAINING_MATCH or primary_run.lobby_id is None:
            return []
        shadow_runs = self._shadow_match_runs(primary_run)
        failed: list[Run] = []
        for shadow_run in shadow_runs:
            if shadow_run.status not in _ACTIVE_RUN_STATUSES:
                continue
            if not self._execution.is_shadow_of(shadow_run, primary_run.run_id):
                continue
            try:
                failed.append(self._execution.fail_run(shadow_run.run_id, message))
            except InvariantViolationError:
                continue
        if failed:
            self._clear_lobby_derived_caches(primary_run.lobby_id)
        return failed

    def cancel_shadow_match_runs(self, primary_run: Run, message: str) -> list[Run]:
        if primary_run.run_kind is not RunKind.TRAINING_MATCH or primary_run.lobby_id is None:
            return []
        shadow_runs = self._shadow_match_runs(primary_run)
        canceled: list[Run] = []
        for shadow_run in shadow_runs:
            if shadow_run.status not in _ACTIVE_RUN_STATUSES:
                continue
            if not self._execution.is_shadow_of(shadow_run, primary_run.run_id):
                continue
            try:
                canceled.append(self._execution.cancel_run(shadow_run.run_id, message=message))
            except InvariantViolationError:
                continue
        if canceled:
            self._clear_lobby_derived_caches(primary_run.lobby_id)
        return canceled

    def _shadow_match_runs(self, primary_run: Run) -> list[Run]:
        if primary_run.lobby_id is None:
            return []
        try:
            lobby = self.get_lobby(primary_run.lobby_id)
        except NotFoundError:
            return []
        group_run_ids: list[str] = []
        for group in lobby.last_scheduled_match_groups:
            if primary_run.run_id in group:
                group_run_ids = list(group)
                break
        if len(group_run_ids) <= 1:
            return []
        runs: list[Run] = []
        for run_id in group_run_ids:
            if run_id == primary_run.run_id:
                continue
            try:
                runs.append(self._execution.get_run(run_id))
            except NotFoundError:
                continue
        return runs

    def _cancel_unqueued_batch_runs(self, *, run_ids: list[str], message: str) -> None:
        for run_id in run_ids:
            try:
                run = self._execution.get_run(run_id)
            except NotFoundError:
                continue
            if run.status in _ACTIVE_RUN_STATUSES:
                try:
                    self._execution.cancel_run(run_id, message=message)
                except InvariantViolationError:
                    continue

    def switch_game_version(self, lobby_id: str, version_id: str) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        target_version = self._game_catalog.get_version(game_id=lobby.game_id, version_id=version_id)
        self._game_catalog.assert_compatible_slot_schema(
            game_id=lobby.game_id,
            current_version_id=lobby.game_version_id,
            target_version_id=target_version.version_id,
        )

        active_lobby_runs = self._execution.list_runs(
            lobby_id=lobby.lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        for run in active_lobby_runs:
            if run.status in _ACTIVE_RUN_STATUSES:
                self._execution.cancel_run(run.run_id, message="canceled_by_game_update")

        lobby.start_updating()
        lobby.set_game_version(target_version.version_id)

        compatibility: dict[str, tuple[bool, str | None]] = {}
        for team_id in lobby.teams:
            result = self._team_workspace.evaluate_compatibility(
                team_id=team_id,
                game_id=lobby.game_id,
                version_id=target_version.version_id,
            )
            if result.compatible:
                compatibility[team_id] = (True, None)
            else:
                compatibility[team_id] = (
                    False,
                    "Не заполнены обязательные слоты: " + ", ".join(result.missing_required_slots),
                )

        lobby.revalidate_ready_states(compatibility_by_team=compatibility)
        lobby.finish_updating()
        self._repository.save(lobby)
        return lobby

    def _create_training_match_runs(self, lobby: Lobby, team_ids: list[str], requested_by: str) -> list[str]:
        run_ids: list[str] = []
        for team_id in team_ids:
            run = self._execution.create_run(
                CreateRunInput(
                    team_id=team_id,
                    game_id=lobby.game_id,
                    requested_by=requested_by,
                    run_kind=RunKind.TRAINING_MATCH,
                    lobby_id=lobby.lobby_id,
                    version_id=lobby.game_version_id,
                )
            )
            run_ids.append(run.run_id)
        return run_ids

    def _compute_cycle_state(self, lobby: Lobby, runs: list[Run]) -> _LobbyCycleState:
        runs_by_id = {run.run_id: run for run in runs}
        groups = self._current_match_groups(lobby)
        current_match_groups: tuple[LobbyMatchGroupView, ...] = ()
        if groups:
            current_match_groups = tuple(
                self._build_match_group_view(
                    group_id=f"current-{index}",
                    batch_id=self._batch_id_for_groups(groups=groups, runs_by_id=runs_by_id),
                    run_ids=group,
                    runs_by_id=runs_by_id,
                    archived=False,
                    replay_started_at=None,
                    replay_frame_index=0,
                )
                for index, group in enumerate(groups)
            )

        current_run_ids = [run_id for group in groups for run_id in group]
        current_runs = [runs_by_id[run_id] for run_id in current_run_ids if run_id in runs_by_id]
        active_runs = [run for run in current_runs if run.status in _ACTIVE_RUN_STATUSES]
        if active_runs:
            started_at = min((_datetime_or_none(run.created_at) for run in active_runs), default=None)
            return _LobbyCycleState(
                phase="simulation",
                phase_label="Симуляция",
                message="Матчи выполняются параллельно.",
                started_at=started_at,
                replay_started_at=None,
                replay_until=None,
                result_until=None,
                replay_frame_index=0,
                replay_frame_count=max((group.replay_frame_count for group in current_match_groups), default=0),
                winner_team_ids=(),
                current_match_groups=current_match_groups,
            )

        if current_runs and all(run.status in _REPLAYABLE_RUN_STATUSES for run in current_runs):
            terminal_runs = [self._ensure_payload(run) for run in current_runs]
            replay_started_at = max(
                (_datetime_or_none(run.finished_at) for run in terminal_runs),
                default=None,
            )
            replay_frame_count = max((self._replay_frames_count(run) for run in terminal_runs), default=1)
            replay_seconds = max(1.0, replay_frame_count * _LOBBY_REPLAY_FRAME_MS / 1000)
            replay_until = replay_started_at + timedelta(seconds=replay_seconds) if replay_started_at else None
            result_until = replay_until + timedelta(seconds=_LOBBY_RESULT_SECONDS) if replay_until else None
            now = utc_now()
            if replay_started_at and replay_until and now < replay_until:
                frame_index = min(
                    replay_frame_count - 1,
                    max(0, int((now - replay_started_at).total_seconds() / (_LOBBY_REPLAY_FRAME_MS / 1000))),
                )
                current_match_groups = tuple(
                    self._build_match_group_view(
                        group_id=f"current-{index}",
                        batch_id=self._batch_id_for_groups(groups=groups, runs_by_id=runs_by_id),
                        run_ids=group,
                        runs_by_id={run.run_id: run for run in terminal_runs},
                        archived=False,
                        replay_started_at=replay_started_at,
                        replay_frame_index=frame_index,
                    )
                    for index, group in enumerate(groups)
                )
                return _LobbyCycleState(
                    phase="replay",
                    phase_label="Идет реплей",
                    message="Показываем матчи этого запуска, следующий цикл начнется после реплея.",
                    started_at=self._batch_started_at(groups=groups, runs_by_id=runs_by_id),
                    replay_started_at=replay_started_at,
                    replay_until=replay_until,
                    result_until=result_until,
                    replay_frame_index=frame_index,
                    replay_frame_count=replay_frame_count,
                    winner_team_ids=self._winner_team_ids_for_groups(
                        groups=groups,
                        runs_by_id={run.run_id: run for run in terminal_runs},
                    ),
                    current_match_groups=current_match_groups,
                )
            if result_until and now < result_until:
                terminal_runs_by_id = {run.run_id: run for run in terminal_runs}
                winner_team_ids = self._winner_team_ids_for_groups(groups=groups, runs_by_id=terminal_runs_by_id)
                return _LobbyCycleState(
                    phase="result",
                    phase_label="Результат",
                    message="Победитель: " + (", ".join(self._team_label(team_id) for team_id in winner_team_ids) if winner_team_ids else "не определен"),
                    started_at=self._batch_started_at(groups=groups, runs_by_id=runs_by_id),
                    replay_started_at=replay_started_at,
                    replay_until=replay_until,
                    result_until=result_until,
                    replay_frame_index=max(0, replay_frame_count - 1),
                    replay_frame_count=replay_frame_count,
                    winner_team_ids=winner_team_ids,
                    current_match_groups=current_match_groups,
                )

        ready_count = sum(1 for state in lobby.teams.values() if state.ready)
        min_players = 2
        try:
            game = self._game_catalog.get_game(lobby.game_id)
            if game.is_multiplayer:
                min_players = game.match_player_bounds[0]
        except (NotFoundError, InvariantViolationError):
            pass
        if ready_count < min_players:
            return _LobbyCycleState(
                phase="waiting_players",
                phase_label="Ожидание игроков",
                message=f"Нужно минимум {min_players} готовых игроков для следующего матча.",
                started_at=None,
                replay_started_at=None,
                replay_until=None,
                result_until=None,
                replay_frame_index=0,
                replay_frame_count=0,
                winner_team_ids=(),
                current_match_groups=(),
            )
        if not self._has_online_ready_viewer(lobby):
            return _LobbyCycleState(
                phase="waiting_viewer",
                phase_label="Ожидание зрителя",
                message="Ждем хотя бы одного готового игрока онлайн, чтобы показать матч.",
                started_at=None,
                replay_started_at=None,
                replay_until=None,
                result_until=None,
                replay_frame_index=0,
                replay_frame_count=0,
                winner_team_ids=(),
                current_match_groups=(),
            )
        return _LobbyCycleState(
            phase="waiting_players",
            phase_label="Ожидание игроков",
            message="Готовим следующий запуск.",
            started_at=None,
            replay_started_at=None,
            replay_until=None,
            result_until=None,
            replay_frame_index=0,
            replay_frame_count=0,
            winner_team_ids=(),
            current_match_groups=(),
        )

    def _current_match_groups(self, lobby: Lobby) -> list[list[str]]:
        if lobby.last_scheduled_match_groups:
            return [list(group) for group in lobby.last_scheduled_match_groups if group]
        if lobby.last_scheduled_run_ids:
            return [list(lobby.last_scheduled_run_ids)]
        return []

    def _archived_match_run_id_groups(self, *, lobby: Lobby, runs: list[Run]) -> list[list[str]]:
        if not runs:
            return []
        game = self._game_catalog.get_game(lobby.game_id)
        max_players = game.match_player_bounds[1] if game.is_multiplayer else 2
        min_datetime = datetime.min.replace(tzinfo=utc_now().tzinfo)
        sorted_runs = sorted(runs, key=lambda run: _datetime_or_none(run.created_at) or min_datetime, reverse=True)
        signature_groups = self._archived_signature_match_run_id_groups(sorted_runs=sorted_runs, max_players=max_players)
        if signature_groups is not None:
            unsigned_runs = [run for run in sorted_runs if self._payload_team_signature(run) is None]
            groups = signature_groups + self._archived_time_match_run_id_groups(
                sorted_runs=unsigned_runs,
                max_players=max_players,
            )
            runs_by_id = {run.run_id: run for run in sorted_runs}
            return sorted(
                groups,
                key=lambda group: self._batch_started_at(groups=[group], runs_by_id=runs_by_id) or min_datetime,
                reverse=True,
            )

        return self._archived_time_match_run_id_groups(sorted_runs=sorted_runs, max_players=max_players)

    def _archived_signature_match_run_id_groups(self, *, sorted_runs: list[Run], max_players: int) -> list[list[str]] | None:
        close_seconds = 2.0
        buckets_by_signature: dict[tuple[str, ...], list[list[Run]]] = {}
        groups: list[list[Run]] = []
        expected_size_by_group: dict[int, int] = {}
        saw_signature = False
        for run in sorted_runs:
            signature = self._payload_team_signature(run)
            if signature is None:
                continue
            saw_signature = True
            expected_size = min(max_players, len(signature))
            buckets = buckets_by_signature.setdefault(signature, [])
            target = next(
                (
                    bucket
                    for bucket in buckets
                    if len(bucket) < expected_size
                    and all(item.team_id != run.team_id for item in bucket)
                    and self._runs_are_close_enough_for_archive_group(
                        previous=bucket[-1],
                        current=run,
                        close_seconds=close_seconds,
                    )
                ),
                None,
            )
            if target is None:
                target = []
                buckets.append(target)
                groups.append(target)
                expected_size_by_group[id(target)] = expected_size
            target.append(run)
        if not saw_signature:
            return None
        return [
            [run.run_id for run in group]
            for group in groups
            if len(group) == expected_size_by_group.get(id(group), len(group))
        ]

    @staticmethod
    def _runs_are_close_enough_for_archive_group(*, previous: Run, current: Run, close_seconds: float) -> bool:
        previous_created_at = _datetime_or_none(previous.created_at)
        created_at = _datetime_or_none(current.created_at)
        if previous_created_at is None or created_at is None:
            return False
        return abs((previous_created_at - created_at).total_seconds()) <= close_seconds

    @staticmethod
    def _archived_time_match_run_id_groups(*, sorted_runs: list[Run], max_players: int) -> list[list[str]]:
        groups: list[list[str]] = []
        current: list[Run] = []
        close_seconds = 2.0
        for run in sorted_runs:
            previous = current[-1] if current else None
            if previous is not None:
                previous_created_at = _datetime_or_none(previous.created_at)
                created_at = _datetime_or_none(run.created_at)
                if (
                    len(current) >= max_players
                    or previous_created_at is None
                    or created_at is None
                    or abs((previous_created_at - created_at).total_seconds()) > close_seconds
                ):
                    groups.append([item.run_id for item in current])
                    current = []
            current.append(run)
        if current:
            groups.append([item.run_id for item in current])
        return groups

    @staticmethod
    def _payload_team_signature(run: Run) -> tuple[str, ...] | None:
        payload = run.result_payload if isinstance(run.result_payload, dict) else {}
        metrics = payload.get("metrics")
        metrics_dict = metrics if isinstance(metrics, dict) else {}
        team_ids: set[str] = set()

        for participant_key in ("match_participants", "participants"):
            participants = payload.get(participant_key)
            if isinstance(participants, list):
                for item in participants:
                    if not isinstance(item, dict):
                        continue
                    team_id = item.get("team_id")
                    if team_id:
                        team_ids.add(str(team_id))
                if len(team_ids) > 1:
                    return tuple(sorted(team_ids))

        for source in (payload, metrics_dict):
            for key in ("scores", "placements"):
                value = source.get(key)
                if isinstance(value, dict):
                    team_ids.update(str(team_id) for team_id in value.keys() if team_id)
        if len(team_ids) <= 1:
            return None
        return tuple(sorted(team_ids))

    def _build_archived_match_group_views(
        self,
        *,
        lobby: Lobby,
        runs: list[Run],
        limit: int,
    ) -> tuple[LobbyMatchGroupView, ...]:
        if not runs:
            return ()
        runs_with_payload = self._finished_runs_with_payload_cached(lobby=lobby, runs=runs)
        groups = self._archived_match_run_id_groups(lobby=lobby, runs=runs_with_payload)
        runs_by_id = {run.run_id: run for run in runs_with_payload}
        return tuple(
            self._build_match_group_view(
                group_id=f"archive-{index}",
                batch_id=self._batch_id_for_groups(groups=[group], runs_by_id=runs_by_id),
                run_ids=group,
                runs_by_id=runs_by_id,
                archived=True,
                replay_started_at=None,
                replay_frame_index=0,
            )
            for index, group in enumerate(groups[:limit])
        )

    def _build_archived_match_group_views_cached(
        self,
        *,
        lobby: Lobby,
        runs: list[Run],
        limit: int,
    ) -> tuple[LobbyMatchGroupView, ...]:
        signature = (self._finished_runs_signature(lobby=lobby, runs=runs), limit)
        cached = self._archived_match_groups_cache.get(lobby.lobby_id)
        if cached is not None and cached[0] == signature:
            return cached[1]

        groups = self._build_archived_match_group_views(lobby=lobby, runs=runs, limit=limit)
        self._archived_match_groups_cache[lobby.lobby_id] = (signature, groups)
        return groups

    def _build_match_group_view(
        self,
        *,
        group_id: str,
        batch_id: str,
        run_ids: list[str],
        runs_by_id: dict[str, Run],
        archived: bool,
        replay_started_at: datetime | None,
        replay_frame_index: int,
    ) -> LobbyMatchGroupView:
        runs = [runs_by_id[run_id] for run_id in run_ids if run_id in runs_by_id]
        payload_runs = [self._ensure_payload(run) if run.status in _REPLAYABLE_RUN_STATUSES else run for run in runs]
        statuses = {run.status for run in runs}
        if statuses & _ACTIVE_RUN_STATUSES:
            status = "simulation"
        elif archived:
            status = "finished"
        elif statuses and statuses <= _REPLAYABLE_RUN_STATUSES:
            status = "replay" if replay_started_at is not None else "result"
        else:
            status = "pending"
        started_at = min(
            (value for run in runs if (value := _datetime_or_none(run.created_at)) is not None),
            default=None,
        )
        finished_at = max(
            (value for run in runs if (value := _datetime_or_none(run.finished_at)) is not None),
            default=None,
        )
        frame_count = max((self._replay_frames_count(run) for run in payload_runs), default=1)
        return LobbyMatchGroupView(
            group_id=group_id,
            batch_id=batch_id,
            run_ids=tuple(run.run_id for run in runs),
            team_ids=tuple(run.team_id for run in runs),
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            replay_frame_count=frame_count,
            replay_frame_index=max(0, min(replay_frame_index, frame_count - 1)),
            winner_team_ids=self._winner_team_ids(payload_runs),
            scores_by_team=self._scores_by_team(payload_runs),
        )

    def _batch_id_for_groups(self, *, groups: list[list[str]], runs_by_id: dict[str, Run]) -> str:
        started_at = self._batch_started_at(groups=groups, runs_by_id=runs_by_id)
        return started_at.isoformat() if started_at else "-".join(run_id for group in groups for run_id in group)

    @staticmethod
    def _batch_started_at(*, groups: list[list[str]], runs_by_id: dict[str, Run]) -> datetime | None:
        return min(
            (
                created_at
                for group in groups
                for run_id in group
                if (created_at := _datetime_or_none(runs_by_id.get(run_id).created_at if runs_by_id.get(run_id) else None))
                is not None
            ),
            default=None,
        )

    def _ensure_payload(self, run: Run) -> Run:
        if run.result_payload is not None:
            return run
        if run.status not in _TERMINAL_RUN_STATUSES:
            return run
        return self._execution.get_run(run.run_id)

    def _has_online_ready_viewer(self, lobby: Lobby) -> bool:
        now = utc_now()
        redis_count = self._online_viewer_count_from_redis(lobby_id=lobby.lobby_id, now=now)
        if redis_count is not None:
            return redis_count > 0
        self._prune_online_viewers(lobby_id=lobby.lobby_id, now=now)
        return bool(self._viewer_last_seen_by_lobby.get(lobby.lobby_id, {}))

    def _prune_online_viewers(self, *, lobby_id: str, now: datetime) -> None:
        viewers = self._viewer_last_seen_by_lobby.get(lobby_id)
        if not viewers:
            return
        cutoff = now - timedelta(seconds=_LOBBY_ONLINE_VIEWER_TTL_SECONDS)
        stale = [user_id for user_id, seen_at in viewers.items() if seen_at < cutoff]
        for user_id in stale:
            viewers.pop(user_id, None)
        if not viewers:
            self._viewer_last_seen_by_lobby.pop(lobby_id, None)

    def _mark_viewer_online_in_redis(self, *, lobby_id: str, user_id: str, now: datetime) -> bool:
        client = self._matchmaking_lock_client
        zadd = getattr(client, "zadd", None)
        expire = getattr(client, "expire", None)
        if not callable(zadd):
            return False
        key = self._viewer_presence_key(lobby_id)
        try:
            zadd(key, {user_id: now.timestamp()})
            if callable(expire):
                expire(key, _LOBBY_ONLINE_VIEWER_TTL_SECONDS * 2)
        except Exception:
            return False
        return True

    def _online_viewer_count_from_redis(self, *, lobby_id: str, now: datetime) -> int | None:
        client = self._matchmaking_lock_client
        zremrangebyscore = getattr(client, "zremrangebyscore", None)
        zcard = getattr(client, "zcard", None)
        if not callable(zremrangebyscore) or not callable(zcard):
            return None
        key = self._viewer_presence_key(lobby_id)
        cutoff = now.timestamp() - _LOBBY_ONLINE_VIEWER_TTL_SECONDS
        try:
            zremrangebyscore(key, "-inf", cutoff)
            return int(zcard(key))
        except Exception:
            return None

    @staticmethod
    def _viewer_presence_key(lobby_id: str) -> str:
        return f"{_LOBBY_VIEWER_PRESENCE_KEY_PREFIX}{lobby_id}"

    def _winner_team_ids(self, runs: list[Run]) -> tuple[str, ...]:
        winner = self._single_winner_team_id(runs)
        return () if winner is None else (winner,)

    def _scores_by_team(self, runs: list[Run]) -> dict[str, float]:
        scores: dict[str, float] = {}
        group_team_ids = {run.team_id for run in runs}
        for run in runs:
            payload = run.result_payload if isinstance(run.result_payload, dict) else {}
            metrics = payload.get("metrics")
            metrics_dict = metrics if isinstance(metrics, dict) else {}
            payload_scores = payload.get("scores")
            metrics_scores = metrics_dict.get("scores")
            for source in (payload_scores, metrics_scores):
                if not isinstance(source, dict):
                    continue
                for team_id, raw_score in source.items():
                    if team_id not in group_team_ids or not isinstance(raw_score, (int, float)):
                        continue
                    scores[team_id] = max(scores.get(team_id, float(raw_score)), float(raw_score))
            own_score = self._extract_score(payload=payload, metrics=metrics_dict, team_id=run.team_id)
            if own_score is not None:
                scores[run.team_id] = max(scores.get(run.team_id, own_score), own_score)
        return scores

    def _winner_team_ids_for_groups(self, *, groups: list[list[str]], runs_by_id: dict[str, Run]) -> tuple[str, ...]:
        winners: list[str] = []
        for group in groups:
            winner = self._single_winner_team_id([runs_by_id[run_id] for run_id in group if run_id in runs_by_id])
            if winner is not None:
                winners.append(winner)
        return tuple(dict.fromkeys(winners))

    def _single_winner_team_id(self, runs: list[Run]) -> str | None:
        group_team_ids = {run.team_id for run in runs}
        placements_by_team: dict[str, int] = {}
        scored: dict[str, float] = {}
        for run in runs:
            payload = run.result_payload if isinstance(run.result_payload, dict) else {}
            metrics = payload.get("metrics")
            metrics_dict = metrics if isinstance(metrics, dict) else {}
            placements = payload.get("placements")
            if not isinstance(placements, dict):
                placements = metrics_dict.get("placements")
            if isinstance(placements, dict):
                for team_id, raw_place in placements.items():
                    if team_id not in group_team_ids or not isinstance(raw_place, int):
                        continue
                    previous = placements_by_team.get(team_id)
                    placements_by_team[team_id] = raw_place if previous is None else min(previous, raw_place)
            score = self._extract_score(payload=payload, metrics=metrics_dict, team_id=run.team_id)
            if score is not None:
                scored[run.team_id] = score

        if placements_by_team:
            best_place = min(placements_by_team.values())
            placed_winners = [team_id for team_id, place in placements_by_team.items() if place == best_place]
            if len(placed_winners) == 1:
                return placed_winners[0]

        score_map = self._scores_by_team(runs)
        scored_candidates = score_map or scored
        if scored_candidates:
            best = max(scored_candidates.values())
            scored_winners = [team_id for team_id, score in scored_candidates.items() if score == best]
            return sorted(scored_winners, key=self._team_sort_key)[0]

        if placements_by_team:
            best_place = min(placements_by_team.values())
            placed_winners = [team_id for team_id, place in placements_by_team.items() if place == best_place]
            return sorted(placed_winners, key=self._team_sort_key)[0]
        return None

    def _team_sort_key(self, team_id: str) -> tuple[str, str]:
        try:
            team = self._team_workspace.get_team(team_id)
        except NotFoundError:
            return (team_id.casefold(), team_id)
        label = team.name or team.captain_user_id or team_id
        return (label.casefold(), team_id)

    def _team_label(self, team_id: str) -> str:
        try:
            team = self._team_workspace.get_team(team_id)
        except NotFoundError:
            return team_id
        return team.name or team.captain_user_id or team_id

    @staticmethod
    def _replay_frames_count(run: Run) -> int:
        payload = run.result_payload if isinstance(run.result_payload, dict) else {}
        frames = payload.get("frames")
        if isinstance(frames, list) and frames:
            return len(frames)
        return 1

    def _collect_participant_stats_cached(self, lobby: Lobby, runs: list[Run]) -> tuple[LobbyParticipantStats, ...]:
        signature = self._finished_runs_signature(lobby=lobby, runs=runs)
        cached = self._participant_stats_cache.get(lobby.lobby_id)
        if cached is not None and cached[0] == signature:
            return cached[1]

        runs_with_payload = self._finished_runs_with_payload_cached(lobby=lobby, runs=runs)
        stats = self._collect_participant_stats(lobby=lobby, runs=runs_with_payload)
        self._participant_stats_cache[lobby.lobby_id] = (signature, stats)
        return stats

    def _finished_runs_with_payload_cached(self, *, lobby: Lobby, runs: list[Run]) -> list[Run]:
        signature = self._finished_runs_signature(lobby=lobby, runs=runs)
        cached = self._finished_runs_payload_cache.get(lobby.lobby_id)
        if cached is not None and cached[0] == signature:
            return cached[1]

        runs_with_payload = [
            run
            if run.result_payload is not None or run.status is not RunStatus.FINISHED
            else self._execution.get_run(run.run_id)
            for run in runs
        ]
        self._finished_runs_payload_cache[lobby.lobby_id] = (signature, runs_with_payload)
        return runs_with_payload

    def _finished_runs_signature(self, *, lobby: Lobby, runs: list[Run]) -> object:
        return (
            tuple(
                sorted(
                    (
                        run.run_id,
                        run.status.value,
                        _datetime_or_none(run.finished_at),
                    )
                    for run in runs
                )
            ),
            tuple(sorted(lobby.teams.keys())),
        )

    def _clear_lobby_derived_caches(self, lobby_id: str) -> None:
        self._participant_stats_cache.pop(lobby_id, None)
        self._archived_match_groups_cache.pop(lobby_id, None)
        self._finished_runs_payload_cache.pop(lobby_id, None)
        self._live_state_cache.pop(lobby_id, None)

    def _get_cached_lobby_live_state(self, lobby: Lobby) -> tuple[tuple[Run, ...], tuple[Run, ...], _LobbyCycleState]:
        now = utc_now()
        signature = self._lobby_live_signature(lobby)
        cached = self._live_state_cache.get(lobby.lobby_id)
        if cached is not None and cached.expires_at > now and cached.lobby_signature == signature:
            return cached.runs, cached.active_runs, cached.cycle

        runs = tuple(
            self._execution.list_runs(
                lobby_id=lobby.lobby_id,
                run_kind=RunKind.TRAINING_MATCH,
                include_result_payload=False,
            )
        )
        active_runs = tuple(run for run in runs if run.status in _ACTIVE_RUN_STATUSES)
        cycle = self._compute_cycle_state(lobby=lobby, runs=list(runs))
        if cycle.phase not in {"replay", "result"}:
            self._live_state_cache[lobby.lobby_id] = _CachedLobbyLiveState(
                expires_at=now + timedelta(seconds=_LOBBY_LIVE_CACHE_TTL_SECONDS),
                lobby_signature=signature,
                runs=runs,
                active_runs=active_runs,
                cycle=cycle,
            )
        else:
            self._live_state_cache.pop(lobby.lobby_id, None)
        return runs, active_runs, cycle

    @staticmethod
    def _lobby_live_signature(lobby: Lobby) -> object:
        return (
            lobby.status.value,
            lobby.game_version_id,
            tuple(lobby.last_scheduled_run_ids),
            tuple(tuple(group) for group in lobby.last_scheduled_match_groups),
            tuple(
                sorted(
                    (team_id, state.ready, state.blocker_reason)
                    for team_id, state in lobby.teams.items()
                )
            ),
        )

    def _collect_participant_stats(self, lobby: Lobby, runs: list[Run]) -> tuple[LobbyParticipantStats, ...]:
        wins_by_team, matches_by_team, score_sum_by_team, score_count_by_team = self._cumulative_stats_maps(lobby)

        runs_by_id = {run.run_id: run for run in runs if run.team_id in lobby.teams}
        for group in self._archived_match_run_id_groups(lobby=lobby, runs=list(runs_by_id.values())):
            group_runs = [runs_by_id[run_id] for run_id in group if run_id in runs_by_id]
            if not group_runs:
                continue
            winner_team_id = self._single_winner_team_id(group_runs)
            if winner_team_id is not None:
                wins_by_team[winner_team_id] = wins_by_team.get(winner_team_id, 0) + 1

            group_scores = self._scores_by_team(group_runs)
            for run in group_runs:
                matches_by_team[run.team_id] = matches_by_team.get(run.team_id, 0) + 1
                score = group_scores.get(run.team_id)
                if score is not None:
                    score_sum_by_team[run.team_id] = score_sum_by_team.get(run.team_id, 0.0) + score
                    score_count_by_team[run.team_id] = score_count_by_team.get(run.team_id, 0) + 1

        items: list[LobbyParticipantStats] = []
        for team_id in sorted(lobby.teams.keys()):
            team = self._team_workspace.get_team(team_id)
            matches_total = matches_by_team.get(team_id, 0)
            score_count = score_count_by_team.get(team_id, 0)
            average_score = None if score_count == 0 else score_sum_by_team.get(team_id, 0.0) / score_count
            items.append(
                LobbyParticipantStats(
                    team_id=team_id,
                    captain_user_id=team.captain_user_id,
                    display_name=team.name,
                    matches_total=matches_total,
                    wins=wins_by_team.get(team_id, 0),
                    average_score=average_score,
                )
            )
        return tuple(items)

    @staticmethod
    def _cumulative_stats_maps(
        lobby: Lobby,
    ) -> tuple[dict[str, int], dict[str, int], dict[str, float], dict[str, int]]:
        wins_by_team: dict[str, int] = {}
        matches_by_team: dict[str, int] = {}
        score_sum_by_team: dict[str, float] = {}
        score_count_by_team: dict[str, int] = {}
        for team_id, stats in lobby.cumulative_stats_by_team.items():
            wins_by_team[team_id] = int(stats.get("wins", 0) or 0)
            matches_by_team[team_id] = int(stats.get("matches_total", 0) or 0)
            score_sum_by_team[team_id] = float(stats.get("score_sum", 0.0) or 0.0)
            score_count_by_team[team_id] = int(stats.get("score_count", 0) or 0)
        return wins_by_team, matches_by_team, score_sum_by_team, score_count_by_team

    def _add_cumulative_stats_for_match_groups(
        self,
        *,
        lobby: Lobby,
        groups: list[list[str]],
        runs_by_id: dict[str, Run],
    ) -> None:
        for group in groups:
            group_runs = [
                runs_by_id[run_id]
                for run_id in group
                if run_id in runs_by_id and runs_by_id[run_id].team_id in lobby.teams
            ]
            if not group_runs:
                continue
            winner_team_id = self._single_winner_team_id(group_runs)
            group_scores = self._scores_by_team(group_runs)
            for run in group_runs:
                stats = lobby.cumulative_stats_by_team.setdefault(
                    run.team_id,
                    {"matches_total": 0, "wins": 0, "score_sum": 0.0, "score_count": 0},
                )
                stats["matches_total"] = int(stats.get("matches_total", 0) or 0) + 1
                if winner_team_id == run.team_id:
                    stats["wins"] = int(stats.get("wins", 0) or 0) + 1
                score = group_scores.get(run.team_id)
                if score is not None:
                    stats["score_sum"] = float(stats.get("score_sum", 0.0) or 0.0) + score
                    stats["score_count"] = int(stats.get("score_count", 0) or 0) + 1

    @staticmethod
    def _extract_score(
        *,
        payload: dict[str, object],
        metrics: dict[str, object],
        team_id: str,
    ) -> float | None:
        for source in (payload, metrics):
            for key in ("score", "points"):
                raw = source.get(key)
                if isinstance(raw, (int, float)):
                    return float(raw)
        for source in (payload, metrics):
            scores = source.get("scores")
            if not isinstance(scores, dict):
                continue
            raw = scores.get(team_id)
            if isinstance(raw, (int, float)):
                return float(raw)
            if len(scores) == 1:
                only_value = next(iter(scores.values()))
                if isinstance(only_value, (int, float)):
                    return float(only_value)
        return None


def _compact_shadow_payload(payload: dict[str, object]) -> dict[str, object]:
    compact = {
        key: value
        for key, value in payload.items()
        if key not in {"frames", "events"}
    }
    compact["shadow_result"] = True
    return compact
