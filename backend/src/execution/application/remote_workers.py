from datetime import UTC, timedelta
import hashlib
import secrets

from execution.application.service import RegisterWorkerInput, UpdateWorkerStatusInput
from execution.domain.model import WorkerStatus
from execution.domain.remote_worker import RemoteWorkerCredential
from shared.kernel import InvariantViolationError, UnauthorizedError, new_id, utc_now


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class RemoteWorkerService:
    def __init__(self, repository, execution):
        self.repository = repository
        self.execution = execution

    def add(self, name: str, slots: int, labels: dict[str, str]):
        worker_id = new_id("external")
        self.execution.register_worker(
            RegisterWorkerInput(
                worker_id=worker_id, hostname=name, capacity_total=slots, labels=labels
            )
        )
        return worker_id, self.issue_enrollment(worker_id, create=True)

    def issue_enrollment(self, worker_id: str, *, create=False):
        key = f"enroll.{worker_id}.{secrets.token_urlsafe(32)}"
        expires = utc_now() + timedelta(minutes=30)
        if create:
            self.repository.save(RemoteWorkerCredential(worker_id, secret_hash(key), expires))
        else:
            with self.repository.mutate(worker_id) as credential:
                credential.enrollment_hash = secret_hash(key)
                credential.enrollment_expires_at = expires
                credential.token_hash = None
                credential.connected_at = None
                credential.revoked_at = None
        self.execution.update_worker_status(
            UpdateWorkerStatusInput(worker_id, WorkerStatus.OFFLINE)
        )
        return key, expires

    def enroll(self, key: str, token: str):
        parts = key.split(".")
        if len(parts) != 3 or parts[0] != "enroll":
            raise UnauthorizedError("Неверный ключ подключения")
        worker_id = parts[1]
        if not token.startswith(f"worker.{worker_id}."):
            raise UnauthorizedError("Неверный токен машины")
        if self.repository.get(worker_id) is None:
            raise UnauthorizedError("Неверный ключ подключения")
        with self.repository.mutate(worker_id) as credential:
            if (
                credential.revoked_at
                or _aware(credential.enrollment_expires_at) <= utc_now()
                or not secrets.compare_digest(credential.enrollment_hash, secret_hash(key))
            ):
                raise UnauthorizedError("Ключ подключения отозван или истёк")
            digest = secret_hash(token)
            if credential.token_hash and not secrets.compare_digest(credential.token_hash, digest):
                raise UnauthorizedError("Ключ подключения уже использован")
            credential.token_hash = digest
            credential.connected_at = credential.connected_at or utc_now()
        worker = self.execution.get_worker(worker_id)
        if worker.status is WorkerStatus.OFFLINE:
            self.execution.worker_heartbeat(worker_id, worker.capacity_total)
        return self.execution.get_worker(worker_id)

    def authenticate(self, token: str):
        parts = token.split(".")
        credential = (
            self.repository.get(parts[1]) if len(parts) == 3 and parts[0] == "worker" else None
        )
        if (
            credential is None
            or credential.revoked_at
            or not credential.token_hash
            or not secrets.compare_digest(credential.token_hash, secret_hash(token))
        ):
            raise UnauthorizedError("Токен машины отозван или неверен")
        return self.execution.get_worker(credential.worker_id)

    def revoke(self, worker_id: str):
        with self.repository.mutate(worker_id) as credential:
            credential.revoked_at = utc_now()
            credential.token_hash = None
        return self.execution.update_worker_status(
            UpdateWorkerStatusInput(worker_id, WorkerStatus.DISABLED)
        )

    def metadata(self, worker_id: str):
        credential = self.repository.get(worker_id)
        if credential is None:
            return {"connection_type": "internal"}
        state = (
            "revoked"
            if credential.revoked_at
            else "active"
            if credential.token_hash
            else ("expired" if _aware(credential.enrollment_expires_at) <= utc_now() else "pending")
        )
        return {
            "connection_type": "external",
            "token_status": state,
            "enrollment_expires_at": credential.enrollment_expires_at,
        }

    def require_enabled(self, worker):
        if worker.status is WorkerStatus.DISABLED:
            raise InvariantViolationError("Машина отключена администратором")
