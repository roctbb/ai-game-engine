from __future__ import annotations

from dataclasses import replace

from execution.domain.model import BuildJob, MatchExecution, Run, RunKind, RunStatus, WorkerNode


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
        requested_by: str | None = None,
        include_result_payload: bool = True,
        limit: int | None = None,
        offset: int | None = None,
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
            if requested_by is not None and run.requested_by != requested_by:
                continue
            runs.append(run if include_result_payload else replace(run, result_payload=None))
        result = sorted(runs, key=lambda item: item.created_at, reverse=True)
        if offset is not None and offset > 0:
            result = result[offset:]
        if limit is not None:
            result = result[:limit]
        return result

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


class InMemoryMatchExecutionRepository:
    def __init__(self) -> None:
        self._items: dict[str, MatchExecution] = {}

    def save(self, match: MatchExecution) -> None:
        self._items[match.match_execution_id] = match

    def get(self, match_execution_id: str, *, include_result_payload: bool = True) -> MatchExecution | None:
        match = self._items.get(match_execution_id)
        if match is None or include_result_payload:
            return match
        return replace(match, result_payload=None)

    def find_by_run_id(self, run_id: str, *, include_result_payload: bool = True) -> MatchExecution | None:
        for match in self._items.values():
            if run_id in match.run_ids:
                return match if include_result_payload else replace(match, result_payload=None)
        return None

    def delete_many(self, match_execution_ids: list[str]) -> None:
        for match_execution_id in match_execution_ids:
            self._items.pop(match_execution_id, None)


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
