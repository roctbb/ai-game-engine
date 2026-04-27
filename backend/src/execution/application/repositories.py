from __future__ import annotations

from typing import Protocol

from execution.domain.model import BuildJob, Run, RunKind, RunStatus, WorkerNode


class RunRepository(Protocol):
    def save(self, run: Run) -> None:
        ...

    def get(self, run_id: str, *, include_result_payload: bool = True) -> Run | None:
        ...

    def list(self) -> list[Run]:
        ...

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
        ...

    def list_active_by_requested_by_and_kind(
        self, requested_by: str, run_kind: RunKind
    ) -> list[Run]:
        ...

    def delete_many(self, run_ids: list[str]) -> None:
        ...


class WorkerRepository(Protocol):
    def save(self, worker: WorkerNode) -> None:
        ...

    def get(self, worker_id: str) -> WorkerNode | None:
        ...

    def list(self) -> list[WorkerNode]:
        ...


class BuildRepository(Protocol):
    def save(self, build: BuildJob) -> None:
        ...

    def get(self, build_id: str) -> BuildJob | None:
        ...
