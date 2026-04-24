from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import JSON as SqlJson
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class WorkspaceTeamOrm(Base):
    __tablename__ = "workspace_teams"

    team_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    game_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(Text)
    captain_user_id: Mapped[str] = mapped_column(String(120), index=True)
    slots_json: Mapped[dict[str, dict[str, object]]] = mapped_column(SqlJson, default=dict)


class WorkspaceTeamSnapshotOrm(Base):
    __tablename__ = "workspace_team_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    team_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspace_teams.team_id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[str] = mapped_column(String(64), index=True)
    version_id: Mapped[str] = mapped_column(String(64), index=True)
    codes_by_slot_json: Mapped[dict[str, str]] = mapped_column(SqlJson, default=dict)
    revisions_by_slot_json: Mapped[dict[str, int]] = mapped_column(SqlJson, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
