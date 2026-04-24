from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from administration.domain.model import GameSource, GameSourceStatus, GameSourceSync, GameSourceType, SyncStatus
from administration.infrastructure.sqlalchemy_models import GameSourceOrm, GameSourceSyncOrm


class SqlAlchemyGameSourceRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def save(self, source: GameSource) -> None:
        with self._session_factory() as session:
            session.merge(_map_source_to_orm(source))
            session.commit()

    def get(self, source_id: str) -> GameSource | None:
        with self._session_factory() as session:
            row = session.get(GameSourceOrm, source_id)
            return None if row is None else _map_source_from_orm(row)

    def list(self) -> list[GameSource]:
        with self._session_factory() as session:
            rows = session.execute(select(GameSourceOrm).order_by(GameSourceOrm.created_at)).scalars().all()
            return [_map_source_from_orm(row) for row in rows]

    def get_by_repo_url(self, repo_url: str, default_branch: str) -> GameSource | None:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(GameSourceOrm).where(
                        GameSourceOrm.repo_url == repo_url,
                        GameSourceOrm.default_branch == default_branch,
                    )
                )
                .scalars()
                .first()
            )
            return None if row is None else _map_source_from_orm(row)


class SqlAlchemyGameSourceSyncRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def save(self, sync: GameSourceSync) -> None:
        with self._session_factory() as session:
            session.merge(_map_sync_to_orm(sync))
            session.commit()

    def list_by_source(self, source_id: str) -> list[GameSourceSync]:
        with self._session_factory() as session:
            rows = (
                session.execute(
                    select(GameSourceSyncOrm)
                    .where(GameSourceSyncOrm.source_id == source_id)
                    .order_by(GameSourceSyncOrm.started_at.desc())
                )
                .scalars()
                .all()
            )
            return [_map_sync_from_orm(row) for row in rows]


def _map_source_to_orm(source: GameSource) -> GameSourceOrm:
    return GameSourceOrm(
        source_id=source.source_id,
        source_type=source.source_type.value,
        repo_url=source.repo_url,
        default_branch=source.default_branch,
        status=source.status.value,
        last_sync_status=source.last_sync_status.value,
        last_synced_commit_sha=source.last_synced_commit_sha,
        created_by=source.created_by,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _map_source_from_orm(row: GameSourceOrm) -> GameSource:
    return GameSource(
        source_id=row.source_id,
        source_type=GameSourceType(row.source_type),
        repo_url=row.repo_url,
        default_branch=row.default_branch,
        status=GameSourceStatus(row.status),
        last_sync_status=SyncStatus(row.last_sync_status),
        last_synced_commit_sha=row.last_synced_commit_sha,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _map_sync_to_orm(sync: GameSourceSync) -> GameSourceSyncOrm:
    return GameSourceSyncOrm(
        sync_id=sync.sync_id,
        source_id=sync.source_id,
        requested_by=sync.requested_by,
        status=sync.status.value,
        build_id=sync.build_id,
        image_digest=sync.image_digest,
        error_message=sync.error_message,
        commit_sha=sync.commit_sha,
        started_at=sync.started_at,
        finished_at=sync.finished_at,
    )


def _map_sync_from_orm(row: GameSourceSyncOrm) -> GameSourceSync:
    return GameSourceSync(
        sync_id=row.sync_id,
        source_id=row.source_id,
        requested_by=row.requested_by,
        status=SyncStatus(row.status),
        build_id=row.build_id,
        image_digest=row.image_digest,
        error_message=row.error_message,
        commit_sha=row.commit_sha,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )
