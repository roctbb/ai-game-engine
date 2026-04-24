from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.config.settings import settings


def create_sqlalchemy_engine(database_url: str | None = None):
    return create_engine(database_url or settings.database_url, pool_pre_ping=True)


engine = create_sqlalchemy_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
