from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from identity.domain.model import AppSession, AuthProvider, UserRole
from identity.infrastructure.sqlalchemy_models import IdentitySessionOrm


class SqlAlchemySessionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, app_session: AppSession) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_session_to_orm(app_session))

    def get(self, session_id: str) -> AppSession | None:
        with self._session_factory() as session:
            row = session.scalar(select(IdentitySessionOrm).where(IdentitySessionOrm.session_id == session_id))
            return None if row is None else _map_session_from_orm(row)

    def delete(self, session_id: str) -> None:
        with self._session_factory.begin() as session:
            row = session.get(IdentitySessionOrm, session_id)
            if row is not None:
                session.delete(row)


def _map_session_to_orm(app_session: AppSession) -> IdentitySessionOrm:
    return IdentitySessionOrm(
        session_id=app_session.session_id,
        external_user_id=app_session.external_user_id,
        nickname=app_session.nickname,
        role=app_session.role.value,
        provider=app_session.provider.value,
        created_at=app_session.created_at,
    )


def _map_session_from_orm(row: IdentitySessionOrm) -> AppSession:
    return AppSession(
        session_id=row.session_id,
        external_user_id=row.external_user_id,
        nickname=row.nickname,
        role=UserRole(row.role),
        provider=AuthProvider(row.provider),
        created_at=row.created_at,
    )
