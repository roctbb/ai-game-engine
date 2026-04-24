from __future__ import annotations

from typing import Protocol

from training_lobby.domain.model import Lobby


class LobbyRepository(Protocol):
    def save(self, lobby: Lobby) -> None:
        ...

    def get(self, lobby_id: str) -> Lobby | None:
        ...

    def list(self) -> list[Lobby]:
        ...
