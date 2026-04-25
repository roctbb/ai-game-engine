"""Add catalog learning sections."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_catalog_learning_section"
down_revision = "0002_identity_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "catalog_games" not in set(inspector.get_table_names()):
        return

    columns = {item["name"] for item in inspector.get_columns("catalog_games")}
    if "learning_section" not in columns:
        op.add_column("catalog_games", sa.Column("learning_section", sa.String(length=80), nullable=True))

    existing_indexes = {item["name"] for item in inspector.get_indexes("catalog_games")}
    if "ix_catalog_games_learning_section" not in existing_indexes:
        op.create_index("ix_catalog_games_learning_section", "catalog_games", ["learning_section"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "catalog_games" not in set(inspector.get_table_names()):
        return

    existing_indexes = {item["name"] for item in inspector.get_indexes("catalog_games")}
    if "ix_catalog_games_learning_section" in existing_indexes:
        op.drop_index("ix_catalog_games_learning_section", table_name="catalog_games")

    columns = {item["name"] for item in inspector.get_columns("catalog_games")}
    if "learning_section" in columns:
        op.drop_column("catalog_games", "learning_section")
