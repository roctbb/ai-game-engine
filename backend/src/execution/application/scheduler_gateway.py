from __future__ import annotations

from typing import Protocol


class SchedulerGateway(Protocol):
    def schedule_run(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> None:
        ...


class NoopSchedulerGateway:
    """Safe fallback for local dev/tests when scheduler-service is not configured."""

    def schedule_run(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> None:
        _ = run_id
        _ = required_worker_labels
