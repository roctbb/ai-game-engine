"""Add indexes for lobby run lookups."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_execution_run_lobby_indexes"
down_revision = "0006_lobby_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "execution_runs" not in set(inspector.get_table_names()):
        return

    existing_indexes = {item["name"] for item in inspector.get_indexes("execution_runs")}
    if "ix_execution_runs_lobby_id" not in existing_indexes:
        op.create_index("ix_execution_runs_lobby_id", "execution_runs", ["lobby_id"], unique=False)
    if "ix_execution_runs_lobby_kind_created_at" not in existing_indexes:
        op.create_index(
            "ix_execution_runs_lobby_kind_created_at",
            "execution_runs",
            ["lobby_id", "run_kind", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "execution_runs" not in set(inspector.get_table_names()):
        return

    existing_indexes = {item["name"] for item in inspector.get_indexes("execution_runs")}
    if "ix_execution_runs_lobby_kind_created_at" in existing_indexes:
        op.drop_index("ix_execution_runs_lobby_kind_created_at", table_name="execution_runs")
    if "ix_execution_runs_lobby_id" in existing_indexes:
        op.drop_index("ix_execution_runs_lobby_id", table_name="execution_runs")
