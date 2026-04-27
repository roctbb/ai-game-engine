from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from execution.domain.model import BuildJob, MatchExecution, MatchExecutionStatus, Run, RunKind, WorkerNode
from execution.infrastructure.sqlalchemy_repository import (
    SqlAlchemyBuildRepository,
    SqlAlchemyMatchExecutionRepository,
    SqlAlchemyRunRepository,
    SqlAlchemyWorkerRepository,
)
from shared.db.base import Base


def _build_session_factory() -> sessionmaker:
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_sqlalchemy_run_repository_persists_and_filters_active_runs() -> None:
    session_factory = _build_session_factory()
    repository = SqlAlchemyRunRepository(session_factory)

    run = Run.create(
        team_id='team-1',
        game_id='game-1',
        requested_by='user-1',
        run_kind=RunKind.SINGLE_TASK,
    )
    repository.save(run)

    loaded = repository.get(run.run_id)
    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert loaded.run_kind is RunKind.SINGLE_TASK

    active = repository.list_active_by_requested_by_and_kind(
        requested_by='user-1',
        run_kind=RunKind.SINGLE_TASK,
    )
    assert len(active) == 1

    run.mark_canceled()
    repository.save(run)

    active_after_cancel = repository.list_active_by_requested_by_and_kind(
        requested_by='user-1',
        run_kind=RunKind.SINGLE_TASK,
    )
    assert active_after_cancel == []


def test_sqlalchemy_match_execution_repository_roundtrip() -> None:
    session_factory = _build_session_factory()
    repository = SqlAlchemyMatchExecutionRepository(session_factory)

    match = MatchExecution.create(
        primary_run_id='run-a',
        run_ids=['run-a', 'run-b'],
        game_id='game-1',
        run_kind=RunKind.TRAINING_MATCH,
        lobby_id='lobby-1',
    )
    match.mark_queued()
    match.mark_started('worker-1')
    match.mark_finished({'scores': {'team-a': 1, 'team-b': 0}})
    repository.save(match)

    loaded = repository.get(match.match_execution_id)
    assert loaded is not None
    assert loaded.status is MatchExecutionStatus.FINISHED
    assert loaded.run_ids == ('run-a', 'run-b')
    assert loaded.result_payload == {'scores': {'team-a': 1, 'team-b': 0}}


def test_sqlalchemy_worker_repository_roundtrip() -> None:
    session_factory = _build_session_factory()
    repository = SqlAlchemyWorkerRepository(session_factory)

    worker = WorkerNode.register(
        worker_id='worker-1',
        hostname='host-a',
        capacity_total=4,
        labels={'zone': 'lab'},
    )
    repository.save(worker)

    loaded = repository.get('worker-1')
    assert loaded is not None
    assert loaded.hostname == 'host-a'
    assert loaded.capacity_total == 4
    assert loaded.labels['zone'] == 'lab'


def test_sqlalchemy_build_repository_roundtrip() -> None:
    session_factory = _build_session_factory()
    repository = SqlAlchemyBuildRepository(session_factory)

    build = BuildJob.start(game_source_id='source-1', repo_url='https://example.com/repo.git')
    build.mark_finished(image_digest='sha256:abc123')
    repository.save(build)

    loaded = repository.get(build.build_id)
    assert loaded is not None
    assert loaded.image_digest == 'sha256:abc123'
