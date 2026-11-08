"""Store optional reproducibility and debug settings without changing game contracts."""
from alembic import op
import sqlalchemy as sa

revision = "0014_run_execution_options"
down_revision = "0013_catalog_game_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "execution_runs" in inspector.get_table_names() and "execution_options" not in {
        c["name"] for c in inspector.get_columns("execution_runs")
    }:
        op.add_column("execution_runs", sa.Column("execution_options", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("execution_runs", "execution_options")
