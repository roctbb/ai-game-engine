"""Add multiplayer match size bounds."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_multiplayer_match_bounds"
down_revision = "0003_catalog_learning_section"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "catalog_games" in table_names:
        columns = {item["name"] for item in inspector.get_columns("catalog_games")}
        if "min_players_per_match" not in columns:
            op.add_column("catalog_games", sa.Column("min_players_per_match", sa.Integer(), nullable=True))
        if "max_players_per_match" not in columns:
            op.add_column("catalog_games", sa.Column("max_players_per_match", sa.Integer(), nullable=True))

        op.execute(
            """
            UPDATE catalog_games
            SET min_players_per_match = COALESCE(min_players_per_match, 2),
                max_players_per_match = COALESCE(max_players_per_match, 2),
                mode = 'multiplayer'
            WHERE mode = 'small_match'
            """
        )
        op.execute(
            """
            UPDATE catalog_games
            SET min_players_per_match = COALESCE(min_players_per_match, 2),
                max_players_per_match = COALESCE(max_players_per_match, 64),
                mode = 'multiplayer'
            WHERE mode = 'massive_lobby'
            """
        )

    if "competitions" in table_names:
        columns = {item["name"] for item in inspector.get_columns("competitions")}
        if "min_match_size" not in columns:
            op.add_column(
                "competitions",
                sa.Column("min_match_size", sa.Integer(), nullable=False, server_default="2"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "competitions" in table_names:
        columns = {item["name"] for item in inspector.get_columns("competitions")}
        if "min_match_size" in columns:
            op.drop_column("competitions", "min_match_size")

    if "catalog_games" in table_names:
        columns = {item["name"] for item in inspector.get_columns("catalog_games")}
        if "max_players_per_match" in columns:
            op.drop_column("catalog_games", "max_players_per_match")
        if "min_players_per_match" in columns:
            op.drop_column("catalog_games", "min_players_per_match")
