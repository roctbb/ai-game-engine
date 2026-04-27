from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy import JSON as SqlJson
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class RunOrm(Base):
    __tablename__ = "execution_runs"
    __table_args__ = (
        Index("ix_execution_runs_lobby_kind_created_at", "lobby_id", "run_kind", "created_at"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(64), index=True)
    game_id: Mapped[str] = mapped_column(String(64), index=True)
    requested_by: Mapped[str] = mapped_column(String(120), index=True)
    run_kind: Mapped[str] = mapped_column(String(32), index=True)
    lobby_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    target_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(32), index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revisions_by_slot: Mapped[dict[str, int]] = mapped_column(SqlJson, default=dict)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    result_payload: Mapped[dict[str, object] | None] = mapped_column(SqlJson, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkerOrm(Base):
    __tablename__ = "execution_workers"

    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255))
    capacity_total: Mapped[int] = mapped_column(Integer)
    capacity_available: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    labels: Mapped[dict[str, str]] = mapped_column(SqlJson, default=dict)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BuildOrm(Base):
    __tablename__ = "execution_builds"

    build_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    game_source_id: Mapped[str] = mapped_column(String(120), index=True)
    repo_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    image_digest: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
