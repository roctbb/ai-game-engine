"""Separate revocable credentials for internet workers."""

from alembic import op
import sqlalchemy as sa

revision = "0020_remote_workers"
down_revision = "0019_remove_catalog_visibility"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "execution_remote_worker_credentials",
        sa.Column("worker_id", sa.String(120), primary_key=True),
        sa.Column("enrollment_hash", sa.String(64), nullable=False),
        sa.Column("enrollment_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("execution_remote_worker_credentials")
