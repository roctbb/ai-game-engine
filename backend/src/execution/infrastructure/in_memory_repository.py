from __future__ import annotations

from execution.domain.model import BuildJob, Run, RunKind, RunStatus, WorkerNode


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._items: dict[str, Run] = {}

    def save(self, run: Run) -> None:
        self._items[run.run_id] = run

    def get(self, run_id: str) -> Run | None:
        return self._items.get(run_id)

    def list(self) -> list[Run]:
        return sorted(self._items.values(), key=lambda run: run.created_at, reverse=True)

    def list_active_by_requested_by_and_kind(
        self, requested_by: str, run_kind: RunKind
    ) -> list[Run]:
        active_statuses = {RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING}
        return [
            run
            for run in self._items.values()
            if run.requested_by == requested_by
            and run.run_kind is run_kind
            and run.status in active_statuses
        ]


class InMemoryWorkerRepository:
    def __init__(self) -> None:
        self._items: dict[str, WorkerNode] = {}

    def save(self, worker: WorkerNode) -> None:
        self._items[worker.worker_id] = worker

    def get(self, worker_id: str) -> WorkerNode | None:
        return self._items.get(worker_id)

    def list(self) -> list[WorkerNode]:
        return sorted(self._items.values(), key=lambda worker: worker.worker_id)


class InMemoryBuildRepository:
    def __init__(self) -> None:
        self._items: dict[str, BuildJob] = {}

    def save(self, build: BuildJob) -> None:
        self._items[build.build_id] = build

    def get(self, build_id: str) -> BuildJob | None:
        return self._items.get(build_id)
