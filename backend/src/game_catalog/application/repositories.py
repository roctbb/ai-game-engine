from __future__ import annotations

from typing import Protocol

from game_catalog.domain.model import Game


class GameRepository(Protocol):
    def save(self, game: Game) -> None:
        ...

    def get(self, game_id: str) -> Game | None:
        ...

    def get_by_slug(self, slug: str) -> Game | None:
        ...

    def list(self) -> list[Game]:
        ...
