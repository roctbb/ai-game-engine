from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy import JSON as SqlJson
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class LobbyOrm(Base):
    __tablename__ = "training_lobbies"

    lobby_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    game_id: Mapped[str] = mapped_column(String(64), index=True)
    game_version_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)

    kind: Mapped[str] = mapped_column(String(32), index=True)
    access: Mapped[str] = mapped_column(String(32), index=True)
    access_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    max_teams: Mapped[int]
    status: Mapped[str] = mapped_column(String(32), index=True)

    teams_json: Mapped[dict[str, dict[str, object]]] = mapped_column(SqlJson, default=dict)
    last_scheduled_run_ids_json: Mapped[list[str]] = mapped_column(SqlJson, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
