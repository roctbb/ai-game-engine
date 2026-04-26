from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from shared.kernel import InvariantViolationError, NotFoundError, new_id, utc_now

_UNSET = object()


class LobbyKind(StrEnum):
    TRAINING = "training"
    COMPETITION = "competition"


class LobbyAccess(StrEnum):
    PUBLIC = "public"
    CODE = "code"


class LobbyStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    UPDATING = "updating"
    CLOSED = "closed"


@dataclass(slots=True)
class LobbyTeamState:
    team_id: str
    ready: bool = False
    blocker_reason: str | None = None


@dataclass(slots=True)
class Lobby:
    lobby_id: str
    game_id: str
    game_version_id: str
    title: str
    kind: LobbyKind
    access: LobbyAccess
    access_code: str | None
    max_teams: int
    status: LobbyStatus
    teams: dict[str, LobbyTeamState] = field(default_factory=dict)
    last_scheduled_run_ids: tuple[str, ...] = ()
    last_scheduled_match_groups: tuple[tuple[str, ...], ...] = ()
    auto_delete_training_runs_days: int | None = None
    created_at: object = field(default_factory=utc_now)

    @staticmethod
    def create(
        game_id: str,
        game_version_id: str,
        title: str,
        kind: LobbyKind,
        access: LobbyAccess,
        access_code: str | None,
        max_teams: int,
    ) -> "Lobby":
        if access == LobbyAccess.CODE and not access_code:
            raise InvariantViolationError("Для закрытого лобби нужен код доступа")
        status = LobbyStatus.OPEN if kind == LobbyKind.TRAINING else LobbyStatus.DRAFT
        return Lobby(
            lobby_id=new_id("lobby"),
            game_id=game_id,
            game_version_id=game_version_id,
            title=title,
            kind=kind,
            access=access,
            access_code=access_code,
            max_teams=max_teams,
            status=status,
        )

    def join_team(self, team_id: str, access_code: str | None = None, *, bypass_access_code: bool = False) -> None:
        joinable_statuses = {LobbyStatus.OPEN, LobbyStatus.DRAFT}
        if self.kind is LobbyKind.TRAINING:
            joinable_statuses.add(LobbyStatus.RUNNING)
        if self.status not in joinable_statuses:
            raise InvariantViolationError("В текущем статусе нельзя присоединиться к лобби")
        if team_id in self.teams:
            raise InvariantViolationError("Команда уже в лобби")
        if len(self.teams) >= self.max_teams:
            raise InvariantViolationError("Лобби заполнено")
        if not bypass_access_code and self.access == LobbyAccess.CODE and self.access_code != access_code:
            raise InvariantViolationError("Неверный код доступа к лобби")
        self.teams[team_id] = LobbyTeamState(team_id=team_id, ready=False)

    def leave_team(self, team_id: str) -> None:
        if team_id not in self.teams:
            raise NotFoundError("Команда не состоит в лобби")
        if self.kind == LobbyKind.COMPETITION and self.status == LobbyStatus.RUNNING:
            raise InvariantViolationError("Во время соревнования выход запрещен")
        self.teams.pop(team_id)

    def mark_ready(self, team_id: str, ready: bool, blocker_reason: str | None = None) -> None:
        if team_id not in self.teams:
            raise NotFoundError("Команда не состоит в лобби")
        team_state = self.teams[team_id]
        team_state.ready = ready
        team_state.blocker_reason = blocker_reason

    def start_updating(self) -> None:
        if self.kind == LobbyKind.COMPETITION and self.status == LobbyStatus.RUNNING:
            raise InvariantViolationError("Нельзя обновлять игру во время соревнования")
        self.status = LobbyStatus.UPDATING

    def finish_updating(self) -> None:
        if self.status != LobbyStatus.UPDATING:
            return
        self.status = LobbyStatus.OPEN if self.kind == LobbyKind.TRAINING else LobbyStatus.DRAFT

    def set_running(self) -> None:
        if self.kind != LobbyKind.TRAINING:
            return
        self.status = LobbyStatus.RUNNING

    def set_open(self) -> None:
        if self.kind != LobbyKind.TRAINING:
            return
        self.status = LobbyStatus.OPEN

    def pause(self) -> None:
        if self.kind != LobbyKind.TRAINING:
            raise InvariantViolationError("Пауза поддерживается только для training лобби")
        if self.status == LobbyStatus.PAUSED:
            return
        if self.status not in {LobbyStatus.OPEN, LobbyStatus.RUNNING}:
            raise InvariantViolationError("Пауза доступна только из open/running")
        self.status = LobbyStatus.PAUSED

    def reopen(self) -> None:
        if self.kind != LobbyKind.TRAINING:
            raise InvariantViolationError("Возобновление поддерживается только для training лобби")
        if self.status == LobbyStatus.OPEN:
            return
        if self.status not in {LobbyStatus.PAUSED, LobbyStatus.STOPPED}:
            raise InvariantViolationError("Возобновление доступно только из paused/stopped")
        self.status = LobbyStatus.OPEN

    def stop(self) -> None:
        if self.kind != LobbyKind.TRAINING:
            raise InvariantViolationError("Остановка поддерживается только для training лобби")
        if self.status == LobbyStatus.STOPPED:
            return
        if self.status not in {LobbyStatus.OPEN, LobbyStatus.RUNNING, LobbyStatus.PAUSED}:
            raise InvariantViolationError("Остановка доступна только из open/running/paused")
        self.status = LobbyStatus.STOPPED
        self.last_scheduled_run_ids = ()
        self.last_scheduled_match_groups = ()
        for team_state in self.teams.values():
            team_state.ready = False
            team_state.blocker_reason = "Лобби остановлено преподавателем"

    def close(self) -> None:
        if self.status == LobbyStatus.CLOSED:
            return
        if self.status == LobbyStatus.UPDATING:
            raise InvariantViolationError("Нельзя закрыть лобби во время обновления")
        self.status = LobbyStatus.CLOSED
        self.last_scheduled_run_ids = ()
        self.last_scheduled_match_groups = ()
        for team_state in self.teams.values():
            team_state.ready = False
            team_state.blocker_reason = "Лобби закрыто администратором"

    def set_last_scheduled_runs(self, run_ids: list[str]) -> None:
        self.last_scheduled_run_ids = tuple(run_ids)
        if not run_ids:
            self.last_scheduled_match_groups = ()

    def set_last_scheduled_match_groups(self, match_groups: list[list[str]]) -> None:
        normalized = tuple(tuple(run_id for run_id in group if run_id) for group in match_groups if group)
        self.last_scheduled_match_groups = normalized
        self.last_scheduled_run_ids = tuple(run_id for group in normalized for run_id in group)

    def set_game_version(self, version_id: str) -> None:
        self.game_version_id = version_id

    def update_settings(
        self,
        *,
        title: str | None = None,
        access: LobbyAccess | None = None,
        access_code: str | None = None,
        max_teams: int | None = None,
        auto_delete_training_runs_days: int | None | object = _UNSET,
    ) -> None:
        if title is not None:
            normalized_title = title.strip()
            if len(normalized_title) < 2:
                raise InvariantViolationError("Название лобби должно быть не короче 2 символов")
            self.title = normalized_title
        if max_teams is not None:
            if max_teams < len(self.teams):
                raise InvariantViolationError("Лимит игроков не может быть меньше текущего числа участников")
            self.max_teams = max_teams
        if access is not None:
            self.access = access
        if access_code is not None:
            self.access_code = access_code.strip() or None
        if self.access == LobbyAccess.CODE and not self.access_code:
            raise InvariantViolationError("Для закрытого лобби нужен код доступа")
        if self.access == LobbyAccess.PUBLIC:
            self.access_code = None
        if auto_delete_training_runs_days is not _UNSET:
            if not isinstance(auto_delete_training_runs_days, int) and auto_delete_training_runs_days is not None:
                raise InvariantViolationError("Срок хранения матчей должен быть числом дней")
            if isinstance(auto_delete_training_runs_days, int) and not 1 <= auto_delete_training_runs_days <= 3650:
                raise InvariantViolationError("Срок хранения матчей должен быть от 1 до 3650 дней")
            self.auto_delete_training_runs_days = auto_delete_training_runs_days

    def revalidate_ready_states(self, compatibility_by_team: dict[str, tuple[bool, str | None]]) -> None:
        for team_id, state in self.teams.items():
            compatible, reason = compatibility_by_team.get(team_id, (False, "Команда не проверена"))
            if not compatible and state.ready:
                state.ready = False
            if compatible:
                state.blocker_reason = None
            else:
                state.blocker_reason = reason
