from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class IdentitySessionOrm(Base):
    __tablename__ = "identity_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_user_id: Mapped[str] = mapped_column(String(255), index=True)
    nickname: Mapped[str] = mapped_column(String(120), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
