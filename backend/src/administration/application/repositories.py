from __future__ import annotations

from typing import Protocol

from administration.domain.model import GameSource, GameSourceSync


class GameSourceRepository(Protocol):
    def save(self, source: GameSource) -> None:
        ...

    def get(self, source_id: str) -> GameSource | None:
        ...

    def list(self) -> list[GameSource]:
        ...

    def get_by_repo_url(self, repo_url: str, default_branch: str) -> GameSource | None:
        ...


class GameSourceSyncRepository(Protocol):
    def save(self, sync: GameSourceSync) -> None:
        ...

    def list_by_source(self, source_id: str) -> list[GameSourceSync]:
        ...
