"""Remove task publication and catalog visibility states."""

from alembic import op
import sqlalchemy as sa

revision = "0019_remove_catalog_visibility"
down_revision = "0018_competition_presentation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("catalog_games") as batch:
        batch.drop_index("ix_catalog_games_catalog_metadata_status")
        batch.drop_index("ix_catalog_games_is_hidden")
        batch.drop_column("catalog_metadata_status")
        batch.drop_column("is_hidden")


def downgrade() -> None:
    with op.batch_alter_table("catalog_games") as batch:
        batch.add_column(sa.Column("catalog_metadata_status", sa.String(32), nullable=False, server_default="ready"))
        batch.add_column(sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_index("ix_catalog_games_catalog_metadata_status", ["catalog_metadata_status"])
        batch.create_index("ix_catalog_games_is_hidden", ["is_hidden"])
