"""Run the production SQL dialect as well as SQLite for execution context lookups."""

from contextlib import contextmanager
import os
from pathlib import Path
import runpy
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import BigInteger, create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from execution.application.service import CreateRunInput
from execution.domain.model import MatchExecution, RunKind, RunStatus
from execution.infrastructure.sqlalchemy_repository import (
    SqlAlchemyMatchExecutionRepository,
    SqlAlchemyRunRepository,
    SqlAlchemyWorkerRepository,
)
from shared.db.base import Base
from test_distributed_execution import distributed, ready_team  # noqa: F401
import worker_service.main as worker


@contextmanager
def isolated_postgres_sessions(url, *, create_tables=True):
    schema = "execution_regression_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        if create_tables:
            Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture(params=["sqlite", "postgresql"])
def execution_sessions(request, tmp_path):
    if request.param == "postgresql":
        url = os.getenv("POSTGRES_TEST_URL")
        if not url:
            pytest.skip("POSTGRES_TEST_URL required; CI always supplies PostgreSQL")
        with isolated_postgres_sessions(url) as sessions:
            yield sessions
    else:
        engine = create_engine(
            f"sqlite+pysqlite:///{tmp_path / 'execution.sqlite'}",
            connect_args={"check_same_thread": False},
        )
        try:
            Base.metadata.create_all(engine)
            yield sessionmaker(bind=engine)
        finally:
            engine.dispose()


def test_exact_secondary_membership_and_absent_match(execution_sessions):
    repository = SqlAlchemyMatchExecutionRepository(execution_sessions)
    assert repository.find_by_run_id("unknown-single-task") is None
    match = MatchExecution.create(
        primary_run_id="run-primary",
        run_ids=["run-primary", "run-secondary", "run_%_literal", 'run-"quoted"', "run-игрок"],
        game_id="game",
        run_kind=RunKind.TRAINING_MATCH,
        lobby_id=None,
    )
    repository.save(match)
    for run_id in match.run_ids:
        found = repository.find_by_run_id(run_id, include_result_payload=False)
        assert found.match_execution_id == match.match_execution_id
        assert found.result_payload is None
    for absent in ("run", "secondary", "run-second", "run-primar", "run_XX_literal", "run-игро"):
        assert repository.find_by_run_id(absent) is None


def test_single_task_never_queries_match_repository(container, monkeypatch):
    game, team = ready_team(
        container, "knight_coins_v1", "single-skip", "def make_move(x, y, board): return (1, 2)"
    )
    run = container.execution.create_run(
        CreateRunInput(team.team_id, game.game_id, "single-skip", RunKind.SINGLE_TASK)
    )

    def unexpected_lookup(*args, **kwargs):
        raise AssertionError("An individual task cannot belong to a multiplayer match")

    monkeypatch.setattr(
        container.execution._match_execution_repository, "find_by_run_id", unexpected_lookup
    )
    assert container.execution.get_match_execution_for_run(run) is None


def test_knight_coins_full_worker_pipeline_with_sql_repositories(execution_sessions, distributed):  # noqa: F811
    container, queue = distributed
    container.execution._run_repository = SqlAlchemyRunRepository(execution_sessions)
    container.execution._match_execution_repository = SqlAlchemyMatchExecutionRepository(
        execution_sessions
    )
    container.execution._worker_repository = SqlAlchemyWorkerRepository(execution_sessions)
    game, team = ready_team(
        container, "knight_coins_v1", "knight-postgres", "def make_move(x, y, board): return (1, 2)"
    )
    run = container.execution.create_run(
        CreateRunInput(team.team_id, game.game_id, "knight-postgres", RunKind.SINGLE_TASK)
    )
    container.execution.queue_run(run.run_id)
    response = worker._pull_and_execute_once()
    assert response["status"] == "completed"
    completed = container.execution.get_run(run.run_id)
    assert completed.status is RunStatus.FINISHED
    assert container.spectator_replay.get_by_run_id(run.run_id).frames
    assert queue.stats()["known_count"] == 0


def test_postgres_upgrades_existing_lease_generation_without_losing_data():
    url = os.getenv("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_URL required; CI always supplies PostgreSQL")
    migration = runpy.run_path(
        str(Path(__file__).parents[1] / "alembic/versions/0016_lease_generation_bigint.py")
    )
    with isolated_postgres_sessions(url, create_tables=False) as sessions:
        with sessions.kw["bind"].begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE execution_runs (run_id TEXT PRIMARY KEY, "
                    "lease_generation INTEGER NOT NULL DEFAULT 0)"
                )
            )
            connection.execute(
                text("INSERT INTO execution_runs (run_id, lease_generation) VALUES ('legacy', 42)")
            )
            assert not isinstance(
                inspect(connection).get_columns("execution_runs")[1]["type"], BigInteger
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration["upgrade"]()
            assert isinstance(
                inspect(connection).get_columns("execution_runs")[1]["type"], BigInteger
            )
            assert connection.scalar(text("SELECT lease_generation FROM execution_runs")) == 42
            generation = 1_794_127_581_537_768
            connection.execute(
                text("UPDATE execution_runs SET lease_generation = :generation"),
                {"generation": generation},
            )
            assert (
                connection.scalar(text("SELECT lease_generation FROM execution_runs")) == generation
            )
            connection.execute(text("INSERT INTO execution_runs (run_id) VALUES ('new')"))
            assert (
                connection.scalar(
                    text("SELECT lease_generation FROM execution_runs WHERE run_id = 'new'")
                )
                == 0
            )
