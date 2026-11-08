from datetime import UTC, datetime
from pathlib import Path
import runpy

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import Boolean, DateTime, Integer, select
from sqlalchemy import JSON as SqlJson

from shared.db.base import Base
from test_postgres_execution_context import execution_sessions  # noqa: F401


TABLE_NAMES = {
    "catalog_games",
    "catalog_game_versions",
    "workspace_teams",
    "workspace_team_snapshots",
    "execution_runs",
    "execution_match_executions",
    "spectator_replays",
    "training_lobbies",
    "competitions",
}


def seed_game_graph(connection, prefix, slug, *, mode="single_task", status="finished"):
    """Populate the actual SQL schema, including versions and team snapshot FKs."""
    for table in Base.metadata.sorted_tables:
        if table.name not in TABLE_NAMES:
            continue
        values = {}
        for column in table.columns:
            if column.nullable or column.default is not None or column.server_default is not None:
                continue
            if isinstance(column.type, DateTime):
                value = datetime.now(tz=UTC)
            elif isinstance(column.type, Boolean):
                value = False
            elif isinstance(column.type, Integer):
                value = 1
            elif isinstance(column.type, SqlJson):
                value = {"marker": prefix}
            else:
                value = f"{prefix}-{column.name}"
            values[column.name] = value
        values["game_id"] = f"{prefix}-game_id"
        if table.name == "catalog_games":
            values.update(slug=slug, mode=mode)
        if table.name == "execution_runs":
            values["status"] = status
        connection.execute(table.insert().values(**values))


def snapshot(connection):
    return {
        name: list(connection.execute(select(Base.metadata.tables[name]))) for name in TABLE_NAMES
    }


def removal_migration():
    return runpy.run_path(
        str(Path(__file__).parents[1] / "alembic/versions/0017_remove_intro_tasks.py")
    )["upgrade"]


def test_removal_deletes_only_selected_single_task_graphs(execution_sessions):  # noqa: F811
    engine = execution_sessions.kw["bind"]
    with engine.begin() as connection:
        seed_game_graph(connection, "removed", "gate_guard_v1")
        seed_game_graph(connection, "kept", "maze_escape_v1")
        seed_game_graph(connection, "custom", "wall_archer_v1", mode="multiplayer")
        before = snapshot(connection)
        upgrade = removal_migration()
        with Operations.context(MigrationContext.configure(connection)):
            upgrade()
            upgrade()
        after = snapshot(connection)
        for name in TABLE_NAMES:
            assert after[name] == [row for row in before[name] if row.game_id != "removed-game_id"]


def test_removal_refuses_to_delete_an_active_engine_attempt(execution_sessions):  # noqa: F811
    engine = execution_sessions.kw["bind"]
    with engine.begin() as connection:
        seed_game_graph(connection, "active", "gate_guard_v1", status="running")
        before = snapshot(connection)
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="Stop active runs"):
                removal_migration()()
        assert snapshot(connection) == before
