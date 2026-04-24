from __future__ import annotations

from typing import Protocol

from identity.domain.model import AppSession


class SessionRepository(Protocol):
    def save(self, session: AppSession) -> None:
        ...

    def get(self, session_id: str) -> AppSession | None:
        ...

    def delete(self, session_id: str) -> None:
        ...
