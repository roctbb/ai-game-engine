from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from identity.domain.model import AppSession, AuthProvider, UserRole
from identity.infrastructure.sqlalchemy_repository import SqlAlchemySessionRepository
from shared.db.base import Base
import shared.db.models as _db_models


def _build_session_factory() -> sessionmaker:
    _ = _db_models
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_sqlalchemy_session_repository_roundtrip_and_delete() -> None:
    session_factory = _build_session_factory()
    repository = SqlAlchemySessionRepository(session_factory)

    app_session = AppSession.create(
        external_user_id="dev:student-1",
        nickname="student-1",
        role=UserRole.STUDENT,
        provider=AuthProvider.DEV,
    )
    repository.save(app_session)

    loaded = repository.get(app_session.session_id)
    assert loaded is not None
    assert loaded.session_id == app_session.session_id
    assert loaded.external_user_id == "dev:student-1"
    assert loaded.nickname == "student-1"
    assert loaded.role is UserRole.STUDENT
    assert loaded.provider is AuthProvider.DEV

    repository.delete(app_session.session_id)
    assert repository.get(app_session.session_id) is None
