"""Add catalog game visibility flag."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_catalog_game_visibility"
down_revision = "0012_run_result_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "catalog_games" not in set(inspector.get_table_names()):
        return

    columns = {item["name"] for item in inspector.get_columns("catalog_games")}
    if "is_hidden" not in columns:
        op.add_column(
            "catalog_games",
            sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    indexes = {item["name"] for item in inspector.get_indexes("catalog_games")}
    if "ix_catalog_games_is_hidden" not in indexes:
        op.create_index("ix_catalog_games_is_hidden", "catalog_games", ["is_hidden"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "catalog_games" not in set(inspector.get_table_names()):
        return

    indexes = {item["name"] for item in inspector.get_indexes("catalog_games")}
    if "ix_catalog_games_is_hidden" in indexes:
        op.drop_index("ix_catalog_games_is_hidden", table_name="catalog_games")

    columns = {item["name"] for item in inspector.get_columns("catalog_games")}
    if "is_hidden" in columns:
        op.drop_column("catalog_games", "is_hidden")
