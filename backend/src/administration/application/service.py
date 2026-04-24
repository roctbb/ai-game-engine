from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from administration.application.builder_gateway import BuilderGateway
from administration.application.repositories import GameSourceRepository, GameSourceSyncRepository
from administration.domain.model import (
    GameSource,
    GameSourceSync,
    SyncStatus,
    derive_commit_sha,
    ensure_can_start_sync,
    require_source,
)
from shared.kernel import ConflictError, ExternalServiceError, InvariantViolationError


_BUILD_ID_RE = re.compile(r"^build_[0-9a-f]{32}$")
_IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(slots=True)
class CreateGameSourceInput:
    repo_url: str
    default_branch: str
    created_by: str


@dataclass(slots=True)
class TriggerSyncInput:
    source_id: str
    requested_by: str


@dataclass(slots=True)
class UpdateSourceStatusInput:
    source_id: str
    status: str


class AdministrationService:
    def __init__(
        self,
        source_repository: GameSourceRepository,
        source_sync_repository: GameSourceSyncRepository,
        builder_gateway: BuilderGateway,
    ) -> None:
        self._source_repository = source_repository
        self._source_sync_repository = source_sync_repository
        self._builder_gateway = builder_gateway

    def list_sources(self) -> list[GameSource]:
        return self._source_repository.list()

    def update_source_status(self, data: UpdateSourceStatusInput) -> GameSource:
        source = require_source(self._source_repository.get(data.source_id), data.source_id)
        normalized = data.status.strip().lower()
        if normalized == "active":
            source.activate()
        elif normalized == "disabled":
            source.disable()
        else:
            raise InvariantViolationError("Статус source должен быть active или disabled")
        self._source_repository.save(source)
        return source

    def create_git_source(self, data: CreateGameSourceInput) -> GameSource:
        normalized_repo_url = _normalize_git_url(data.repo_url)
        branch = (data.default_branch or "").strip() or "main"
        if self._source_repository.get_by_repo_url(normalized_repo_url, branch) is not None:
            raise ConflictError("Источник с таким repo_url и default_branch уже существует")

        source = GameSource.create_git(
            repo_url=normalized_repo_url,
            default_branch=branch,
            created_by=data.created_by.strip(),
        )
        self._source_repository.save(source)
        return source

    def sync_source(self, data: TriggerSyncInput) -> tuple[GameSource, GameSourceSync]:
        source = require_source(self._source_repository.get(data.source_id), data.source_id)
        ensure_can_start_sync(source)

        sync = GameSourceSync.start(source_id=source.source_id, requested_by=data.requested_by)
        source.mark_syncing()
        self._source_sync_repository.save(sync)
        self._source_repository.save(source)

        try:
            build_result = self._builder_gateway.start_build(
                game_source_id=source.source_id,
                repo_url=source.repo_url,
            )
        except ExternalServiceError as exc:
            source.mark_sync_failed()
            sync.mark_failed(build_id=None, error_message=exc.message)
            self._source_repository.save(source)
            self._source_sync_repository.save(sync)
            raise

        try:
            if build_result.status is SyncStatus.FINISHED and build_result.image_digest:
                _validate_finished_build_artifact(
                    build_id=build_result.build_id,
                    image_digest=build_result.image_digest,
                )
                commit_sha = derive_commit_sha(repo_url=source.repo_url, default_branch=source.default_branch)
                source.mark_sync_finished(commit_sha=commit_sha)
                sync.mark_finished(
                    build_id=build_result.build_id,
                    image_digest=build_result.image_digest,
                    commit_sha=commit_sha,
                )
                self._source_repository.save(source)
                self._source_sync_repository.save(sync)
                return source, sync
        except ExternalServiceError as exc:
            source.mark_sync_failed()
            sync.mark_failed(
                build_id=build_result.build_id or None,
                error_message=exc.message,
            )
            self._source_repository.save(source)
            self._source_sync_repository.save(sync)
            raise

        source.mark_sync_failed()
        sync.mark_failed(
            build_id=build_result.build_id,
            error_message=build_result.error_message or "Builder sync failed",
        )
        self._source_repository.save(source)
        self._source_sync_repository.save(sync)
        raise ExternalServiceError(sync.error_message or "Builder sync failed")

    def list_sync_history(self, source_id: str) -> list[GameSourceSync]:
        _ = require_source(self._source_repository.get(source_id), source_id)
        return self._source_sync_repository.list_by_source(source_id=source_id)


def _normalize_git_url(raw_url: str) -> str:
    value = raw_url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise InvariantViolationError("Поддерживаются только публичные HTTP(S) git-репозитории")
    if not parsed.netloc:
        raise InvariantViolationError("repo_url должен содержать host")
    if not parsed.path or parsed.path == "/":
        raise InvariantViolationError("repo_url должен содержать путь к репозиторию")
    if parsed.username is not None or parsed.password is not None:
        raise InvariantViolationError("repo_url не должен содержать credentials")
    if parsed.query:
        raise InvariantViolationError("repo_url не должен содержать query-параметры")
    if parsed.fragment:
        raise InvariantViolationError("repo_url не должен содержать fragment")
    return value.rstrip("/")


def _validate_finished_build_artifact(*, build_id: str, image_digest: str) -> None:
    if not _BUILD_ID_RE.fullmatch(build_id):
        raise ExternalServiceError("Builder вернул некорректный build_id")
    if not _IMAGE_DIGEST_RE.fullmatch(image_digest):
        raise ExternalServiceError("Builder вернул некорректный image_digest")
