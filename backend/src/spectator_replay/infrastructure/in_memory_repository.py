from __future__ import annotations

from execution.domain.model import RunKind
from spectator_replay.domain.model import ReplayRecord


class InMemoryReplayRepository:
    def __init__(self) -> None:
        self._items_by_run_id: dict[str, ReplayRecord] = {}

    def save(self, replay: ReplayRecord) -> None:
        self._items_by_run_id[replay.run_id] = replay

    def get_by_run_id(self, run_id: str, *, include_content: bool = True) -> ReplayRecord | None:
        item = self._items_by_run_id.get(run_id)
        if item is None or include_content:
            return item
        return ReplayRecord(
            replay_id=item.replay_id,
            run_id=item.run_id,
            game_id=item.game_id,
            run_kind=item.run_kind,
            status=item.status,
            visibility=item.visibility,
            frames=[],
            events=[],
            summary=dict(item.summary),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def list(
        self,
        game_id: str | None = None,
        run_kind: RunKind | None = None,
        limit: int = 50,
        include_content: bool = True,
    ) -> list[ReplayRecord]:
        items = list(self._items_by_run_id.values())
        if game_id is not None:
            items = [item for item in items if item.game_id == game_id]
        if run_kind is not None:
            items = [item for item in items if item.run_kind is run_kind]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        items = items[:limit]
        if include_content:
            return items
        return [
            ReplayRecord(
                replay_id=item.replay_id,
                run_id=item.run_id,
                game_id=item.game_id,
                run_kind=item.run_kind,
                status=item.status,
                visibility=item.visibility,
                frames=[],
                events=[],
                summary=dict(item.summary),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ]

    def delete_by_run_ids(self, run_ids: list[str]) -> None:
        for run_id in run_ids:
            self._items_by_run_id.pop(run_id, None)
