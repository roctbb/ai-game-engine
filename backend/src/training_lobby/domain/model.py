from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from shared.kernel import InvariantViolationError, NotFoundError, new_id, utc_now


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
        if self.status != LobbyStatus.PAUSED:
            raise InvariantViolationError("Возобновление доступно только из paused")
        self.status = LobbyStatus.OPEN

    def close(self) -> None:
        if self.status == LobbyStatus.CLOSED:
            return
        if self.status == LobbyStatus.UPDATING:
            raise InvariantViolationError("Нельзя закрыть лобби во время обновления")
        self.status = LobbyStatus.CLOSED
        self.last_scheduled_run_ids = ()
        for team_state in self.teams.values():
            team_state.ready = False
            team_state.blocker_reason = "Лобби закрыто администратором"

    def set_last_scheduled_runs(self, run_ids: list[str]) -> None:
        self.last_scheduled_run_ids = tuple(run_ids)

    def set_game_version(self, version_id: str) -> None:
        self.game_version_id = version_id

    def revalidate_ready_states(self, compatibility_by_team: dict[str, tuple[bool, str | None]]) -> None:
        for team_id, state in self.teams.items():
            compatible, reason = compatibility_by_team.get(team_id, (False, "Команда не проверена"))
            if not compatible and state.ready:
                state.ready = False
            if compatible:
                state.blocker_reason = None
            else:
                state.blocker_reason = reason
