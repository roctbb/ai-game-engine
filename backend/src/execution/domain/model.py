from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from team_workspace.domain.model import TeamSnapshot
from shared.kernel import InvariantViolationError, NotFoundError, new_id, utc_now


class RunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELED = "canceled"


class RunKind(StrEnum):
    SINGLE_TASK = "single_task"
    TRAINING_MATCH = "training_match"
    COMPETITION_MATCH = "competition_match"


class WorkerStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"
    DISABLED = "disabled"


class BuildStatus(StrEnum):
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"


class MatchExecutionStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(slots=True)
class Run:
    run_id: str
    team_id: str
    game_id: str
    requested_by: str
    run_kind: RunKind
    lobby_id: str | None = None
    target_version_id: str | None = None
    match_execution_id: str | None = None
    match_primary_run_id: str | None = None
    status: RunStatus = RunStatus.CREATED
    snapshot_id: str | None = None
    snapshot_version_id: str | None = None
    revisions_by_slot: dict[str, int] = field(default_factory=dict)
    worker_id: str | None = None
    active_lease_id: str | None = None
    created_at: object = field(default_factory=utc_now)
    queued_at: object | None = None
    started_at: object | None = None
    finished_at: object | None = None
    result_payload: dict[str, object] | None = None
    result_summary: dict[str, object] | None = None
    error_message: str | None = None

    @staticmethod
    def create(
        team_id: str,
        game_id: str,
        requested_by: str,
        run_kind: RunKind,
        lobby_id: str | None = None,
        target_version_id: str | None = None,
    ) -> "Run":
        return Run(
            run_id=new_id("run"),
            team_id=team_id,
            game_id=game_id,
            requested_by=requested_by,
            run_kind=run_kind,
            lobby_id=lobby_id,
            target_version_id=target_version_id,
        )

    def queue_with_snapshot(self, snapshot: TeamSnapshot) -> None:
        if self.status != RunStatus.CREATED:
            raise InvariantViolationError("Snapshot можно фиксировать только при переходе created->queued")
        if snapshot.team_id != self.team_id:
            raise InvariantViolationError("Snapshot не принадлежит команде запуска")
        self.snapshot_id = snapshot.snapshot_id
        self.snapshot_version_id = snapshot.version_id
        self.revisions_by_slot = dict(snapshot.revisions_by_slot)
        self.status = RunStatus.QUEUED
        self.queued_at = utc_now()

    def mark_accepted(self, worker_id: str, lease_id: str) -> None:
        if self.status != RunStatus.QUEUED:
            raise InvariantViolationError("Запуск можно принять только из queued")
        if not lease_id:
            raise InvariantViolationError("lease_id обязателен для принятия запуска")
        self.worker_id = worker_id
        self.active_lease_id = lease_id

    def mark_started(self, worker_id: str, lease_id: str | None = None) -> None:
        if self.status != RunStatus.QUEUED:
            raise InvariantViolationError("Запуск можно стартовать только из queued")
        self.require_active_lease(worker_id=worker_id, lease_id=lease_id)
        self.status = RunStatus.RUNNING
        self.worker_id = worker_id
        if lease_id:
            self.active_lease_id = lease_id
        self.started_at = utc_now()

    def mark_finished(self, payload: dict[str, object]) -> None:
        if self.status not in {RunStatus.RUNNING, RunStatus.QUEUED}:
            raise InvariantViolationError("Запуск нельзя завершить из текущего статуса")
        self.status = RunStatus.FINISHED
        self.result_payload = payload
        self.finished_at = utc_now()

    def mark_failed(self, message: str) -> None:
        if self.status not in {RunStatus.RUNNING, RunStatus.QUEUED}:
            raise InvariantViolationError("Запуск нельзя перевести в failed из текущего статуса")
        self.status = RunStatus.FAILED
        self.error_message = message
        self.finished_at = utc_now()

    def mark_canceled(self, message: str | None = None) -> None:
        if self.status not in {RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING}:
            raise InvariantViolationError("Запуск нельзя отменить из текущего статуса")
        self.status = RunStatus.CANCELED
        self.error_message = message
        self.finished_at = utc_now()

    def require_active_lease(self, worker_id: str | None, lease_id: str | None) -> None:
        if self.active_lease_id is None:
            return
        if not lease_id or lease_id != self.active_lease_id:
            raise InvariantViolationError("Устаревший или некорректный lease_id запуска")
        if self.worker_id is not None and worker_id is not None and self.worker_id != worker_id:
            raise InvariantViolationError("Запуск закреплен за другим worker")


@dataclass(slots=True)
class MatchExecution:
    match_execution_id: str
    primary_run_id: str
    run_ids: tuple[str, ...]
    game_id: str
    run_kind: RunKind
    lobby_id: str | None
    status: MatchExecutionStatus
    worker_id: str | None = None
    created_at: object = field(default_factory=utc_now)
    queued_at: object | None = None
    started_at: object | None = None
    finished_at: object | None = None
    result_payload: dict[str, object] | None = None
    error_message: str | None = None

    @staticmethod
    def create(
        *,
        primary_run_id: str,
        run_ids: list[str],
        game_id: str,
        run_kind: RunKind,
        lobby_id: str | None,
    ) -> "MatchExecution":
        normalized = tuple(dict.fromkeys(run_ids))
        if not normalized:
            raise InvariantViolationError("MatchExecution требует хотя бы один run")
        if primary_run_id not in normalized:
            raise InvariantViolationError("Primary run должен входить в MatchExecution")
        return MatchExecution(
            match_execution_id=new_id("match"),
            primary_run_id=primary_run_id,
            run_ids=normalized,
            game_id=game_id,
            run_kind=run_kind,
            lobby_id=lobby_id,
            status=MatchExecutionStatus.CREATED,
        )

    def mark_queued(self) -> None:
        if self.status is not MatchExecutionStatus.CREATED:
            raise InvariantViolationError("Матч можно поставить в очередь только из created")
        self.status = MatchExecutionStatus.QUEUED
        self.queued_at = utc_now()

    def mark_accepted(self, worker_id: str) -> None:
        if self.status is not MatchExecutionStatus.QUEUED:
            raise InvariantViolationError("Матч можно принять только из queued")
        if self.worker_id is not None and self.worker_id != worker_id:
            raise InvariantViolationError("Матч уже принят другим worker")
        self.worker_id = worker_id

    def mark_started(self, worker_id: str) -> None:
        if self.status is not MatchExecutionStatus.QUEUED:
            raise InvariantViolationError("Матч можно стартовать только из queued")
        if self.worker_id is not None and self.worker_id != worker_id:
            raise InvariantViolationError("Матч уже закреплен за другим worker")
        self.status = MatchExecutionStatus.RUNNING
        self.worker_id = worker_id
        self.started_at = utc_now()

    def mark_finished(self, payload: dict[str, object]) -> None:
        if self.status not in {MatchExecutionStatus.QUEUED, MatchExecutionStatus.RUNNING}:
            raise InvariantViolationError("Матч нельзя завершить из текущего статуса")
        self.status = MatchExecutionStatus.FINISHED
        self.result_payload = payload
        self.finished_at = utc_now()

    def mark_failed(self, message: str) -> None:
        if self.status not in {MatchExecutionStatus.CREATED, MatchExecutionStatus.QUEUED, MatchExecutionStatus.RUNNING}:
            raise InvariantViolationError("Матч нельзя перевести в failed из текущего статуса")
        self.status = MatchExecutionStatus.FAILED
        self.error_message = message
        self.finished_at = utc_now()

    def mark_canceled(self, message: str | None = None) -> None:
        if self.status not in {MatchExecutionStatus.CREATED, MatchExecutionStatus.QUEUED, MatchExecutionStatus.RUNNING}:
            raise InvariantViolationError("Матч нельзя отменить из текущего статуса")
        self.status = MatchExecutionStatus.CANCELED
        self.error_message = message
        self.finished_at = utc_now()


@dataclass(slots=True)
class WorkerNode:
    worker_id: str
    hostname: str
    capacity_total: int
    capacity_available: int
    status: WorkerStatus
    labels: dict[str, str]
    last_heartbeat_at: object

    @staticmethod
    def register(worker_id: str, hostname: str, capacity_total: int, labels: dict[str, str]) -> "WorkerNode":
        return WorkerNode(
            worker_id=worker_id,
            hostname=hostname,
            capacity_total=capacity_total,
            capacity_available=capacity_total,
            status=WorkerStatus.ONLINE,
            labels=labels,
            last_heartbeat_at=utc_now(),
        )

    def refresh_registration(self, hostname: str, capacity_total: int, labels: dict[str, str]) -> None:
        if capacity_total <= 0:
            raise InvariantViolationError("capacity_total должен быть положительным")
        self.hostname = hostname
        self.capacity_total = capacity_total
        self.capacity_available = min(self.capacity_available, self.capacity_total)
        self.labels = labels
        self.last_heartbeat_at = utc_now()

    def heartbeat(self, capacity_available: int) -> None:
        if capacity_available < 0 or capacity_available > self.capacity_total:
            raise InvariantViolationError("Некорректный available capacity")
        self.capacity_available = capacity_available
        self.last_heartbeat_at = utc_now()
        if self.status is WorkerStatus.OFFLINE:
            self.status = WorkerStatus.ONLINE

    def set_status(self, status: WorkerStatus) -> None:
        self.status = status
        self.last_heartbeat_at = utc_now()


@dataclass(slots=True)
class BuildJob:
    build_id: str
    game_source_id: str
    repo_url: str
    status: BuildStatus
    image_digest: str | None = None
    error_message: str | None = None
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)

    @staticmethod
    def start(game_source_id: str, repo_url: str) -> "BuildJob":
        return BuildJob(
            build_id=new_id("build"),
            game_source_id=game_source_id,
            repo_url=repo_url,
            status=BuildStatus.STARTED,
        )

    def mark_finished(self, image_digest: str) -> None:
        self.status = BuildStatus.FINISHED
        self.image_digest = image_digest
        self.updated_at = utc_now()

    def mark_failed(self, error_message: str) -> None:
        self.status = BuildStatus.FAILED
        self.error_message = error_message
        self.updated_at = utc_now()


def require_run(value: Run | None, run_id: str) -> Run:
    if value is None:
        raise NotFoundError(f"Run {run_id} не найден")
    return value


def require_match_execution(value: MatchExecution | None, match_execution_id: str) -> MatchExecution:
    if value is None:
        raise NotFoundError(f"MatchExecution {match_execution_id} не найден")
    return value


def require_worker(value: WorkerNode | None, worker_id: str) -> WorkerNode:
    if value is None:
        raise NotFoundError(f"Worker {worker_id} не найден")
    return value


def require_build(value: BuildJob | None, build_id: str) -> BuildJob:
    if value is None:
        raise NotFoundError(f"Build {build_id} не найден")
    return value
