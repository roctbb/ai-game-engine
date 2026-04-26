from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Integer
from sqlalchemy import JSON as SqlJson
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class CatalogGameOrm(Base):
    __tablename__ = "catalog_games"

    game_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    learning_section: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    topics: Mapped[list[str]] = mapped_column(SqlJson, default=list)
    min_players_per_match: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_players_per_match: Mapped[int | None] = mapped_column(Integer, nullable=True)
    catalog_metadata_status: Mapped[str] = mapped_column(String(32), default="ready", index=True)
    active_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class CatalogGameVersionOrm(Base):
    __tablename__ = "catalog_game_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    game_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("catalog_games.game_id", ondelete="CASCADE"), index=True
    )
    semver: Mapped[str] = mapped_column(String(64), index=True)
    required_slots_json: Mapped[list[dict[str, object]]] = mapped_column(SqlJson, default=list)
    required_worker_labels_json: Mapped[dict[str, str]] = mapped_column(SqlJson, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
