from __future__ import annotations

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session, load_only, sessionmaker

from execution.domain.model import RunKind, RunStatus
from spectator_replay.domain.model import ReplayRecord, ReplayVisibility
from spectator_replay.infrastructure.sqlalchemy_models import ReplayOrm


class SqlAlchemyReplayRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, replay: ReplayRecord) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_replay_to_orm(replay))

    def get_by_run_id(self, run_id: str, *, include_content: bool = True) -> ReplayRecord | None:
        with self._session_factory() as session:
            query = select(ReplayOrm).where(ReplayOrm.run_id == run_id)
            if not include_content:
                query = query.options(
                    load_only(
                        ReplayOrm.replay_id,
                        ReplayOrm.run_id,
                        ReplayOrm.game_id,
                        ReplayOrm.run_kind,
                        ReplayOrm.status,
                        ReplayOrm.visibility,
                        ReplayOrm.summary_json,
                        ReplayOrm.created_at,
                        ReplayOrm.updated_at,
                    )
                )
            row = session.scalar(query)
            return None if row is None else _map_replay_from_orm(row, include_content=include_content)

    def list(
        self,
        game_id: str | None = None,
        run_kind: RunKind | None = None,
        limit: int = 50,
        include_content: bool = True,
    ) -> list[ReplayRecord]:
        with self._session_factory() as session:
            query = select(ReplayOrm)
            if game_id is not None:
                query = query.where(ReplayOrm.game_id == game_id)
            if run_kind is not None:
                query = query.where(ReplayOrm.run_kind == run_kind.value)
            if not include_content:
                query = query.options(
                    load_only(
                        ReplayOrm.replay_id,
                        ReplayOrm.run_id,
                        ReplayOrm.game_id,
                        ReplayOrm.run_kind,
                        ReplayOrm.status,
                        ReplayOrm.visibility,
                        ReplayOrm.summary_json,
                        ReplayOrm.created_at,
                        ReplayOrm.updated_at,
                    )
                )
            query = query.order_by(desc(ReplayOrm.updated_at)).limit(limit)
            rows = session.scalars(query).all()
            return [_map_replay_from_orm(row, include_content=include_content) for row in rows]

    def delete_by_run_ids(self, run_ids: list[str]) -> None:
        if not run_ids:
            return
        with self._session_factory.begin() as session:
            session.execute(delete(ReplayOrm).where(ReplayOrm.run_id.in_(run_ids)))


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


def _map_replay_from_orm(row: ReplayOrm, *, include_content: bool = True) -> ReplayRecord:
    return ReplayRecord(
        replay_id=row.replay_id,
        run_id=row.run_id,
        game_id=row.game_id,
        run_kind=RunKind(row.run_kind),
        status=RunStatus(row.status),
        visibility=ReplayVisibility(row.visibility),
        frames=[dict(item) for item in (row.frames_json or []) if isinstance(item, dict)]
        if include_content
        else [],
        events=[dict(item) for item in (row.events_json or []) if isinstance(item, dict)]
        if include_content
        else [],
        summary=dict(row.summary_json or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
