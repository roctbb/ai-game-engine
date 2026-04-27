from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy import JSON as SqlJson
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class ReplayOrm(Base):
    __tablename__ = "spectator_replays"
    __table_args__ = (
        Index("ix_spectator_replays_game_kind_updated_at", "game_id", "run_kind", "updated_at"),
    )

    replay_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    game_id: Mapped[str] = mapped_column(String(64), index=True)
    run_kind: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    visibility: Mapped[str] = mapped_column(String(32), default="public")
    frames_json: Mapped[list[dict[str, object]]] = mapped_column(SqlJson, default=list)
    events_json: Mapped[list[dict[str, object]]] = mapped_column(SqlJson, default=list)
    summary_json: Mapped[dict[str, object]] = mapped_column(SqlJson, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
