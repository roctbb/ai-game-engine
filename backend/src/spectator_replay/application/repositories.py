from __future__ import annotations

from typing import Protocol

from execution.domain.model import RunKind
from spectator_replay.domain.model import ReplayRecord


class ReplayRepository(Protocol):
    def save(self, replay: ReplayRecord) -> None:
        ...

    def get_by_run_id(self, run_id: str) -> ReplayRecord | None:
        ...

    def list(self, game_id: str | None = None, run_kind: RunKind | None = None, limit: int = 50) -> list[ReplayRecord]:
        ...

    def delete_by_run_ids(self, run_ids: list[str]) -> None:
        ...
