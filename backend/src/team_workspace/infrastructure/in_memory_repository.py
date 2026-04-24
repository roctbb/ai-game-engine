from __future__ import annotations

from team_workspace.domain.model import Team, TeamSnapshot


class InMemoryTeamRepository:
    def __init__(self) -> None:
        self._items: dict[str, Team] = {}

    def save(self, team: Team) -> None:
        self._items[team.team_id] = team

    def get(self, team_id: str) -> Team | None:
        return self._items.get(team_id)

    def list_by_game(self, game_id: str) -> list[Team]:
        return [team for team in self._items.values() if team.game_id == game_id]


class InMemoryTeamSnapshotRepository:
    def __init__(self) -> None:
        self._items: dict[str, TeamSnapshot] = {}
        self._last_by_team: dict[str, str] = {}

    def save(self, snapshot: TeamSnapshot) -> None:
        self._items[snapshot.snapshot_id] = snapshot
        self._last_by_team[snapshot.team_id] = snapshot.snapshot_id

    def get(self, snapshot_id: str) -> TeamSnapshot | None:
        return self._items.get(snapshot_id)

    def latest_for_team(self, team_id: str) -> TeamSnapshot | None:
        snapshot_id = self._last_by_team.get(team_id)
        if snapshot_id is None:
            return None
        return self._items.get(snapshot_id)
