"""Add index for spectator replay list lookups."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_spectator_replay_list_indexes"
down_revision = "0007_execution_run_lobby_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "spectator_replays" not in set(inspector.get_table_names()):
        return

    existing_indexes = {item["name"] for item in inspector.get_indexes("spectator_replays")}
    if "ix_spectator_replays_game_kind_updated_at" not in existing_indexes:
        op.create_index(
            "ix_spectator_replays_game_kind_updated_at",
            "spectator_replays",
            ["game_id", "run_kind", "updated_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "spectator_replays" not in set(inspector.get_table_names()):
        return

    existing_indexes = {item["name"] for item in inspector.get_indexes("spectator_replays")}
    if "ix_spectator_replays_game_kind_updated_at" in existing_indexes:
        op.drop_index("ix_spectator_replays_game_kind_updated_at", table_name="spectator_replays")
