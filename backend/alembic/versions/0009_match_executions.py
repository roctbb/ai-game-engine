"""Add match executions for one worker job per multiplayer match."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_match_executions"
down_revision = "0008_replay_list_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "execution_match_executions" not in tables:
        op.create_table(
            "execution_match_executions",
            sa.Column("match_execution_id", sa.String(length=64), nullable=False),
            sa.Column("primary_run_id", sa.String(length=64), nullable=False),
            sa.Column("run_ids", sa.JSON(), nullable=False),
            sa.Column("game_id", sa.String(length=64), nullable=False),
            sa.Column("run_kind", sa.String(length=32), nullable=False),
            sa.Column("lobby_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("worker_id", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("result_payload", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("match_execution_id"),
        )
        op.create_index(
            "ix_execution_match_executions_primary_run_id",
            "execution_match_executions",
            ["primary_run_id"],
            unique=False,
        )
        op.create_index(
            "ix_execution_match_executions_game_id",
            "execution_match_executions",
            ["game_id"],
            unique=False,
        )
        op.create_index(
            "ix_execution_match_executions_run_kind",
            "execution_match_executions",
            ["run_kind"],
            unique=False,
        )
        op.create_index(
            "ix_execution_match_executions_lobby_id",
            "execution_match_executions",
            ["lobby_id"],
            unique=False,
        )
        op.create_index(
            "ix_execution_match_executions_status",
            "execution_match_executions",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_execution_match_executions_created_at",
            "execution_match_executions",
            ["created_at"],
            unique=False,
        )
        op.create_index(
            "ix_execution_match_executions_lobby_kind_created_at",
            "execution_match_executions",
            ["lobby_id", "run_kind", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_execution_match_executions_game_kind_created_at",
            "execution_match_executions",
            ["game_id", "run_kind", "created_at"],
            unique=False,
        )

    if "execution_runs" not in tables:
        return

    run_columns = {item["name"] for item in inspector.get_columns("execution_runs")}
    if "match_execution_id" not in run_columns:
        op.add_column(
            "execution_runs",
            sa.Column("match_execution_id", sa.String(length=64), nullable=True),
        )
        op.create_index(
            "ix_execution_runs_match_execution_id",
            "execution_runs",
            ["match_execution_id"],
            unique=False,
        )
    if "match_primary_run_id" not in run_columns:
        op.add_column(
            "execution_runs",
            sa.Column("match_primary_run_id", sa.String(length=64), nullable=True),
        )
        op.create_index(
            "ix_execution_runs_match_primary_run_id",
            "execution_runs",
            ["match_primary_run_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "execution_runs" in tables:
        run_columns = {item["name"] for item in inspector.get_columns("execution_runs")}
        run_indexes = {item["name"] for item in inspector.get_indexes("execution_runs")}
        if "ix_execution_runs_match_primary_run_id" in run_indexes:
            op.drop_index("ix_execution_runs_match_primary_run_id", table_name="execution_runs")
        if "match_primary_run_id" in run_columns:
            op.drop_column("execution_runs", "match_primary_run_id")
        if "ix_execution_runs_match_execution_id" in run_indexes:
            op.drop_index("ix_execution_runs_match_execution_id", table_name="execution_runs")
        if "match_execution_id" in run_columns:
            op.drop_column("execution_runs", "match_execution_id")

    if "execution_match_executions" not in tables:
        return
    indexes = {item["name"] for item in inspector.get_indexes("execution_match_executions")}
    for index_name in (
        "ix_execution_match_executions_game_kind_created_at",
        "ix_execution_match_executions_lobby_kind_created_at",
        "ix_execution_match_executions_created_at",
        "ix_execution_match_executions_status",
        "ix_execution_match_executions_lobby_id",
        "ix_execution_match_executions_run_kind",
        "ix_execution_match_executions_game_id",
        "ix_execution_match_executions_primary_run_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="execution_match_executions")
    op.drop_table("execution_match_executions")
