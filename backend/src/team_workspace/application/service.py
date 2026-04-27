from __future__ import annotations

from dataclasses import dataclass

from game_catalog.application.service import GameCatalogService
from team_workspace.application.repositories import TeamRepository, TeamSnapshotRepository
from team_workspace.domain.model import Team, TeamCompatibility, TeamSnapshot
from shared.kernel import NotFoundError


@dataclass(frozen=True, slots=True)
class TeamSlotState:
    slot_key: str
    state: str
    required: bool
    code: str | None
    revision: int | None


@dataclass(frozen=True, slots=True)
class TeamWorkspaceView:
    team_id: str
    game_id: str
    captain_user_id: str
    version_id: str
    slot_states: tuple[TeamSlotState, ...]


class TeamWorkspaceService:
    def __init__(
        self,
        team_repository: TeamRepository,
        snapshot_repository: TeamSnapshotRepository,
        game_catalog: GameCatalogService,
    ) -> None:
        self._team_repository = team_repository
        self._snapshot_repository = snapshot_repository
        self._game_catalog = game_catalog

    def create_team(self, game_id: str, name: str, captain_user_id: str) -> Team:
        self._game_catalog.get_game(game_id)
        existing = self.list_teams_by_game_and_captain(game_id=game_id, captain_user_id=captain_user_id)
        if existing:
            return existing[0]
        team = Team.create(game_id=game_id, name=name, captain_user_id=captain_user_id)
        self._team_repository.save(team)
        return team

    def get_team(self, team_id: str) -> Team:
        team = self._team_repository.get(team_id)
        if team is None:
            raise NotFoundError(f"Команда {team_id} не найдена")
        return team

    def list_teams_by_game(self, game_id: str) -> tuple[Team, ...]:
        return tuple(self._team_repository.list_by_game(game_id))

    def list_teams_by_game_and_captain(self, game_id: str, captain_user_id: str) -> tuple[Team, ...]:
        teams = self._team_repository.list_by_game_and_captain(
            game_id=game_id,
            captain_user_id=captain_user_id,
        )
        teams.sort(key=lambda team: team.team_id)
        return tuple(teams)

    def get_or_create_personal_team(self, game_id: str, captain_user_id: str) -> Team:
        existing = self.list_teams_by_game_and_captain(game_id=game_id, captain_user_id=captain_user_id)
        if existing:
            return existing[0]
        return self.create_team(
            game_id=game_id,
            name=captain_user_id,
            captain_user_id=captain_user_id,
        )

    def update_slot_code(self, team_id: str, actor_user_id: str, slot_key: str, code: str) -> Team:
        team = self.get_team(team_id)
        team.update_slot_code(actor_user_id=actor_user_id, slot_key=slot_key, code=code)
        self._team_repository.save(team)
        return team

    def evaluate_compatibility(
        self,
        team_id: str,
        game_id: str,
        version_id: str | None = None,
    ) -> TeamCompatibility:
        team = self.get_team(team_id)
        version = self._game_catalog.get_version(game_id=game_id, version_id=version_id)
        return team.compatibility(version.required_slot_keys)

    def create_snapshot(
        self,
        team_id: str,
        game_id: str,
        version_id: str | None = None,
    ) -> TeamSnapshot:
        team = self.get_team(team_id)
        version = self._game_catalog.get_version(game_id=game_id, version_id=version_id)
        snapshot = team.create_snapshot(version_id=version.version_id, required_slot_keys=version.required_slot_keys)
        self._snapshot_repository.save(snapshot)
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> TeamSnapshot:
        snapshot = self._snapshot_repository.get(snapshot_id)
        if snapshot is None:
            raise NotFoundError(f"Snapshot {snapshot_id} не найден")
        return snapshot

    def get_workspace_view(self, team_id: str, version_id: str | None = None) -> TeamWorkspaceView:
        team = self.get_team(team_id)
        version = self._game_catalog.get_version(game_id=team.game_id, version_id=version_id)

        states: list[TeamSlotState] = []
        version_slot_keys: set[str] = set()
        for slot_def in version.required_slots:
            version_slot_keys.add(slot_def.key)
            slot = team.slots.get(slot_def.key)
            if slot is None or not slot.code.strip():
                state = "empty"
                revision = None
                code = None
            else:
                state = "filled"
                revision = slot.revision
                code = slot.code
            states.append(
                TeamSlotState(
                    slot_key=slot_def.key,
                    state=state,
                    required=slot_def.required,
                    code=code,
                    revision=revision,
                )
            )

        for slot_key, slot in sorted(team.slots.items()):
            if slot_key not in version_slot_keys:
                states.append(
                    TeamSlotState(
                        slot_key=slot_key,
                        state="incompatible",
                        required=False,
                        code=slot.code,
                        revision=slot.revision,
                    )
                )

        return TeamWorkspaceView(
            team_id=team.team_id,
            game_id=team.game_id,
            captain_user_id=team.captain_user_id,
            version_id=version.version_id,
            slot_states=tuple(states),
        )
