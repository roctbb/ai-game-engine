from __future__ import annotations

from dataclasses import replace

from execution.domain.model import BuildJob, Run, RunKind, RunStatus, WorkerNode


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._items: dict[str, Run] = {}

    def save(self, run: Run) -> None:
        self._items[run.run_id] = run

    def get(self, run_id: str, *, include_result_payload: bool = True) -> Run | None:
        run = self._items.get(run_id)
        if run is None or include_result_payload:
            return run
        return replace(run, result_payload=None)

    def list(self) -> list[Run]:
        return sorted(self._items.values(), key=lambda run: run.created_at, reverse=True)

    def list_filtered(
        self,
        *,
        team_id: str | None = None,
        game_id: str | None = None,
        lobby_id: str | None = None,
        run_kind: RunKind | None = None,
        status: RunStatus | None = None,
        include_result_payload: bool = True,
    ) -> list[Run]:
        runs: list[Run] = []
        for run in self._items.values():
            if team_id is not None and run.team_id != team_id:
                continue
            if game_id is not None and run.game_id != game_id:
                continue
            if lobby_id is not None and run.lobby_id != lobby_id:
                continue
            if run_kind is not None and run.run_kind is not run_kind:
                continue
            if status is not None and run.status is not status:
                continue
            runs.append(run if include_result_payload else replace(run, result_payload=None))
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

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

    def delete_many(self, run_ids: list[str]) -> None:
        for run_id in run_ids:
            self._items.pop(run_id, None)


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
