from __future__ import annotations

import httpx

from administration.application.builder_gateway import BuildSyncResult
from administration.domain.model import SyncStatus
from shared.kernel import ExternalServiceError


class HttpBuilderGateway:
    def __init__(self, builder_base_url: str, timeout_seconds: float = 15.0) -> None:
        self._builder_base_url = builder_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def start_build(self, game_source_id: str, repo_url: str) -> BuildSyncResult:
        url = f"{self._builder_base_url}/internal/builds/start"
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(
                    url,
                    json={
                        "game_source_id": game_source_id,
                        "repo_url": repo_url,
                    },
                )
        except httpx.HTTPError as exc:
            raise ExternalServiceError("Не удалось связаться с builder-service") from exc

        if response.status_code >= 400:
            raise ExternalServiceError(f"builder-service вернул HTTP {response.status_code}")

        payload = response.json()
        raw_status = str(payload.get("status", "")).strip().lower()
        build_id = str(payload.get("build_id", "")).strip()
        if not build_id:
            raise ExternalServiceError("builder-service завершил sync без build_id")

        if raw_status == SyncStatus.FINISHED.value:
            image_digest = payload.get("image_digest")
            if not image_digest:
                raise ExternalServiceError("builder-service завершил build без image_digest")
            return BuildSyncResult(
                build_id=build_id,
                status=SyncStatus.FINISHED,
                image_digest=str(image_digest),
                error_message=None,
            )

        if raw_status == SyncStatus.FAILED.value:
            return BuildSyncResult(
                build_id=build_id,
                status=SyncStatus.FAILED,
                image_digest=None,
                error_message=str(payload.get("error_message") or "Builder sync failed"),
            )

        raise ExternalServiceError(f"builder-service вернул неожиданный статус '{raw_status}'")
