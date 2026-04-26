from __future__ import annotations

from training_lobby.domain.model import Lobby


class InMemoryLobbyRepository:
    def __init__(self) -> None:
        self._items: dict[str, Lobby] = {}

    def save(self, lobby: Lobby) -> None:
        self._items[lobby.lobby_id] = lobby

    def get(self, lobby_id: str) -> Lobby | None:
        return self._items.get(lobby_id)

    def list(self) -> list[Lobby]:
        return sorted(self._items.values(), key=lambda lobby: lobby.created_at, reverse=True)

    def delete(self, lobby_id: str) -> None:
        self._items.pop(lobby_id, None)
