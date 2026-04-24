from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class GameSourceOrm(Base):
    __tablename__ = "administration_game_sources"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    repo_url: Mapped[str] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), index=True)
    last_sync_status: Mapped[str] = mapped_column(String(32), index=True)
    last_synced_commit_sha: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GameSourceSyncOrm(Base):
    __tablename__ = "administration_game_source_syncs"

    sync_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("administration_game_sources.source_id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    build_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
