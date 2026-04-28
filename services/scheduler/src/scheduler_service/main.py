from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel, Field
from redis import Redis

from scheduler_service.queue import SchedulerQueue
from scheduler_service.settings import settings

app = FastAPI(title=settings.app_name)
redis_client = Redis.from_url(settings.redis_url)
queue = SchedulerQueue(redis_client=redis_client)


class PullRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=120)
    worker_labels: dict[str, str] = Field(default_factory=dict)


class ScheduleRunRequest(BaseModel):
    required_worker_labels: dict[str, str] = Field(default_factory=dict)


class AckFinishedRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)
    lease_id: str = Field(min_length=1, max_length=120)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/runs/{run_id}/schedule")
def schedule_run(run_id: str, request: ScheduleRunRequest | None = None) -> dict[str, object]:
    inserted = queue.enqueue(
        run_id=run_id,
        required_worker_labels=request.required_worker_labels if request is not None else None,
    )
    return {
        "run_id": run_id,
        "status": "queued" if inserted else "already_queued",
    }


@app.post("/internal/workers/pull-next")
def pull_next(request: PullRequest) -> dict[str, object]:
    lease = queue.pull_next(
        worker_id=request.worker_id,
        leased_at_epoch=int(datetime.now(tz=UTC).timestamp()),
        worker_labels=request.worker_labels,
    )
    return {
        "worker_id": request.worker_id,
        "run_id": lease.run_id if lease else None,
        "lease_id": lease.lease_id if lease else None,
        "status": "assigned" if lease else "empty",
    }


@app.post("/internal/runs/ack-finished")
def ack_finished(request: AckFinishedRequest) -> dict[str, str]:
    acknowledged = queue.ack_finished(
        worker_id=request.worker_id,
        run_id=request.run_id,
        lease_id=request.lease_id,
    )
    return {"status": "acknowledged" if acknowledged else "stale_lease_ignored"}


@app.get("/internal/queue/stats")
def queue_stats() -> dict[str, object]:
    return queue.stats()
