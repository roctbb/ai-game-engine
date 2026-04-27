from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from team_workspace.domain.model import Team, TeamSlotCode, TeamSnapshot
from team_workspace.infrastructure.sqlalchemy_models import WorkspaceTeamOrm, WorkspaceTeamSnapshotOrm


class SqlAlchemyTeamRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, team: Team) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_team_to_orm(team))

    def get(self, team_id: str) -> Team | None:
        with self._session_factory() as session:
            row = session.get(WorkspaceTeamOrm, team_id)
            return None if row is None else _map_team_from_orm(row)

    def list_by_game(self, game_id: str) -> list[Team]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkspaceTeamOrm)
                .where(WorkspaceTeamOrm.game_id == game_id)
                .order_by(WorkspaceTeamOrm.team_id)
            ).all()
            return [_map_team_from_orm(row) for row in rows]

    def list_by_game_and_captain(self, game_id: str, captain_user_id: str) -> list[Team]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkspaceTeamOrm)
                .where(WorkspaceTeamOrm.game_id == game_id)
                .where(WorkspaceTeamOrm.captain_user_id == captain_user_id)
                .order_by(WorkspaceTeamOrm.team_id)
            ).all()
            return [_map_team_from_orm(row) for row in rows]


class SqlAlchemyTeamSnapshotRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, snapshot: TeamSnapshot) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_snapshot_to_orm(snapshot))

    def get(self, snapshot_id: str) -> TeamSnapshot | None:
        with self._session_factory() as session:
            row = session.get(WorkspaceTeamSnapshotOrm, snapshot_id)
            return None if row is None else _map_snapshot_from_orm(row)

    def latest_for_team(self, team_id: str) -> TeamSnapshot | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(WorkspaceTeamSnapshotOrm)
                .where(WorkspaceTeamSnapshotOrm.team_id == team_id)
                .order_by(desc(WorkspaceTeamSnapshotOrm.created_at))
                .limit(1)
            )
            return None if row is None else _map_snapshot_from_orm(row)


def _map_team_to_orm(team: Team) -> WorkspaceTeamOrm:
    slots_json: dict[str, dict[str, object]] = {}
    for slot_key, slot in team.slots.items():
        slots_json[slot_key] = {
            "code": slot.code,
            "revision": slot.revision,
            "updated_at": slot.updated_at.isoformat(),
        }
    return WorkspaceTeamOrm(
        team_id=team.team_id,
        game_id=team.game_id,
        name=team.name,
        captain_user_id=team.captain_user_id,
        slots_json=slots_json,
    )


def _map_team_from_orm(row: WorkspaceTeamOrm) -> Team:
    slots: dict[str, TeamSlotCode] = {}
    for slot_key, raw in (row.slots_json or {}).items():
        updated_at_raw = raw.get("updated_at")
        updated_at = (
            datetime.fromisoformat(str(updated_at_raw))
            if isinstance(updated_at_raw, str)
            else datetime.now()
        )
        slots[slot_key] = TeamSlotCode(
            slot_key=slot_key,
            code=str(raw.get("code", "")),
            revision=int(raw.get("revision", 1)),
            updated_at=updated_at,
        )

    return Team(
        team_id=row.team_id,
        game_id=row.game_id,
        name=row.name,
        captain_user_id=row.captain_user_id,
        slots=slots,
    )


def _map_snapshot_to_orm(snapshot: TeamSnapshot) -> WorkspaceTeamSnapshotOrm:
    return WorkspaceTeamSnapshotOrm(
        snapshot_id=snapshot.snapshot_id,
        team_id=snapshot.team_id,
        game_id=snapshot.game_id,
        version_id=snapshot.version_id,
        codes_by_slot_json=snapshot.codes_by_slot,
        revisions_by_slot_json=snapshot.revisions_by_slot,
        created_at=snapshot.created_at,
    )


def _map_snapshot_from_orm(row: WorkspaceTeamSnapshotOrm) -> TeamSnapshot:
    return TeamSnapshot(
        snapshot_id=row.snapshot_id,
        team_id=row.team_id,
        game_id=row.game_id,
        version_id=row.version_id,
        codes_by_slot=dict(row.codes_by_slot_json or {}),
        revisions_by_slot={
            str(key): int(value) for key, value in (row.revisions_by_slot_json or {}).items()
        },
        created_at=row.created_at,
    )
