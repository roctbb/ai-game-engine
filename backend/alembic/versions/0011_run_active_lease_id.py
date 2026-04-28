"""Track active execution lease for runs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_run_active_lease_id"
down_revision = "0010_lobby_cumulative_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "execution_runs" not in tables:
        return
    columns = {item["name"] for item in inspector.get_columns("execution_runs")}
    if "active_lease_id" not in columns:
        op.add_column(
            "execution_runs",
            sa.Column("active_lease_id", sa.String(length=120), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "execution_runs" not in tables:
        return
    columns = {item["name"] for item in inspector.get_columns("execution_runs")}
    if "active_lease_id" in columns:
        op.drop_column("execution_runs", "active_lease_id")
