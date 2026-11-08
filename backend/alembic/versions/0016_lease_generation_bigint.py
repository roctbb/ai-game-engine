"""Persist time-based lease generations without overflowing PostgreSQL INTEGER."""

from alembic import op
import sqlalchemy as sa

revision = "0016_lease_generation_bigint"
down_revision = "0015_execution_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite INTEGER already stores signed 64-bit values and cannot ALTER TYPE.
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "execution_runs",
            "lease_generation",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # PostgreSQL rejects values outside INTEGER's range instead of truncating them.
        op.alter_column(
            "execution_runs",
            "lease_generation",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
