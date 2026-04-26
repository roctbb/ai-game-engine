"""Add lobby management settings."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_lobby_management"
down_revision = "0005_training_lobby_match_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "training_lobbies" not in table_names:
        return

    columns = {item["name"] for item in inspector.get_columns("training_lobbies")}
    if "auto_delete_training_runs_days" not in columns:
        op.add_column(
            "training_lobbies",
            sa.Column("auto_delete_training_runs_days", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "training_lobbies" not in table_names:
        return

    columns = {item["name"] for item in inspector.get_columns("training_lobbies")}
    if "auto_delete_training_runs_days" in columns:
        op.drop_column("training_lobbies", "auto_delete_training_runs_days")
