from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

from execution.application.service import CreateRunInput, ExecutionService
from execution.domain.model import Run, RunKind, RunStatus
from game_catalog.application.service import GameCatalogService
from game_catalog.domain.model import CatalogMetadataStatus, GameMode
from team_workspace.application.service import TeamWorkspaceService
from training_lobby.application.repositories import LobbyRepository
from training_lobby.domain.model import Lobby, LobbyAccess, LobbyKind, LobbyStatus
from shared.kernel import InvariantViolationError, NotFoundError, utc_now


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
_LOBBY_REPLAY_FRAME_MS = 500
_LOBBY_REPLAY_GRACE_SECONDS = 1


def _can_change_participation(lobby: Lobby) -> bool:
    if lobby.status in {LobbyStatus.OPEN, LobbyStatus.DRAFT}:
        return True
    return lobby.kind is LobbyKind.TRAINING and lobby.status is LobbyStatus.RUNNING


@dataclass(frozen=True, slots=True)
class LobbyParticipantStats:
    team_id: str
    captain_user_id: str
    display_name: str
    matches_total: int
    wins: int
    average_score: float | None


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


class TrainingLobbyService:
    def __init__(
        self,
        repository: LobbyRepository,
        game_catalog: GameCatalogService,
        team_workspace: TeamWorkspaceService,
        execution: ExecutionService,
    ) -> None:
        self._repository = repository
        self._game_catalog = game_catalog
        self._team_workspace = team_workspace
        self._execution = execution
        self._matchmaking_locks: dict[str, Lock] = {}
        self._participant_stats_cache: dict[
            str,
            tuple[tuple[int, object | None], tuple[LobbyParticipantStats, ...]],
        ] = {}

    def create_lobby(self, data: CreateLobbyInput) -> Lobby:
        game = self._game_catalog.get_game(data.game_id)
        if game.mode is GameMode.SINGLE_TASK:
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
        game_teams = self._team_workspace.list_teams_by_game_and_captain(game_id=lobby.game_id, captain_user_id=user_id)
        team_ids = {team.team_id for team in game_teams}
        for team_id in lobby.teams:
            if team_id in team_ids:
                return team_id
        return None

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
        runs = self._execution.list_runs(
            lobby_id=lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        for run in runs:
            if run.team_id != team_id:
                continue
            if run.status in _ACTIVE_RUN_STATUSES:
                self._execution.cancel_run(run.run_id, message="manual_stop_lobby")
        if team_id in lobby.teams and lobby.teams[team_id].ready:
            lobby.mark_ready(team_id=team_id, ready=False)
            self._repository.save(lobby)
        lobby = self.reconcile_training_lobby_status(lobby_id=lobby_id)
        return lobby

    def get_live_view(self, lobby_id: str, user_id: str) -> LobbyLiveView:
        lobby = self.get_lobby(lobby_id)
        runs = self._execution.list_runs(
            lobby_id=lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        active_runs = [run for run in runs if run.status in _ACTIVE_RUN_STATUSES]
        playing_team_ids = tuple(sorted({run.team_id for run in active_runs if run.status is RunStatus.RUNNING}))
        queued_team_ids = set(
            run.team_id for run in active_runs if run.status in {RunStatus.CREATED, RunStatus.QUEUED}
        )
        queued_team_ids.update(
            team_id
            for team_id, team_state in lobby.teams.items()
            if team_state.ready and team_id not in playing_team_ids
        )
        queued_team_ids_tuple = tuple(sorted(queued_team_ids))

        my_team_id = self.find_user_team_in_lobby(lobby_id=lobby_id, user_id=user_id)
        current_run_id = None
        if my_team_id is not None:
            for run in sorted(active_runs, key=lambda item: item.created_at, reverse=True):
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
            if run.status in _TERMINAL_RUN_STATUSES
        ]
        finished_runs.sort(key=lambda item: item.created_at, reverse=True)
        archived_run_ids = tuple(run.run_id for run in finished_runs[:100])
        current_run_ids = tuple(run.run_id for run in sorted(active_runs, key=lambda item: item.created_at, reverse=True))
        participant_stats = self._collect_participant_stats_cached(lobby=lobby, runs=finished_runs)

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
        )

    def join_team(self, lobby_id: str, team_id: str, access_code: str | None) -> Lobby:
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

        lobby.join_team(team_id=team_id, access_code=access_code)
        self._repository.save(lobby)
        return lobby

    def leave_team(self, lobby_id: str, team_id: str) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        lobby.leave_team(team_id)
        self._repository.save(lobby)
        return lobby

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
        elif status == LobbyStatus.CLOSED:
            lobby.close()
        else:
            raise InvariantViolationError("Разрешены только статусы open, paused и closed")
        self._repository.save(lobby)
        return lobby

    def reconcile_training_lobby_status(self, lobby_id: str) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        if lobby.kind is not LobbyKind.TRAINING:
            return lobby
        if lobby.status not in {LobbyStatus.OPEN, LobbyStatus.RUNNING}:
            return lobby

        active_runs = [
            run
            for run in self._execution.list_runs(
                lobby_id=lobby_id,
                run_kind=RunKind.TRAINING_MATCH,
                include_result_payload=False,
            )
            if run.status in _ACTIVE_RUN_STATUSES
        ]
        if active_runs:
            lobby.set_running()
        else:
            lobby.set_open()
            lobby.set_last_scheduled_runs([])
        self._repository.save(lobby)
        return lobby

    def run_matchmaking_cycle(self, lobby_id: str, requested_by: str) -> Lobby:
        lock = self._matchmaking_locks.setdefault(lobby_id, Lock())
        with lock:
            return self._run_matchmaking_cycle_locked(lobby_id=lobby_id, requested_by=requested_by)

    def _run_matchmaking_cycle_locked(self, lobby_id: str, requested_by: str) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        if lobby.kind is not LobbyKind.TRAINING:
            raise InvariantViolationError("Matchmaking cycle доступен только для training лобби")
        if lobby.status in {LobbyStatus.PAUSED, LobbyStatus.UPDATING, LobbyStatus.CLOSED, LobbyStatus.DRAFT}:
            raise InvariantViolationError("В текущем статусе лобби матчмейкинг недоступен")

        game = self._game_catalog.get_game(lobby.game_id)
        runs = self._execution.list_runs(
            lobby_id=lobby.lobby_id,
            run_kind=RunKind.TRAINING_MATCH,
            include_result_payload=False,
        )
        active_runs = [run for run in runs if run.status in _ACTIVE_RUN_STATUSES]
        busy_team_ids = {run.team_id for run in active_runs}
        if not active_runs and self._is_waiting_for_replay_display(runs):
            lobby.set_open()
            lobby.set_last_scheduled_runs([])
            self._repository.save(lobby)
            return lobby

        ready_team_ids = [
            state.team_id
            for state in lobby.teams.values()
            if state.ready
        ]
        ready_team_ids = [team_id for team_id in ready_team_ids if team_id not in busy_team_ids]

        scheduled_team_groups: list[list[str]] = []

        if game.mode.value == "small_match":
            while len(ready_team_ids) >= 2:
                pair = ready_team_ids[:2]
                del ready_team_ids[:2]
                scheduled_team_groups.append(pair)
        elif game.mode.value == "massive_lobby":
            if len(ready_team_ids) >= 2:
                scheduled_team_groups.append(list(ready_team_ids))
        else:
            # single_task не должен работать через lobby matchmaking.
            raise InvariantViolationError("single_task игра не поддерживает lobby matchmaking")

        scheduled_run_ids: list[str] = []
        for team_ids in scheduled_team_groups:
            scheduled_run_ids.extend(
                self._create_training_match_runs(
                    lobby=lobby,
                    team_ids=team_ids,
                    requested_by=requested_by,
                )
            )

        if scheduled_run_ids:
            lobby.set_running()
            lobby.set_last_scheduled_runs(scheduled_run_ids)
            self._repository.save(lobby)
            for run_id in scheduled_run_ids:
                self._execution.queue_run(run_id)
        else:
            if active_runs:
                lobby.set_running()
                self._repository.save(lobby)
                return lobby
            else:
                lobby.set_open()
                lobby.set_last_scheduled_runs([])
            self._repository.save(lobby)

        return lobby

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

    def _is_waiting_for_replay_display(self, runs: list[Run]) -> bool:
        terminal_runs = [
            run
            for run in runs
            if run.run_kind is RunKind.TRAINING_MATCH
            and run.status in _TERMINAL_RUN_STATUSES
            and isinstance(run.finished_at, datetime)
        ]
        if not terminal_runs:
            return False

        latest_run = max(terminal_runs, key=lambda run: run.finished_at)
        finished_at = latest_run.finished_at
        if finished_at is None:
            return False
        if finished_at.tzinfo is None:
            finished_at = finished_at.replace(tzinfo=utc_now().tzinfo)
        run_with_payload = latest_run
        if run_with_payload.result_payload is None:
            run_with_payload = self._execution.get_run(latest_run.run_id)
        frames_count = self._replay_frames_count(run_with_payload)
        display_seconds = max(1.0, frames_count * _LOBBY_REPLAY_FRAME_MS / 1000)
        display_until = finished_at + timedelta(seconds=display_seconds + _LOBBY_REPLAY_GRACE_SECONDS)
        return utc_now() < display_until

    @staticmethod
    def _replay_frames_count(run: Run) -> int:
        payload = run.result_payload if isinstance(run.result_payload, dict) else {}
        frames = payload.get("frames")
        if isinstance(frames, list) and frames:
            return len(frames)
        return 1

    def _collect_participant_stats_cached(self, lobby: Lobby, runs: list[Run]) -> tuple[LobbyParticipantStats, ...]:
        latest_finished_at = max(
            (run.finished_at for run in runs if isinstance(run.finished_at, datetime)),
            default=None,
        )
        signature = (len(runs), latest_finished_at)
        cached = self._participant_stats_cache.get(lobby.lobby_id)
        if cached is not None and cached[0] == signature:
            return cached[1]

        runs_with_payload = [
            run if run.result_payload is not None else self._execution.get_run(run.run_id)
            for run in runs
        ]
        stats = self._collect_participant_stats(lobby=lobby, runs=runs_with_payload)
        self._participant_stats_cache[lobby.lobby_id] = (signature, stats)
        return stats

    def _collect_participant_stats(self, lobby: Lobby, runs: list[Run]) -> tuple[LobbyParticipantStats, ...]:
        wins_by_team: dict[str, int] = {}
        matches_by_team: dict[str, int] = {}
        score_sum_by_team: dict[str, float] = {}
        score_count_by_team: dict[str, int] = {}

        for run in runs:
            if run.team_id not in lobby.teams:
                continue
            matches_by_team[run.team_id] = matches_by_team.get(run.team_id, 0) + 1

            payload = run.result_payload if isinstance(run.result_payload, dict) else {}
            metrics = payload.get("metrics")
            metrics_dict = metrics if isinstance(metrics, dict) else {}
            placements = payload.get("placements")
            if not isinstance(placements, dict):
                placements = metrics_dict.get("placements")
            if isinstance(placements, dict):
                raw_place = placements.get(run.team_id)
                if isinstance(raw_place, int) and raw_place == 1:
                    wins_by_team[run.team_id] = wins_by_team.get(run.team_id, 0) + 1
            score = self._extract_score(payload=payload, metrics=metrics_dict, team_id=run.team_id)
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
