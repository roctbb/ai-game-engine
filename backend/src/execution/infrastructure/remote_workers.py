from contextlib import contextmanager
from copy import deepcopy
from threading import RLock

from sqlalchemy import DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from execution.domain.remote_worker import RemoteWorkerCredential
from shared.db.base import Base
from shared.kernel import NotFoundError


class RemoteWorkerCredentialOrm(Base):
    __tablename__ = "execution_remote_worker_credentials"

    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    enrollment_hash: Mapped[str] = mapped_column(String(64))
    enrollment_expires_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connected_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _from_row(row):
    return RemoteWorkerCredential(
        **{key: getattr(row, key) for key in RemoteWorkerCredential.__dataclass_fields__}
    )


class InMemoryRemoteWorkerRepository:
    def __init__(self):
        self._items = {}
        self._lock = RLock()

    def get(self, worker_id):
        with self._lock:
            return deepcopy(self._items.get(worker_id))

    def save(self, credential):
        with self._lock:
            self._items[credential.worker_id] = deepcopy(credential)

    @contextmanager
    def mutate(self, worker_id):
        with self._lock:
            credential = self.get(worker_id)
            if credential is None:
                raise NotFoundError("Машина не найдена")
            yield credential
            self.save(credential)


class SqlAlchemyRemoteWorkerRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def get(self, worker_id):
        with self._session_factory() as session:
            row = session.get(RemoteWorkerCredentialOrm, worker_id)
            return _from_row(row) if row is not None else None

    def save(self, credential):
        with self._session_factory() as session, session.begin():
            session.merge(RemoteWorkerCredentialOrm(**vars(credential)))

    @contextmanager
    def mutate(self, worker_id):
        with self._session_factory() as session, session.begin():
            row = session.scalar(
                select(RemoteWorkerCredentialOrm)
                .where(RemoteWorkerCredentialOrm.worker_id == worker_id)
                .with_for_update()
            )
            if row is None:
                raise NotFoundError("Машина не найдена")
            credential = _from_row(row)
            yield credential
            for key, value in vars(credential).items():
                setattr(row, key, value)
