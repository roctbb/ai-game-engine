"""Narrow internet gateway. Node credentials never authorize the internal API."""

import asyncio
from datetime import UTC, datetime, timedelta
import json

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from app.auth import require_roles
from app.dependencies import ServiceContainer, get_container
from execution.api import router as legacy
from execution.api.schemas import FinishRunRequest, FailRunRequest, WorkerResponse
from execution.domain.model import RunStatus, WorkerStatus
from execution.infrastructure.worker_distribution import install_command, worker_distribution
from identity.domain.model import UserRole
from shared.config.settings import settings
from shared.kernel import (
    ForbiddenError,
    InvariantViolationError,
    NotFoundError,
    UnauthorizedError,
    utc_now,
)

router = APIRouter()
node_router = APIRouter(prefix="/worker/v1", tags=["External workers"])


class AddMachineRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slots: int = Field(default=1, ge=1, le=64)
    labels: dict[str, str] = Field(default_factory=dict, max_length=32)


class EnrollRequest(BaseModel):
    enrollment_key: str = Field(min_length=40, max_length=200)
    token: str = Field(pattern=r"^worker\.external_[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$")


class PullRequest(BaseModel):
    wait_seconds: float = Field(default=0, ge=0, le=15)


class HeartbeatRequest(BaseModel):
    capacity_available: int = Field(ge=0, le=64)


class LeaseRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=120)
    lease_id: str = Field(min_length=1, max_length=120)


def authenticated_node(
    authorization: str | None = Header(default=None),
    container: ServiceContainer = Depends(get_container),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Нужен токен машины")
    worker = container.remote_workers.authenticate(authorization[7:])
    return worker


def _worker_response(container, worker):
    response = legacy._worker_response(worker)
    # An idle/disconnected external machine must not look online indefinitely.
    seen = worker.last_heartbeat_at
    if isinstance(seen, datetime):
        seen = seen.replace(tzinfo=UTC) if seen.tzinfo is None else seen
        if worker.status is WorkerStatus.ONLINE and utc_now() - seen > timedelta(seconds=45):
            response = response.model_copy(update={"status": WorkerStatus.OFFLINE})
    return response.model_copy(update=container.remote_workers.metadata(worker.worker_id))


def _installation(container, worker_id, issued):
    key, expires = issued
    worker = container.execution.get_worker(worker_id)
    base = settings.frontend_url.rstrip("/")
    if settings.app_env == "production" and not base.startswith("https://"):
        raise InvariantViolationError("Для внешних воркеров нужен публичный HTTPS-адрес")
    return {
        "worker": _worker_response(container, worker),
        "expires_at": expires,
        "command": install_command(base, worker_id, key, worker.capacity_total),
    }


@router.post("/workers/external", dependencies=[Depends(require_roles(UserRole.ADMIN))])
def add_machine(
    request: AddMachineRequest,
    response: Response,
    container: ServiceContainer = Depends(get_container),
):
    if not request.name.strip() or any(
        not key.strip() or len(key) > 64 or len(value) > 128
        for key, value in request.labels.items()
    ):
        raise InvariantViolationError("Проверьте имя и метки машины")
    worker_id, issued = container.remote_workers.add(
        request.name.strip(), request.slots, request.labels
    )
    response.headers["Cache-Control"] = "no-store"
    return _installation(container, worker_id, issued)


@router.post(
    "/workers/{worker_id}/connection", dependencies=[Depends(require_roles(UserRole.ADMIN))]
)
def reconnect_machine(
    worker_id: str, response: Response, container: ServiceContainer = Depends(get_container)
):
    response.headers["Cache-Control"] = "no-store"
    return _installation(container, worker_id, container.remote_workers.issue_enrollment(worker_id))


@router.post("/workers/{worker_id}/revoke", dependencies=[Depends(require_roles(UserRole.ADMIN))])
def revoke_machine(worker_id: str, container: ServiceContainer = Depends(get_container)):
    return _worker_response(container, container.remote_workers.revoke(worker_id))


@node_router.get("/distribution/{digest}.tar.gz")
def distribution(digest: str):
    actual, raw = worker_distribution()
    if actual != digest:
        raise NotFoundError("Версия воркера устарела; получите новую команду подключения")
    return Response(
        raw,
        media_type="application/gzip",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": '"' + actual + '"',
        },
    )


@node_router.post("/enroll", response_model=WorkerResponse)
def enroll(
    request: EnrollRequest, response: Response, container: ServiceContainer = Depends(get_container)
):
    response.headers["Cache-Control"] = "no-store"
    return _worker_response(
        container, container.remote_workers.enroll(request.enrollment_key, request.token)
    )


@node_router.post("/register", response_model=WorkerResponse)
def register(
    worker=Depends(authenticated_node), container: ServiceContainer = Depends(get_container)
):
    return _worker_response(container, worker)


@node_router.post("/heartbeat", response_model=WorkerResponse)
def heartbeat(
    request: HeartbeatRequest,
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    return _worker_response(
        container,
        container.execution.worker_heartbeat(worker.worker_id, request.capacity_available),
    )


@node_router.post("/pull-next")
async def pull_next(
    request: PullRequest,
    authorization: str | None = Header(default=None),
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    deadline = asyncio.get_running_loop().time() + request.wait_seconds
    while True:
        worker = await asyncio.to_thread(authenticated_node, authorization, container)
        if worker.status in {WorkerStatus.DRAINING, WorkerStatus.DISABLED}:
            return {"status": "paused", "run_id": None}
        assigned = await asyncio.to_thread(
            container.scheduler.worker_request,
            "pull",
            {
                "worker_id": worker.worker_id,
                "worker_labels": worker.labels,
                "max_slots": worker.capacity_total,
                "lease_ttl_seconds": 90,
            },
        )
        if run_id := assigned.get("run_id"):
            try:
                await asyncio.to_thread(
                    container.execution.accept_run,
                    run_id,
                    worker.worker_id,
                    assigned["lease_id"],
                    assigned["lease_generation"],
                )
            except (NotFoundError, InvariantViolationError):
                await asyncio.to_thread(
                    container.scheduler.worker_request,
                    "ack",
                    {
                        "worker_id": worker.worker_id,
                        "run_id": run_id,
                        "lease_id": assigned["lease_id"],
                    },
                )
                if asyncio.get_running_loop().time() >= deadline:
                    return {"status": "empty", "run_id": None}
                continue
            return assigned
        if asyncio.get_running_loop().time() >= deadline:
            return assigned
        await asyncio.sleep(0.5)


def _owned_run(container, worker, run_id, lease_id, *, allow_terminal=False):
    container.remote_workers.require_enabled(worker)
    run = container.execution.get_run(run_id, include_result_payload=False)
    if run.worker_id != worker.worker_id or not lease_id or run.active_lease_id != lease_id:
        raise ForbiddenError("Запуск не принадлежит действующей аренде этой машины")
    terminal = run.status in {
        RunStatus.FINISHED,
        RunStatus.FAILED,
        RunStatus.TIMEOUT,
        RunStatus.CANCELED,
    }
    if terminal and allow_terminal:
        return run
    renewed = container.scheduler.worker_request(
        "renew", {"worker_id": worker.worker_id, "run_id": run_id, "lease_id": lease_id}
    )
    if renewed.get("renewed") is not True:
        raise InvariantViolationError("Аренда задания истекла")
    return run


@node_router.post("/renew-lease")
def renew(
    request: LeaseRequest,
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    _owned_run(container, worker, request.run_id, request.lease_id)
    return {"renewed": True}


@node_router.post("/ack-finished")
def acknowledge(
    request: LeaseRequest,
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    run = _owned_run(container, worker, request.run_id, request.lease_id, allow_terminal=True)
    if run.status not in {
        RunStatus.FINISHED,
        RunStatus.FAILED,
        RunStatus.TIMEOUT,
        RunStatus.CANCELED,
    }:
        raise InvariantViolationError("Нельзя убрать незавершённое задание из очереди")
    return container.scheduler.worker_request(
        "ack",
        {"worker_id": worker.worker_id, "run_id": request.run_id, "lease_id": request.lease_id},
    )


@node_router.get("/runs/{run_id}/execution-context")
def context(
    run_id: str,
    x_lease_id: str | None = Header(default=None),
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    _owned_run(container, worker, run_id, x_lease_id)
    return legacy.get_run_execution_context(run_id, None, container)


@node_router.get("/runs/{run_id}/package")
def package(
    run_id: str,
    x_lease_id: str | None = Header(default=None),
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    _owned_run(container, worker, run_id, x_lease_id)
    return legacy.get_run_package(run_id, None, container)


@node_router.get("/runs/{run_id}/control")
def control(
    run_id: str,
    x_lease_id: str | None = Header(default=None),
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    run = _owned_run(container, worker, run_id, x_lease_id, allow_terminal=True)
    return {
        "status": run.status,
        "lease_id": run.active_lease_id,
        "lease_generation": run.lease_generation,
    }


@node_router.post("/runs/{run_id}/accepted")
def accepted(
    run_id: str,
    x_lease_id: str | None = Header(default=None),
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    run = _owned_run(container, worker, run_id, x_lease_id)
    return {"run_id": run.run_id, "status": run.status}


@node_router.post("/runs/{run_id}/started")
def started(
    run_id: str,
    x_lease_id: str | None = Header(default=None),
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    _owned_run(container, worker, run_id, x_lease_id)
    run = container.execution.start_run(run_id, worker.worker_id, x_lease_id)
    return {"run_id": run.run_id, "status": run.status}


@node_router.post("/runs/{run_id}/finished")
def finished(
    run_id: str,
    request: FinishRunRequest,
    x_lease_id: str | None = Header(default=None),
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    run = _owned_run(container, worker, run_id, x_lease_id, allow_terminal=True)
    if request.lease_id != x_lease_id:
        raise ForbiddenError("Некорректная аренда результата")
    if run.status is RunStatus.FINISHED:
        # A lost HTTP response may retry this upload. Never merge a changed result.
        return {"run_id": run.run_id, "status": run.status}
    match = container.execution.get_match_execution_for_run(run, include_result_payload=False)
    participants = (
        {
            container.execution.get_run(rid, include_result_payload=False).team_id
            for rid in match.run_ids
        }
        if match
        else {run.team_id}
    )
    for field in ("scores", "placements"):
        values = request.payload.get(field)
        if isinstance(values, dict) and not set(values) <= participants:
            raise InvariantViolationError("Результат содержит участника другого матча")
    if len(json.dumps(request.payload).encode()) > 32 * 1024 * 1024:
        raise InvariantViolationError("Результат превышает 32 МБ")
    result = legacy.mark_run_finished(run_id, request, None, container)
    return {"run_id": result.run_id, "status": result.status}


@node_router.post("/runs/{run_id}/failed")
def failed(
    run_id: str,
    request: FailRunRequest,
    x_lease_id: str | None = Header(default=None),
    worker=Depends(authenticated_node),
    container: ServiceContainer = Depends(get_container),
):
    _owned_run(container, worker, run_id, x_lease_id, allow_terminal=True)
    if request.lease_id != x_lease_id:
        raise ForbiddenError("Некорректная аренда результата")
    result = legacy.mark_run_failed(run_id, request, None, container)
    return {"run_id": result.run_id, "status": result.status}


router.include_router(node_router)
