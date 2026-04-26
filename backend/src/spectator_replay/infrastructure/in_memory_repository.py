from __future__ import annotations

from execution.domain.model import RunKind
from spectator_replay.domain.model import ReplayRecord


class InMemoryReplayRepository:
    def __init__(self) -> None:
        self._items_by_run_id: dict[str, ReplayRecord] = {}

    def save(self, replay: ReplayRecord) -> None:
        self._items_by_run_id[replay.run_id] = replay

    def get_by_run_id(self, run_id: str) -> ReplayRecord | None:
        return self._items_by_run_id.get(run_id)

    def list(self, game_id: str | None = None, run_kind: RunKind | None = None, limit: int = 50) -> list[ReplayRecord]:
        items = list(self._items_by_run_id.values())
        if game_id is not None:
            items = [item for item in items if item.game_id == game_id]
        if run_kind is not None:
            items = [item for item in items if item.run_kind is run_kind]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items[:limit]

    def delete_by_run_ids(self, run_ids: list[str]) -> None:
        for run_id in run_ids:
            self._items_by_run_id.pop(run_id, None)
