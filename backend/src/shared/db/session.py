from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.config.settings import settings


def create_sqlalchemy_engine(database_url: str | None = None):
    return create_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_timeout=30,
    )
