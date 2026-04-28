from __future__ import annotations

from dataclasses import dataclass

from execution.application.replay_recorder import NoopRunReplayRecorder, RunReplayRecorder
from execution.application.repositories import BuildRepository, MatchExecutionRepository, RunRepository, WorkerRepository
from execution.application.scheduler_gateway import SchedulerGateway
from execution.domain.model import (
    BuildJob,
    MatchExecution,
    MatchExecutionStatus,
    Run,
    RunKind,
    RunStatus,
    WorkerStatus,
    WorkerNode,
    require_build,
    require_match_execution,
    require_run,
    require_worker,
)
from execution.domain.result_contract import validate_result_payload
from execution.domain.result_payload import result_summary_from_payload
from game_catalog.application.service import GameCatalogService
from shared.kernel import ConflictError, ExternalServiceError, InvariantViolationError
from team_workspace.application.service import TeamWorkspaceService


_SINGLE_TASK_BLOCKING_STATUSES = {RunStatus.QUEUED, RunStatus.RUNNING}
_SHADOW_WORKER_PREFIX = "shadow:"


@dataclass(slots=True)
class CreateRunInput:
    team_id: str
    game_id: str
    requested_by: str
    run_kind: RunKind
    lobby_id: str | None = None
    version_id: str | None = None


@dataclass(slots=True)
class RegisterWorkerInput:
    worker_id: str
    hostname: str
    capacity_total: int
    labels: dict[str, str]


@dataclass(slots=True)
class UpdateWorkerStatusInput:
    worker_id: str
    status: WorkerStatus


class ExecutionService:
    def __init__(
        self,
        run_repository: RunRepository,
        match_execution_repository: MatchExecutionRepository,
        worker_repository: WorkerRepository,
        build_repository: BuildRepository,
        scheduler_gateway: SchedulerGateway,
        workspace_service: TeamWorkspaceService,
        game_catalog: GameCatalogService,
        run_replay_recorder: RunReplayRecorder | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._match_execution_repository = match_execution_repository
        self._worker_repository = worker_repository
        self._build_repository = build_repository
        self._scheduler_gateway = scheduler_gateway
        self._workspace_service = workspace_service
        self._game_catalog = game_catalog
        self._run_replay_recorder = run_replay_recorder or NoopRunReplayRecorder()

    def create_run(self, data: CreateRunInput) -> Run:
        team = self._workspace_service.get_team(data.team_id)
        if team.game_id != data.game_id:
            raise InvariantViolationError("team_id и game_id запуска не согласованы")
        if data.version_id is not None:
            self._game_catalog.get_version(game_id=data.game_id, version_id=data.version_id)
        if data.run_kind is RunKind.SINGLE_TASK:
            self._ensure_single_task_can_be_queued(requested_by=data.requested_by)
        run = Run.create(
            team_id=data.team_id,
            game_id=data.game_id,
            requested_by=data.requested_by,
            run_kind=data.run_kind,
            lobby_id=data.lobby_id,
            target_version_id=data.version_id,
        )
        self._run_repository.save(run)
        return run

    def queue_run(self, run_id: str) -> Run:
        run = require_run(self._run_repository.get(run_id), run_id)
        if run.run_kind is RunKind.SINGLE_TASK:
            self._ensure_single_task_can_be_queued(requested_by=run.requested_by, exclude_run_id=run.run_id)
        try:
            snapshot = self._workspace_service.create_snapshot(
                team_id=run.team_id,
                game_id=run.game_id,
                version_id=run.target_version_id,
            )
        except InvariantViolationError as exc:
            if run.status is RunStatus.CREATED:
                run.mark_canceled(message=f"snapshot_validation_failed: {exc}")
                self._run_repository.save(run)
            raise
        run.queue_with_snapshot(snapshot)
        self._run_repository.save(run)
        required_worker_labels = self._game_catalog.get_version(
            game_id=run.game_id,
            version_id=snapshot.version_id,
        ).required_worker_labels
        try:
            self._scheduler_gateway.schedule_run(
                run_id=run.run_id,
                required_worker_labels=required_worker_labels,
            )
        except ExternalServiceError as exc:
            run.mark_failed(message=f"Scheduler enqueue failed: {exc.message}")
            self._run_repository.save(run)
            raise
        return run

    def queue_match_group(self, run_ids: list[str]) -> MatchExecution:
        if not run_ids:
            raise InvariantViolationError("Нельзя поставить в очередь пустой матч")
        runs = [require_run(self._run_repository.get(run_id), run_id) for run_id in run_ids]
        primary_run = runs[0]
        if primary_run.run_kind is not RunKind.TRAINING_MATCH:
            raise InvariantViolationError("MatchExecution сейчас поддерживает только training_match")
        for run in runs:
            if run.run_kind is not primary_run.run_kind:
                raise InvariantViolationError("Все run в матче должны иметь один тип")
            if run.game_id != primary_run.game_id or run.lobby_id != primary_run.lobby_id:
                raise InvariantViolationError("Все run в матче должны принадлежать одной игре и лобби")
            if run.status is not RunStatus.CREATED:
                raise InvariantViolationError("Run можно добавить в MatchExecution только из created")

        snapshots = []
        for run in runs:
            try:
                snapshots.append(
                    self._workspace_service.create_snapshot(
                        team_id=run.team_id,
                        game_id=run.game_id,
                        version_id=run.target_version_id,
                    )
                )
            except InvariantViolationError as exc:
                if run.status is RunStatus.CREATED:
                    run.mark_canceled(message=f"snapshot_validation_failed: {exc}")
                    self._run_repository.save(run)
                raise

        match = MatchExecution.create(
            primary_run_id=primary_run.run_id,
            run_ids=[run.run_id for run in runs],
            game_id=primary_run.game_id,
            run_kind=primary_run.run_kind,
            lobby_id=primary_run.lobby_id,
        )
        match.mark_queued()
        self._match_execution_repository.save(match)

        for run, snapshot in zip(runs, snapshots, strict=True):
            run.queue_with_snapshot(snapshot)
            run.match_execution_id = match.match_execution_id
            run.match_primary_run_id = primary_run.run_id
            self._run_repository.save(run)

        required_worker_labels = self._game_catalog.get_version(
            game_id=primary_run.game_id,
            version_id=primary_run.snapshot_version_id,
        ).required_worker_labels
        try:
            self._scheduler_gateway.schedule_run(
                run_id=primary_run.run_id,
                required_worker_labels=required_worker_labels,
            )
        except ExternalServiceError as exc:
            primary_run.mark_failed(message=f"Scheduler enqueue failed: {exc.message}")
            self._run_repository.save(primary_run)
            match.mark_failed(message=f"Scheduler enqueue failed: {exc.message}")
            self._match_execution_repository.save(match)
            raise
        return match

    def queue_shadow_run(self, run_id: str, *, primary_run_id: str) -> Run:
        run = require_run(self._run_repository.get(run_id), run_id)
        if run.run_kind is not RunKind.TRAINING_MATCH:
            raise InvariantViolationError("Shadow-запуски поддерживаются только для training_match")
        try:
            snapshot = self._workspace_service.create_snapshot(
                team_id=run.team_id,
                game_id=run.game_id,
                version_id=run.target_version_id,
            )
        except InvariantViolationError as exc:
            if run.status is RunStatus.CREATED:
                run.mark_canceled(message=f"snapshot_validation_failed: {exc}")
                self._run_repository.save(run)
            raise
        run.queue_with_snapshot(snapshot)
        run.worker_id = f"{_SHADOW_WORKER_PREFIX}{primary_run_id}"
        self._run_repository.save(run)
        return run

    @staticmethod
    def is_shadow_of(run: Run, primary_run_id: str) -> bool:
        return (
            run.match_primary_run_id == primary_run_id
            and run.run_id != primary_run_id
        ) or run.worker_id == f"{_SHADOW_WORKER_PREFIX}{primary_run_id}"

    @staticmethod
    def is_shadow_run(run: Run) -> bool:
        if run.match_primary_run_id is not None:
            return run.run_id != run.match_primary_run_id
        return isinstance(run.worker_id, str) and run.worker_id.startswith(_SHADOW_WORKER_PREFIX)

    @staticmethod
    def primary_run_id_for_shadow(run: Run) -> str | None:
        if run.match_primary_run_id is not None and run.run_id != run.match_primary_run_id:
            return run.match_primary_run_id
        if isinstance(run.worker_id, str) and run.worker_id.startswith(_SHADOW_WORKER_PREFIX):
            primary_run_id = run.worker_id.removeprefix(_SHADOW_WORKER_PREFIX).strip()
            return primary_run_id or None
        return None

    def start_run(self, run_id: str, worker_id: str, lease_id: str | None = None) -> Run:
        run = require_run(self._run_repository.get(run_id), run_id)
        require_worker(self._worker_repository.get(worker_id), worker_id)
        if run.status is RunStatus.RUNNING and run.worker_id == worker_id and run.active_lease_id == lease_id:
            return run
        run.mark_started(worker_id=worker_id, lease_id=lease_id)
        self._run_repository.save(run)
        self._mark_primary_match_started(run=run, worker_id=worker_id)
        return run

    def accept_run(self, run_id: str, worker_id: str, lease_id: str) -> Run:
        run = require_run(self._run_repository.get(run_id), run_id)
        require_worker(self._worker_repository.get(worker_id), worker_id)
        if run.status is RunStatus.RUNNING and run.worker_id == worker_id and run.active_lease_id == lease_id:
            return run
        run.mark_accepted(worker_id=worker_id, lease_id=lease_id)
        self._run_repository.save(run)
        self._mark_primary_match_accepted(run=run, worker_id=worker_id)
        return run

    def finish_run(self, run_id: str, payload: dict[str, object], lease_id: str | None = None) -> Run:
        run = require_run(self._run_repository.get(run_id), run_id)
        if run.status is RunStatus.FINISHED:
            run.require_active_lease(worker_id=None, lease_id=lease_id)
            validate_result_payload(run_kind=run.run_kind, payload=payload)
            merged_payload = _merge_finished_payload(run.result_payload, payload)
            if merged_payload != run.result_payload:
                run.result_payload = merged_payload
                run.result_summary = result_summary_from_payload(merged_payload)
                self._run_repository.save(run)
                self._merge_primary_match_payload(run=run, payload=payload)
                self._run_replay_recorder.record_run(run)
            return run
        run.require_active_lease(worker_id=None, lease_id=lease_id)
        validate_result_payload(run_kind=run.run_kind, payload=payload)
        run.mark_finished(payload=payload)
        run.result_summary = result_summary_from_payload(payload)
        self._run_repository.save(run)
        self._mark_primary_match_finished(run=run, payload=payload)
        self._run_replay_recorder.record_run(run)
        return run

    def fail_run(self, run_id: str, message: str, lease_id: str | None = None) -> Run:
        run = require_run(self._run_repository.get(run_id), run_id)
        if run.status is RunStatus.FAILED:
            run.require_active_lease(worker_id=None, lease_id=lease_id)
            return run
        run.require_active_lease(worker_id=None, lease_id=lease_id)
        run.mark_failed(message=message)
        self._run_repository.save(run)
        self._mark_primary_match_failed(run=run, message=message)
        self._run_replay_recorder.record_run(run)
        return run

    def cancel_run(self, run_id: str, message: str | None = None) -> Run:
        run = require_run(self._run_repository.get(run_id), run_id)
        run.mark_canceled(message=message)
        self._run_repository.save(run)
        self._mark_primary_match_canceled(run=run, message=message)
        self._run_replay_recorder.record_run(run)
        return run

    def get_run(self, run_id: str, *, include_result_payload: bool = True) -> Run:
        return require_run(
            self._run_repository.get(run_id, include_result_payload=include_result_payload),
            run_id,
        )

    def list_runs(
        self,
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
        return self._run_repository.list_filtered(
            team_id=team_id,
            game_id=game_id,
            lobby_id=lobby_id,
            run_kind=run_kind,
            status=status,
            requested_by=requested_by,
            include_result_payload=include_result_payload,
            limit=limit,
            offset=offset,
        )

    def delete_runs(self, run_ids: list[str]) -> None:
        if not run_ids:
            return
        self._run_replay_recorder.delete_runs(run_ids)
        match_execution_ids = {
            run.match_execution_id
            for run_id in run_ids
            if (run := self._run_repository.get(run_id, include_result_payload=False)) is not None
            and run.match_execution_id is not None
        }
        self._run_repository.delete_many(run_ids)
        if match_execution_ids:
            self._match_execution_repository.delete_many(sorted(match_execution_ids))

    def delete_lobby_runs(self, lobby_id: str, run_kind: RunKind | None = None) -> list[str]:
        runs = self.list_runs(lobby_id=lobby_id, run_kind=run_kind, include_result_payload=False)
        run_ids = [run.run_id for run in runs]
        self.delete_runs(run_ids)
        return run_ids

    def register_worker(self, data: RegisterWorkerInput) -> WorkerNode:
        existing = self._worker_repository.get(data.worker_id)
        if existing is not None:
            existing.refresh_registration(
                hostname=data.hostname,
                capacity_total=data.capacity_total,
                labels=data.labels,
            )
            self._worker_repository.save(existing)
            return existing

        worker = WorkerNode.register(
            worker_id=data.worker_id,
            hostname=data.hostname,
            capacity_total=data.capacity_total,
            labels=data.labels,
        )
        self._worker_repository.save(worker)
        return worker

    def worker_heartbeat(self, worker_id: str, capacity_available: int) -> WorkerNode:
        worker = require_worker(self._worker_repository.get(worker_id), worker_id)
        worker.heartbeat(capacity_available=capacity_available)
        self._worker_repository.save(worker)
        return worker

    def update_worker_status(self, data: UpdateWorkerStatusInput) -> WorkerNode:
        worker = require_worker(self._worker_repository.get(data.worker_id), data.worker_id)
        worker.set_status(data.status)
        self._worker_repository.save(worker)
        return worker

    def list_workers(self) -> list[WorkerNode]:
        return self._worker_repository.list()

    def get_worker(self, worker_id: str) -> WorkerNode:
        return require_worker(self._worker_repository.get(worker_id), worker_id)

    def get_match_execution(self, match_execution_id: str, *, include_result_payload: bool = True) -> MatchExecution:
        return require_match_execution(
            self._match_execution_repository.get(
                match_execution_id,
                include_result_payload=include_result_payload,
            ),
            match_execution_id,
        )

    def get_match_execution_for_run(self, run: Run, *, include_result_payload: bool = True) -> MatchExecution | None:
        if run.match_execution_id is not None:
            return self._match_execution_repository.get(
                run.match_execution_id,
                include_result_payload=include_result_payload,
            )
        return self._match_execution_repository.find_by_run_id(
            run.run_id,
            include_result_payload=include_result_payload,
        )

    def start_build(self, game_source_id: str, repo_url: str) -> BuildJob:
        build = BuildJob.start(game_source_id=game_source_id, repo_url=repo_url)
        self._build_repository.save(build)
        return build

    def _ensure_single_task_can_be_queued(self, requested_by: str, exclude_run_id: str | None = None) -> None:
        active_runs = self._run_repository.list_active_by_requested_by_and_kind(
            requested_by=requested_by,
            run_kind=RunKind.SINGLE_TASK,
        )
        blocking_runs = [
            run for run in active_runs if run.run_id != exclude_run_id and run.status in _SINGLE_TASK_BLOCKING_STATUSES
        ]
        for run in active_runs:
            if run.run_id == exclude_run_id or run.status is not RunStatus.CREATED:
                continue
            run.mark_canceled(message="superseded_created_single_task")
            self._run_repository.save(run)
        if blocking_runs:
            raise ConflictError(
                "У пользователя уже есть активный single_task запуск. "
                "Остановите его или дождитесь завершения."
            )

    def finish_build(self, build_id: str, image_digest: str) -> BuildJob:
        build = require_build(self._build_repository.get(build_id), build_id)
        build.mark_finished(image_digest=image_digest)
        self._build_repository.save(build)
        return build

    def fail_build(self, build_id: str, error_message: str) -> BuildJob:
        build = require_build(self._build_repository.get(build_id), build_id)
        build.mark_failed(error_message=error_message)
        self._build_repository.save(build)
        return build

    def _mark_primary_match_accepted(self, *, run: Run, worker_id: str) -> None:
        match = self._primary_match_execution_for_run(run)
        if match is None or match.status is not MatchExecutionStatus.QUEUED:
            return
        match.mark_accepted(worker_id)
        self._match_execution_repository.save(match)

    def _mark_primary_match_started(self, *, run: Run, worker_id: str) -> None:
        match = self._primary_match_execution_for_run(run)
        if match is None or match.status is not MatchExecutionStatus.QUEUED:
            return
        match.mark_started(worker_id)
        self._match_execution_repository.save(match)

    def _mark_primary_match_finished(self, *, run: Run, payload: dict[str, object]) -> None:
        match = self._primary_match_execution_for_run(run)
        if match is None or match.status is MatchExecutionStatus.FINISHED:
            return
        if match.status in {MatchExecutionStatus.QUEUED, MatchExecutionStatus.RUNNING}:
            match.mark_finished(payload)
            self._match_execution_repository.save(match)

    def _merge_primary_match_payload(self, *, run: Run, payload: dict[str, object]) -> None:
        match = self._primary_match_execution_for_run(run)
        if match is None or match.status is not MatchExecutionStatus.FINISHED:
            return
        merged_payload = _merge_finished_payload(match.result_payload, payload)
        if merged_payload == match.result_payload:
            return
        match.result_payload = merged_payload
        self._match_execution_repository.save(match)

    def _mark_primary_match_failed(self, *, run: Run, message: str) -> None:
        match = self._primary_match_execution_for_run(run)
        if match is None or match.status is MatchExecutionStatus.FAILED:
            return
        if match.status in {MatchExecutionStatus.CREATED, MatchExecutionStatus.QUEUED, MatchExecutionStatus.RUNNING}:
            match.mark_failed(message)
            self._match_execution_repository.save(match)

    def _mark_primary_match_canceled(self, *, run: Run, message: str | None) -> None:
        match = self._primary_match_execution_for_run(run)
        if match is None or match.status is MatchExecutionStatus.CANCELED:
            return
        if match.status in {MatchExecutionStatus.CREATED, MatchExecutionStatus.QUEUED, MatchExecutionStatus.RUNNING}:
            match.mark_canceled(message)
            self._match_execution_repository.save(match)

    def _primary_match_execution_for_run(self, run: Run) -> MatchExecution | None:
        if run.match_execution_id is None or run.match_primary_run_id != run.run_id:
            return None
        return self._match_execution_repository.get(run.match_execution_id)


def _merge_finished_payload(existing: dict[str, object] | None, incoming: dict[str, object]) -> dict[str, object]:
    if not isinstance(existing, dict):
        return dict(incoming)
    merged = dict(existing)
    for key, value in incoming.items():
        current = merged.get(key)
        if key in {"scores", "placements"} and isinstance(current, dict) and isinstance(value, dict):
            merged[key] = {**current, **value}
            continue
        if key == "metrics" and isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_metrics_payload(current, value)
            continue
        if key in {"frames", "events"} and current:
            continue
        merged[key] = value
    return merged


def _merge_metrics_payload(existing: dict[object, object], incoming: dict[object, object]) -> dict[object, object]:
    merged = dict(existing)
    for key, value in incoming.items():
        current = merged.get(key)
        if key in {"scores", "placements"} and isinstance(current, dict) and isinstance(value, dict):
            merged[key] = {**current, **value}
        else:
            merged[key] = value
    return merged
