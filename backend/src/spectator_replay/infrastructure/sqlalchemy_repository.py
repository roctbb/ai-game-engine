from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from execution.domain.model import RunKind, RunStatus
from spectator_replay.domain.model import ReplayRecord, ReplayVisibility
from spectator_replay.infrastructure.sqlalchemy_models import ReplayOrm


class SqlAlchemyReplayRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, replay: ReplayRecord) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_replay_to_orm(replay))

    def get_by_run_id(self, run_id: str) -> ReplayRecord | None:
        with self._session_factory() as session:
            row = session.scalar(select(ReplayOrm).where(ReplayOrm.run_id == run_id))
            return None if row is None else _map_replay_from_orm(row)

    def list(self, game_id: str | None = None, run_kind: RunKind | None = None, limit: int = 50) -> list[ReplayRecord]:
        with self._session_factory() as session:
            query = select(ReplayOrm)
            if game_id is not None:
                query = query.where(ReplayOrm.game_id == game_id)
            if run_kind is not None:
                query = query.where(ReplayOrm.run_kind == run_kind.value)
            query = query.order_by(desc(ReplayOrm.updated_at)).limit(limit)
            rows = session.scalars(query).all()
            return [_map_replay_from_orm(row) for row in rows]


def _map_replay_to_orm(replay: ReplayRecord) -> ReplayOrm:
    return ReplayOrm(
        replay_id=replay.replay_id,
        run_id=replay.run_id,
        game_id=replay.game_id,
        run_kind=replay.run_kind.value,
        status=replay.status.value,
        visibility=replay.visibility.value,
        frames_json=list(replay.frames),
        events_json=list(replay.events),
        summary_json=dict(replay.summary),
        created_at=replay.created_at,
        updated_at=replay.updated_at,
    )


def _map_replay_from_orm(row: ReplayOrm) -> ReplayRecord:
    return ReplayRecord(
        replay_id=row.replay_id,
        run_id=row.run_id,
        game_id=row.game_id,
        run_kind=RunKind(row.run_kind),
        status=RunStatus(row.status),
        visibility=ReplayVisibility(row.visibility),
        frames=[dict(item) for item in (row.frames_json or []) if isinstance(item, dict)],
        events=[dict(item) for item in (row.events_json or []) if isinstance(item, dict)],
        summary=dict(row.summary_json or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

