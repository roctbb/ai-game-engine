"""Store lightweight execution run result summaries."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_run_result_summary"
down_revision = "0011_run_active_lease_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "execution_runs" not in tables:
        return
    columns = {item["name"] for item in inspector.get_columns("execution_runs")}
    if "result_summary" not in columns:
        op.add_column("execution_runs", sa.Column("result_summary", sa.JSON(), nullable=True))

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE execution_runs
            SET result_summary = (
                (result_payload::jsonb - 'frames' - 'events')
                || jsonb_build_object(
                    'replay_frame_count',
                    CASE
                        WHEN jsonb_typeof(result_payload::jsonb -> 'frames') = 'array'
                        THEN jsonb_array_length(result_payload::jsonb -> 'frames')
                        ELSE 1
                    END
                )
            )::json
            WHERE result_payload IS NOT NULL
              AND result_summary IS NULL
              AND jsonb_typeof(result_payload::jsonb) = 'object'
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "execution_runs" not in tables:
        return
    columns = {item["name"] for item in inspector.get_columns("execution_runs")}
    if "result_summary" in columns:
        op.drop_column("execution_runs", "result_summary")
