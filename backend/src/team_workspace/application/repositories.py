from __future__ import annotations

from typing import Protocol

from team_workspace.domain.model import Team, TeamSnapshot


class TeamRepository(Protocol):
    def save(self, team: Team) -> None:
        ...

    def get(self, team_id: str) -> Team | None:
        ...

    def list_by_game(self, game_id: str) -> list[Team]:
        ...


class TeamSnapshotRepository(Protocol):
    def save(self, snapshot: TeamSnapshot) -> None:
        ...

    def get(self, snapshot_id: str) -> TeamSnapshot | None:
        ...

    def latest_for_team(self, team_id: str) -> TeamSnapshot | None:
        ...
