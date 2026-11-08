"""Fence concurrent run updates and persist scheduler/replay delivery intent."""

from alembic import op
import sqlalchemy as sa

revision = "0015_execution_reliability"
down_revision = "0014_run_execution_options"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("execution_runs")}
    for name, kind, default in (
        ("revision", sa.Integer(), "1"),
        ("lease_generation", sa.Integer(), "0"),
        ("dispatch_pending", sa.Boolean(), "false"),
        ("completion_pending", sa.Boolean(), "false"),
    ):
        if name not in columns:
            op.add_column(
                "execution_runs", sa.Column(name, kind, nullable=False, server_default=default)
            )
    match_columns = {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns("execution_match_executions")
    }
    if "revision" not in match_columns:
        op.add_column(
            "execution_match_executions",
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        )
    # Cutover stops old workers. Re-deliver orphaned RUNNING attempts as well as queued jobs.
    op.execute("""UPDATE execution_runs SET status='queued', started_at=NULL, dispatch_pending=true
        WHERE status='running' AND (match_primary_run_id IS NULL OR match_primary_run_id=run_id)""")
    op.execute("""UPDATE execution_runs SET dispatch_pending=true WHERE status='queued'
        AND (match_primary_run_id IS NULL OR match_primary_run_id=run_id)""")
    # Keep the oldest active attempt when upgrading a database containing duplicates.
    op.execute("""UPDATE execution_runs SET status='canceled', error_message='duplicate_active_attempt_migration',
        dispatch_pending=false, completion_pending=true, finished_at=CURRENT_TIMESTAMP
        WHERE run_id IN (SELECT run_id FROM (SELECT run_id, ROW_NUMBER() OVER
        (PARTITION BY requested_by ORDER BY created_at, run_id) AS position
        FROM execution_runs WHERE run_kind='single_task' AND status IN ('queued','running')) AS duplicates
        WHERE position > 1)""")
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("execution_runs")}
    if "uq_execution_single_task_active_user" not in indexes:
        condition = sa.text("run_kind = 'single_task' AND status IN ('queued', 'running')")
        op.create_index(
            "uq_execution_single_task_active_user",
            "execution_runs",
            ["requested_by"],
            unique=True,
            postgresql_where=condition,
            sqlite_where=condition,
        )
    for name in ("dispatch_pending", "completion_pending"):
        if f"ix_execution_runs_{name}" not in indexes:
            op.create_index(f"ix_execution_runs_{name}", "execution_runs", [name])


def downgrade() -> None:
    op.drop_column("execution_match_executions", "revision")
    op.drop_index("uq_execution_single_task_active_user", table_name="execution_runs")
    for name in ("dispatch_pending", "completion_pending"):
        op.drop_index(f"ix_execution_runs_{name}", table_name="execution_runs")
    for name in ("completion_pending", "dispatch_pending", "lease_generation", "revision"):
        op.drop_column("execution_runs", name)
