from __future__ import annotations

import httpx

from shared.kernel import ExternalServiceError


class HttpSchedulerGateway:
    def __init__(self, scheduler_base_url: str, timeout_seconds: float = 3.0) -> None:
        self._scheduler_base_url = scheduler_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def schedule_run(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> None:
        url = f"{self._scheduler_base_url}/internal/runs/{run_id}/schedule"
        payload = {"required_worker_labels": required_worker_labels or {}}
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                f"Не удалось связаться с scheduler-service при постановке run {run_id} в очередь"
            ) from exc

        if response.status_code >= 400:
            raise ExternalServiceError(
                f"scheduler-service вернул HTTP {response.status_code} при постановке run {run_id}"
            )

        payload = response.json()
        status = payload.get("status")
        if status not in {"queued", "already_queued"}:
            raise ExternalServiceError(
                f"scheduler-service вернул неожиданный статус '{status}' для run {run_id}"
            )
