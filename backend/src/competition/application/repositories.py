from __future__ import annotations

from typing import Protocol

from competition.domain.model import Competition


class CompetitionRepository(Protocol):
    def save(self, competition: Competition) -> None:
        ...

    def get(self, competition_id: str) -> Competition | None:
        ...

    def list(self) -> list[Competition]:
        ...
