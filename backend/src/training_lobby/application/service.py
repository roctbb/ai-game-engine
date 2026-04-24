from __future__ import annotations

from dataclasses import dataclass

from execution.application.service import CreateRunInput, ExecutionService
from execution.domain.model import RunKind, RunStatus
from game_catalog.application.service import GameCatalogService
from team_workspace.application.service import TeamWorkspaceService
from training_lobby.application.repositories import LobbyRepository
from training_lobby.domain.model import Lobby, LobbyAccess, LobbyKind, LobbyStatus
from shared.kernel import InvariantViolationError, NotFoundError


@dataclass(slots=True)
class CreateLobbyInput:
    game_id: str
    title: str
    kind: LobbyKind
    access: LobbyAccess
    access_code: str | None
    max_teams: int


_ACTIVE_RUN_STATUSES = {RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING}


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

    def create_lobby(self, data: CreateLobbyInput) -> Lobby:
        game = self._game_catalog.get_game(data.game_id)
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

    def join_team(self, lobby_id: str, team_id: str, access_code: str | None) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        team = self._team_workspace.get_team(team_id)

        if team.game_id != lobby.game_id:
            raise InvariantViolationError("Команда может вступать только в лобби своей игры")

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
        if lobby.status not in {LobbyStatus.OPEN, LobbyStatus.DRAFT}:
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

    def run_matchmaking_cycle(self, lobby_id: str, requested_by: str) -> Lobby:
        lobby = self.get_lobby(lobby_id)
        if lobby.kind is not LobbyKind.TRAINING:
            raise InvariantViolationError("Matchmaking cycle доступен только для training лобби")
        if lobby.status in {LobbyStatus.PAUSED, LobbyStatus.UPDATING, LobbyStatus.CLOSED, LobbyStatus.DRAFT}:
            raise InvariantViolationError("В текущем статусе лобби матчмейкинг недоступен")

        game = self._game_catalog.get_game(lobby.game_id)
        runs = self._execution.list_runs(lobby_id=lobby.lobby_id, run_kind=RunKind.TRAINING_MATCH)
        active_runs = [run for run in runs if run.status in _ACTIVE_RUN_STATUSES]
        busy_team_ids = {run.team_id for run in active_runs}

        ready_team_ids = [
            state.team_id
            for state in lobby.teams.values()
            if state.ready
        ]
        ready_team_ids = [team_id for team_id in ready_team_ids if team_id not in busy_team_ids]

        scheduled_run_ids: list[str] = []

        if game.mode.value == "small_match":
            while len(ready_team_ids) >= 2:
                pair = ready_team_ids[:2]
                del ready_team_ids[:2]
                scheduled_run_ids.extend(
                    self._schedule_training_match(
                        lobby=lobby,
                        team_ids=pair,
                        requested_by=requested_by,
                    )
                )
        elif game.mode.value == "massive_lobby":
            if len(ready_team_ids) >= 2:
                scheduled_run_ids.extend(
                    self._schedule_training_match(
                        lobby=lobby,
                        team_ids=list(ready_team_ids),
                        requested_by=requested_by,
                    )
                )
        else:
            # single_task не должен работать через lobby matchmaking.
            raise InvariantViolationError("single_task игра не поддерживает lobby matchmaking")

        if scheduled_run_ids:
            lobby.set_running()
            lobby.set_last_scheduled_runs(scheduled_run_ids)
        else:
            if active_runs:
                lobby.set_running()
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

    def _schedule_training_match(self, lobby: Lobby, team_ids: list[str], requested_by: str) -> list[str]:
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
            queued = self._execution.queue_run(run.run_id)
            run_ids.append(queued.run_id)
        return run_ids
