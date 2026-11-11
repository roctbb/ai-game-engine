"""Add an opt-in shared sequential tournament broadcast."""

from alembic import op
import sqlalchemy as sa

revision = "0018_competition_presentation"
down_revision = "0017_remove_intro_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("competitions", sa.Column("presentation_mode", sa.String(32), nullable=False, server_default="instant"))


def downgrade() -> None:
    op.drop_column("competitions", "presentation_mode")
