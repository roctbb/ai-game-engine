from __future__ import annotations

from identity.domain.model import AppSession


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._items: dict[str, AppSession] = {}

    def save(self, session: AppSession) -> None:
        self._items[session.session_id] = session

    def get(self, session_id: str) -> AppSession | None:
        return self._items.get(session_id)

    def delete(self, session_id: str) -> None:
        self._items.pop(session_id, None)
