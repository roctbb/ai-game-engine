"""Add persistent identity sessions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_identity_sessions"
down_revision = "0001_v2_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "identity_sessions" not in table_names:
        op.create_table(
            "identity_sessions",
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("external_user_id", sa.String(length=255), nullable=False),
            sa.Column("nickname", sa.String(length=120), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("session_id"),
        )

    existing_indexes = {item["name"] for item in sa.inspect(bind).get_indexes("identity_sessions")}
    _create_index_if_missing(existing_indexes, "ix_identity_sessions_external_user_id", ["external_user_id"])
    _create_index_if_missing(existing_indexes, "ix_identity_sessions_nickname", ["nickname"])
    _create_index_if_missing(existing_indexes, "ix_identity_sessions_role", ["role"])
    _create_index_if_missing(existing_indexes, "ix_identity_sessions_provider", ["provider"])
    _create_index_if_missing(existing_indexes, "ix_identity_sessions_created_at", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "identity_sessions" not in set(inspector.get_table_names()):
        return

    existing_indexes = {item["name"] for item in inspector.get_indexes("identity_sessions")}
    for index_name in (
        "ix_identity_sessions_created_at",
        "ix_identity_sessions_provider",
        "ix_identity_sessions_role",
        "ix_identity_sessions_nickname",
        "ix_identity_sessions_external_user_id",
    ):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="identity_sessions")
    op.drop_table("identity_sessions")


def _create_index_if_missing(existing_indexes: set[str], index_name: str, columns: list[str]) -> None:
    if index_name in existing_indexes:
        return
    op.create_index(index_name, "identity_sessions", columns, unique=False)
