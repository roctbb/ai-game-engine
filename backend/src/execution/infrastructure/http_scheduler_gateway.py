from __future__ import annotations

import httpx
from threading import Lock

from shared.kernel import ExternalServiceError


class HttpSchedulerGateway:
    def __init__(self, scheduler_base_url: str, timeout_seconds: float = 3.0) -> None:
        self._scheduler_base_url = scheduler_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._worker_client = None
        self._worker_client_lock = Lock()

    def schedule_run(
        self, run_id: str, required_worker_labels: dict[str, str] | None = None
    ) -> None:
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

    def cancel_run(self, run_id: str) -> None:
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(f"{self._scheduler_base_url}/internal/runs/{run_id}/cancel")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Не удалось отменить задание {run_id} в scheduler") from exc

    def worker_request(self, operation: str, payload: dict[str, object]) -> dict[str, object]:
        paths = {
            "pull": "/internal/workers/pull-next",
            "renew": "/internal/runs/renew-lease",
            "ack": "/internal/runs/ack-finished",
        }
        try:
            with self._worker_client_lock:
                if self._worker_client is None:
                    self._worker_client = httpx.Client(timeout=self._timeout_seconds)
                client = self._worker_client
            response = client.post(self._scheduler_base_url + paths[operation], json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError("Очередь вычислений временно недоступна") from exc

    def close(self) -> None:
        with self._worker_client_lock:
            if self._worker_client is not None:
                self._worker_client.close()
                self._worker_client = None
