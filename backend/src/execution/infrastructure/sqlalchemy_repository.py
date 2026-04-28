from __future__ import annotations

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session, load_only, sessionmaker

from execution.domain.model import (
    BuildJob,
    BuildStatus,
    MatchExecution,
    MatchExecutionStatus,
    Run,
    RunKind,
    RunStatus,
    WorkerNode,
    WorkerStatus,
)
from execution.infrastructure.sqlalchemy_models import BuildOrm, MatchExecutionOrm, RunOrm, WorkerOrm


class SqlAlchemyRunRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, run: Run) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_run_to_orm(run))

    def get(self, run_id: str, *, include_result_payload: bool = True) -> Run | None:
        with self._session_factory() as session:
            if include_result_payload:
                row = session.get(RunOrm, run_id)
            else:
                row = session.scalar(
                    select(RunOrm)
                    .where(RunOrm.run_id == run_id)
                    .options(
                        load_only(
                            RunOrm.run_id,
                            RunOrm.team_id,
                            RunOrm.game_id,
                            RunOrm.requested_by,
                            RunOrm.run_kind,
                            RunOrm.lobby_id,
                            RunOrm.target_version_id,
                            RunOrm.match_execution_id,
                            RunOrm.match_primary_run_id,
                            RunOrm.status,
                            RunOrm.snapshot_id,
                            RunOrm.snapshot_version_id,
                            RunOrm.revisions_by_slot,
                            RunOrm.worker_id,
                            RunOrm.active_lease_id,
                            RunOrm.created_at,
                            RunOrm.queued_at,
                            RunOrm.started_at,
                            RunOrm.finished_at,
                            RunOrm.error_message,
                        )
                    )
                )
            return None if row is None else _map_run_from_orm(row, include_result_payload=include_result_payload)

    def list(self) -> list[Run]:
        with self._session_factory() as session:
            rows = session.scalars(select(RunOrm).order_by(desc(RunOrm.created_at))).all()
            return [_map_run_from_orm(row) for row in rows]

    def list_filtered(
        self,
        *,
        team_id: str | None = None,
        game_id: str | None = None,
        lobby_id: str | None = None,
        run_kind: RunKind | None = None,
        status: RunStatus | None = None,
        requested_by: str | None = None,
        include_result_payload: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Run]:
        statement = select(RunOrm).order_by(desc(RunOrm.created_at))
        if team_id is not None:
            statement = statement.where(RunOrm.team_id == team_id)
        if game_id is not None:
            statement = statement.where(RunOrm.game_id == game_id)
        if lobby_id is not None:
            statement = statement.where(RunOrm.lobby_id == lobby_id)
        if run_kind is not None:
            statement = statement.where(RunOrm.run_kind == run_kind.value)
        if status is not None:
            statement = statement.where(RunOrm.status == status.value)
        if requested_by is not None:
            statement = statement.where(RunOrm.requested_by == requested_by)
        if not include_result_payload:
            statement = statement.options(
                load_only(
                    RunOrm.run_id,
                    RunOrm.team_id,
                    RunOrm.game_id,
                    RunOrm.requested_by,
                    RunOrm.run_kind,
                    RunOrm.lobby_id,
                    RunOrm.target_version_id,
                    RunOrm.match_execution_id,
                    RunOrm.match_primary_run_id,
                    RunOrm.status,
                    RunOrm.snapshot_id,
                    RunOrm.snapshot_version_id,
                    RunOrm.revisions_by_slot,
                    RunOrm.worker_id,
                    RunOrm.active_lease_id,
                    RunOrm.created_at,
                    RunOrm.queued_at,
                    RunOrm.started_at,
                    RunOrm.finished_at,
                    RunOrm.error_message,
                )
            )
        if offset is not None and offset > 0:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        with self._session_factory() as session:
            rows = session.scalars(statement).all()
            return [
                _map_run_from_orm(row, include_result_payload=include_result_payload)
                for row in rows
            ]

    def list_active_by_requested_by_and_kind(
        self, requested_by: str, run_kind: RunKind
    ) -> list[Run]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RunOrm)
                .where(RunOrm.requested_by == requested_by)
                .where(RunOrm.run_kind == run_kind.value)
                .where(
                    RunOrm.status.in_(
                        [
                            RunStatus.CREATED.value,
                            RunStatus.QUEUED.value,
                            RunStatus.RUNNING.value,
                        ]
                    )
                )
                .order_by(desc(RunOrm.created_at))
            ).all()
            return [_map_run_from_orm(row) for row in rows]

    def delete_many(self, run_ids: list[str]) -> None:
        if not run_ids:
            return
        with self._session_factory.begin() as session:
            session.execute(delete(RunOrm).where(RunOrm.run_id.in_(run_ids)))


class SqlAlchemyMatchExecutionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, match: MatchExecution) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_match_to_orm(match))

    def get(self, match_execution_id: str, *, include_result_payload: bool = True) -> MatchExecution | None:
        with self._session_factory() as session:
            if include_result_payload:
                row = session.get(MatchExecutionOrm, match_execution_id)
            else:
                row = session.scalar(
                    select(MatchExecutionOrm)
                    .where(MatchExecutionOrm.match_execution_id == match_execution_id)
                    .options(
                        load_only(
                            MatchExecutionOrm.match_execution_id,
                            MatchExecutionOrm.primary_run_id,
                            MatchExecutionOrm.run_ids,
                            MatchExecutionOrm.game_id,
                            MatchExecutionOrm.run_kind,
                            MatchExecutionOrm.lobby_id,
                            MatchExecutionOrm.status,
                            MatchExecutionOrm.worker_id,
                            MatchExecutionOrm.created_at,
                            MatchExecutionOrm.queued_at,
                            MatchExecutionOrm.started_at,
                            MatchExecutionOrm.finished_at,
                            MatchExecutionOrm.error_message,
                        )
                    )
                )
            return None if row is None else _map_match_from_orm(row, include_result_payload=include_result_payload)

    def find_by_run_id(self, run_id: str, *, include_result_payload: bool = True) -> MatchExecution | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(MatchExecutionOrm)
                .where(MatchExecutionOrm.run_ids.contains([run_id]))
                .order_by(desc(MatchExecutionOrm.created_at))
            )
            if row is None:
                row = session.scalar(
                    select(MatchExecutionOrm)
                    .where(MatchExecutionOrm.primary_run_id == run_id)
                    .order_by(desc(MatchExecutionOrm.created_at))
                )
            return None if row is None else _map_match_from_orm(row, include_result_payload=include_result_payload)

    def delete_many(self, match_execution_ids: list[str]) -> None:
        if not match_execution_ids:
            return
        with self._session_factory.begin() as session:
            session.execute(
                delete(MatchExecutionOrm).where(
                    MatchExecutionOrm.match_execution_id.in_(match_execution_ids)
                )
            )


class SqlAlchemyWorkerRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, worker: WorkerNode) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_worker_to_orm(worker))

    def get(self, worker_id: str) -> WorkerNode | None:
        with self._session_factory() as session:
            row = session.get(WorkerOrm, worker_id)
            return None if row is None else _map_worker_from_orm(row)

    def list(self) -> list[WorkerNode]:
        with self._session_factory() as session:
            rows = session.scalars(select(WorkerOrm).order_by(WorkerOrm.worker_id)).all()
            return [_map_worker_from_orm(row) for row in rows]


class SqlAlchemyBuildRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, build: BuildJob) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_build_to_orm(build))

    def get(self, build_id: str) -> BuildJob | None:
        with self._session_factory() as session:
            row = session.get(BuildOrm, build_id)
            return None if row is None else _map_build_from_orm(row)


def _map_run_to_orm(run: Run) -> RunOrm:
    return RunOrm(
        run_id=run.run_id,
        team_id=run.team_id,
        game_id=run.game_id,
        requested_by=run.requested_by,
        run_kind=run.run_kind.value,
        lobby_id=run.lobby_id,
        target_version_id=run.target_version_id,
        match_execution_id=run.match_execution_id,
        match_primary_run_id=run.match_primary_run_id,
        status=run.status.value,
        snapshot_id=run.snapshot_id,
        snapshot_version_id=run.snapshot_version_id,
        revisions_by_slot=run.revisions_by_slot,
        worker_id=run.worker_id,
        active_lease_id=run.active_lease_id,
        created_at=run.created_at,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        result_payload=run.result_payload,
        error_message=run.error_message,
    )


def _map_run_from_orm(row: RunOrm, *, include_result_payload: bool = True) -> Run:
    return Run(
        run_id=row.run_id,
        team_id=row.team_id,
        game_id=row.game_id,
        requested_by=row.requested_by,
        run_kind=RunKind(row.run_kind),
        lobby_id=row.lobby_id,
        target_version_id=row.target_version_id,
        match_execution_id=row.match_execution_id,
        match_primary_run_id=row.match_primary_run_id,
        status=RunStatus(row.status),
        snapshot_id=row.snapshot_id,
        snapshot_version_id=row.snapshot_version_id,
        revisions_by_slot=dict(row.revisions_by_slot or {}),
        worker_id=row.worker_id,
        active_lease_id=row.active_lease_id,
        created_at=row.created_at,
        queued_at=row.queued_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        result_payload=row.result_payload if include_result_payload else None,
        error_message=row.error_message,
    )


def _map_match_to_orm(match: MatchExecution) -> MatchExecutionOrm:
    return MatchExecutionOrm(
        match_execution_id=match.match_execution_id,
        primary_run_id=match.primary_run_id,
        run_ids=list(match.run_ids),
        game_id=match.game_id,
        run_kind=match.run_kind.value,
        lobby_id=match.lobby_id,
        status=match.status.value,
        worker_id=match.worker_id,
        created_at=match.created_at,
        queued_at=match.queued_at,
        started_at=match.started_at,
        finished_at=match.finished_at,
        result_payload=match.result_payload,
        error_message=match.error_message,
    )


def _map_match_from_orm(row: MatchExecutionOrm, *, include_result_payload: bool = True) -> MatchExecution:
    return MatchExecution(
        match_execution_id=row.match_execution_id,
        primary_run_id=row.primary_run_id,
        run_ids=tuple(str(run_id) for run_id in (row.run_ids or [])),
        game_id=row.game_id,
        run_kind=RunKind(row.run_kind),
        lobby_id=row.lobby_id,
        status=MatchExecutionStatus(row.status),
        worker_id=row.worker_id,
        created_at=row.created_at,
        queued_at=row.queued_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        result_payload=row.result_payload if include_result_payload else None,
        error_message=row.error_message,
    )


def _map_worker_to_orm(worker: WorkerNode) -> WorkerOrm:
    return WorkerOrm(
        worker_id=worker.worker_id,
        hostname=worker.hostname,
        capacity_total=worker.capacity_total,
        capacity_available=worker.capacity_available,
        status=worker.status.value,
        labels=worker.labels,
        last_heartbeat_at=worker.last_heartbeat_at,
    )


def _map_worker_from_orm(row: WorkerOrm) -> WorkerNode:
    return WorkerNode(
        worker_id=row.worker_id,
        hostname=row.hostname,
        capacity_total=row.capacity_total,
        capacity_available=row.capacity_available,
        status=WorkerStatus(row.status),
        labels=dict(row.labels or {}),
        last_heartbeat_at=row.last_heartbeat_at,
    )


def _map_build_to_orm(build: BuildJob) -> BuildOrm:
    return BuildOrm(
        build_id=build.build_id,
        game_source_id=build.game_source_id,
        repo_url=build.repo_url,
        status=build.status.value,
        image_digest=build.image_digest,
        error_message=build.error_message,
        created_at=build.created_at,
        updated_at=build.updated_at,
    )


def _map_build_from_orm(row: BuildOrm) -> BuildJob:
    return BuildJob(
        build_id=row.build_id,
        game_source_id=row.game_source_id,
        repo_url=row.repo_url,
        status=BuildStatus(row.status),
        image_digest=row.image_digest,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
