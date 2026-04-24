from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib

from shared.kernel import ConflictError, NotFoundError, new_id, utc_now


class GameSourceType(StrEnum):
    EMBEDDED = "embedded"
    GIT = "git"


class GameSourceStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class SyncStatus(StrEnum):
    NEVER = "never"
    SYNCING = "syncing"
    FINISHED = "finished"
    FAILED = "failed"


@dataclass(slots=True)
class GameSource:
    source_id: str
    source_type: GameSourceType
    repo_url: str
    default_branch: str
    status: GameSourceStatus
    last_sync_status: SyncStatus
    last_synced_commit_sha: str | None
    created_by: str
    created_at: object
    updated_at: object

    @staticmethod
    def create_git(repo_url: str, default_branch: str, created_by: str) -> "GameSource":
        now = utc_now()
        return GameSource(
            source_id=new_id("gsrc"),
            source_type=GameSourceType.GIT,
            repo_url=repo_url,
            default_branch=default_branch,
            status=GameSourceStatus.ACTIVE,
            last_sync_status=SyncStatus.NEVER,
            last_synced_commit_sha=None,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )

    def mark_syncing(self) -> None:
        self.last_sync_status = SyncStatus.SYNCING
        self.updated_at = utc_now()

    def mark_sync_finished(self, commit_sha: str) -> None:
        self.last_sync_status = SyncStatus.FINISHED
        self.last_synced_commit_sha = commit_sha
        self.updated_at = utc_now()

    def mark_sync_failed(self) -> None:
        self.last_sync_status = SyncStatus.FAILED
        self.updated_at = utc_now()

    def disable(self) -> None:
        self.status = GameSourceStatus.DISABLED
        self.updated_at = utc_now()

    def activate(self) -> None:
        self.status = GameSourceStatus.ACTIVE
        self.updated_at = utc_now()


@dataclass(slots=True)
class GameSourceSync:
    sync_id: str
    source_id: str
    requested_by: str
    status: SyncStatus
    build_id: str | None
    image_digest: str | None
    error_message: str | None
    commit_sha: str | None
    started_at: object
    finished_at: object | None

    @staticmethod
    def start(source_id: str, requested_by: str) -> "GameSourceSync":
        return GameSourceSync(
            sync_id=new_id("gsync"),
            source_id=source_id,
            requested_by=requested_by,
            status=SyncStatus.SYNCING,
            build_id=None,
            image_digest=None,
            error_message=None,
            commit_sha=None,
            started_at=utc_now(),
            finished_at=None,
        )

    def mark_finished(self, build_id: str, image_digest: str, commit_sha: str) -> None:
        self.status = SyncStatus.FINISHED
        self.build_id = build_id
        self.image_digest = image_digest
        self.commit_sha = commit_sha
        self.finished_at = utc_now()

    def mark_failed(self, build_id: str | None, error_message: str) -> None:
        self.status = SyncStatus.FAILED
        self.build_id = build_id
        self.error_message = error_message
        self.finished_at = utc_now()


def require_source(value: GameSource | None, source_id: str) -> GameSource:
    if value is None:
        raise NotFoundError(f"Game source {source_id} не найден")
    return value


def ensure_can_start_sync(source: GameSource) -> None:
    if source.status is GameSourceStatus.DISABLED:
        raise ConflictError("Синхронизация недоступна для отключенного источника")
    if source.last_sync_status is SyncStatus.SYNCING:
        raise ConflictError("Для источника уже выполняется синхронизация")


def derive_commit_sha(repo_url: str, default_branch: str) -> str:
    raw = f"{repo_url}|{default_branch}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]
