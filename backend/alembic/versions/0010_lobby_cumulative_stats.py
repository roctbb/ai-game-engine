"""Store cumulative training lobby stats."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_lobby_cumulative_stats"
down_revision = "0009_match_executions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "training_lobbies" not in tables:
        return
    columns = {item["name"] for item in inspector.get_columns("training_lobbies")}
    if "cumulative_stats_by_team_json" not in columns:
        op.add_column(
            "training_lobbies",
            sa.Column("cumulative_stats_by_team_json", sa.JSON(), nullable=True),
        )
        op.execute(
            "UPDATE training_lobbies "
            "SET cumulative_stats_by_team_json = '{}' "
            "WHERE cumulative_stats_by_team_json IS NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "training_lobbies" not in tables:
        return
    columns = {item["name"] for item in inspector.get_columns("training_lobbies")}
    if "cumulative_stats_by_team_json" in columns:
        op.drop_column("training_lobbies", "cumulative_stats_by_team_json")
