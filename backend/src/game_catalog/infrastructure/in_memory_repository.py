from __future__ import annotations

from game_catalog.domain.model import Game


class InMemoryGameRepository:
    def __init__(self) -> None:
        self._items: dict[str, Game] = {}

    def save(self, game: Game) -> None:
        self._items[game.game_id] = game

    def get(self, game_id: str) -> Game | None:
        return self._items.get(game_id)

    def get_by_slug(self, slug: str) -> Game | None:
        for game in self._items.values():
            if game.slug == slug:
                return game
        return None

    def list(self) -> list[Game]:
        return sorted(self._items.values(), key=lambda game: game.slug)
