from __future__ import annotations

import hashlib

from administration.application.builder_gateway import BuildSyncResult
from administration.domain.model import SyncStatus
from shared.kernel import new_id


class NoopBuilderGateway:
    """Fallback gateway for local dev/tests without a dedicated builder-service."""

    def start_build(self, game_source_id: str, repo_url: str) -> BuildSyncResult:
        hasher = hashlib.sha256()
        hasher.update(game_source_id.encode("utf-8"))
        hasher.update(b"|")
        hasher.update(repo_url.encode("utf-8"))
        digest = f"sha256:{hasher.hexdigest()}"
        return BuildSyncResult(
            build_id=new_id("build"),
            status=SyncStatus.FINISHED,
            image_digest=digest,
            error_message=None,
        )
