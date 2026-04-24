from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy import JSON as SqlJson
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class CompetitionOrm(Base):
    __tablename__ = "competitions"

    competition_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    game_id: Mapped[str] = mapped_column(String(64), index=True)
    game_version_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(32), index=True)
    tie_break_policy: Mapped[str] = mapped_column(String(32))
    advancement_top_k: Mapped[int]
    match_size: Mapped[int]
    status: Mapped[str] = mapped_column(String(32), index=True)

    entrants_json: Mapped[dict[str, dict[str, object]]] = mapped_column(SqlJson, default=dict)
    rounds_json: Mapped[list[dict[str, object]]] = mapped_column(SqlJson, default=list)
    current_round_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    winner_team_ids_json: Mapped[list[str]] = mapped_column(SqlJson, default=list)
    pending_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scheduled_run_ids_json: Mapped[list[str]] = mapped_column(SqlJson, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
