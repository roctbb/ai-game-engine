from __future__ import annotations

from administration.domain.model import GameSource, GameSourceSync


class InMemoryGameSourceRepository:
    def __init__(self) -> None:
        self._items: dict[str, GameSource] = {}

    def save(self, source: GameSource) -> None:
        self._items[source.source_id] = source

    def get(self, source_id: str) -> GameSource | None:
        return self._items.get(source_id)

    def list(self) -> list[GameSource]:
        return sorted(self._items.values(), key=lambda item: item.created_at)

    def get_by_repo_url(self, repo_url: str, default_branch: str) -> GameSource | None:
        for source in self._items.values():
            if source.repo_url == repo_url and source.default_branch == default_branch:
                return source
        return None


class InMemoryGameSourceSyncRepository:
    def __init__(self) -> None:
        self._items: dict[str, GameSourceSync] = {}

    def save(self, sync: GameSourceSync) -> None:
        self._items[sync.sync_id] = sync

    def list_by_source(self, source_id: str) -> list[GameSourceSync]:
        result = [item for item in self._items.values() if item.source_id == source_id]
        return sorted(result, key=lambda item: item.started_at, reverse=True)
