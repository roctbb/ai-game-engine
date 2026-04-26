"""Track training lobby scheduled match groups."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_training_lobby_match_groups"
down_revision = "0004_multiplayer_match_bounds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "training_lobbies" not in table_names:
        return

    columns = {item["name"] for item in inspector.get_columns("training_lobbies")}
    if "last_scheduled_match_groups_json" not in columns:
        op.add_column(
            "training_lobbies",
            sa.Column("last_scheduled_match_groups_json", sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "training_lobbies" not in table_names:
        return

    columns = {item["name"] for item in inspector.get_columns("training_lobbies")}
    if "last_scheduled_match_groups_json" in columns:
        op.drop_column("training_lobbies", "last_scheduled_match_groups_json")
