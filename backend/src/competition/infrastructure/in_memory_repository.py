from __future__ import annotations

from competition.domain.model import Competition


class InMemoryCompetitionRepository:
    def __init__(self) -> None:
        self._items: dict[str, Competition] = {}

    def save(self, competition: Competition) -> None:
        self._items[competition.competition_id] = competition

    def get(self, competition_id: str) -> Competition | None:
        return self._items.get(competition_id)

    def list(self) -> list[Competition]:
        return sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)

    def list_by_lobby(self, lobby_id: str) -> list[Competition]:
        return [
            item
            for item in self.list()
            if item.lobby_id == lobby_id
        ]
