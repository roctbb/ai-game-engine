from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from administration.domain.model import SyncStatus


@dataclass(frozen=True, slots=True)
class BuildSyncResult:
    build_id: str
    status: SyncStatus
    image_digest: str | None = None
    error_message: str | None = None


class BuilderGateway(Protocol):
    def start_build(self, game_source_id: str, repo_url: str) -> BuildSyncResult:
        ...
