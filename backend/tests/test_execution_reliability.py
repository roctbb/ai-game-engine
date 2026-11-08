from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from execution.application.service import CreateRunInput, RegisterWorkerInput
from execution.domain.model import Run, RunKind, RunStatus
from execution.infrastructure.sqlalchemy_repository import SqlAlchemyRunRepository
from shared.db.base import Base
from shared.kernel import ConflictError, InvariantViolationError, NotFoundError


def queued_run(container):
    game = next(g for g in container.game_catalog.list_games() if g.slug == "snake_v1")
    team = container.team_workspace.create_team(game.game_id, "Reliability", "audit")
    container.team_workspace.update_slot_code(
        team.team_id, "audit", "agent", "def make_move(*args): return 'right'\n"
    )
    run = container.execution.create_run(
        CreateRunInput(team.team_id, game.game_id, "audit", RunKind.SINGLE_TASK)
    )
    return container.execution.queue_run(run.run_id)


def test_new_generation_recovers_running_attempt_and_fences_old_worker(container):
    run = queued_run(container)
    for worker in ("old", "new"):
        container.execution.register_worker(RegisterWorkerInput(worker, worker, 1, {}))
    container.execution.accept_run(run.run_id, "old", "lease-old", 10)
    container.execution.start_run(run.run_id, "old", "lease-old")
    container.execution.accept_run(run.run_id, "new", "lease-new", 11)
    container.execution.start_run(run.run_id, "new", "lease-new")
    with pytest.raises(InvariantViolationError):
        container.execution.finish_run(
            run.run_id, {"status": "finished", "metrics": {}}, "lease-old"
        )
    container.execution.finish_run(run.run_id, {"status": "finished", "metrics": {}}, "lease-new")
    assert container.execution.get_run(run.run_id).status is RunStatus.FINISHED


def test_replay_delivery_recovers_without_another_worker_callback(container):
    run = queued_run(container)
    recorder = container.spectator_replay

    class FlakyRecorder:
        failed = False

        def record_run(self, value):
            if not self.failed:
                self.failed = True
                raise RuntimeError("replay storage temporarily unavailable")
            recorder.record_run(value)

    container.execution._run_replay_recorder = FlakyRecorder()
    with pytest.raises(RuntimeError):
        container.execution.finish_run(run.run_id, {"status": "finished", "metrics": {}})
    assert container.execution.get_run(run.run_id).completion_pending
    with pytest.raises(NotFoundError):
        recorder.get_by_run_id(run.run_id)
    container.execution.dispatch_pending_runs()
    assert recorder.get_by_run_id(run.run_id).run_id == run.run_id
    assert not container.execution.get_run(run.run_id).completion_pending


@pytest.fixture()
def sql_runs(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'runs.sqlite'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield SqlAlchemyRunRepository(sessionmaker(bind=engine))
    engine.dispose()


def test_stop_cannot_be_overwritten_by_concurrent_finish(container, sql_runs, monkeypatch):
    container.execution._run_repository = sql_runs
    run = Run.create("team", "game", "user", RunKind.SINGLE_TASK)
    run.status, run.active_lease_id = RunStatus.RUNNING, "lease"
    sql_runs.save(run)
    read, resume = Event(), Event()
    original = sql_runs.get

    def interleave(run_id, **kwargs):
        value = original(run_id, **kwargs)
        if current_thread().name.startswith("finishing"):
            read.set()
            assert resume.wait(5)
        return value

    monkeypatch.setattr(sql_runs, "get", interleave)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="finishing") as pool:
        result = pool.submit(
            container.execution.finish_run,
            run.run_id,
            {"status": "finished", "metrics": {}},
            "lease",
        )
        assert read.wait(5)
        container.execution.cancel_run(run.run_id)
        resume.set()
        with pytest.raises(ConflictError):
            result.result(timeout=5)
    assert original(run.run_id).status is RunStatus.CANCELED


def test_database_arbitrates_parallel_active_attempts(sql_runs):
    runs = [Run.create("team", "game", "same-user", RunKind.SINGLE_TASK) for _ in range(2)]
    for run in runs:
        sql_runs.save(run)
        run.status = RunStatus.QUEUED

    def save(run):
        try:
            sql_runs.save(run)
            return True
        except ConflictError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, runs))
    assert sorted(results) == [False, True]
    assert (
        len(
            [
                run
                for run in sql_runs.list_active_by_requested_by_and_kind(
                    "same-user", RunKind.SINGLE_TASK
                )
                if run.status is RunStatus.QUEUED
            ]
        )
        == 1
    )


def test_package_is_frozen_before_mutable_game_sources_change(container, tmp_path):
    import shutil
    import tarfile
    from io import BytesIO
    from pathlib import Path
    from execution.infrastructure.game_packages import GamePackageStore

    source = Path(__file__).resolve().parents[2] / "games" / "snake"
    games = tmp_path / "games"
    shutil.copytree(source, games / "snake")
    store = GamePackageStore(container.game_catalog, games, tmp_path / "packages")
    container.execution.game_package_store = store
    run = queued_run(container)
    digest = run.execution_options["package_digest"]
    original = (games / "snake" / "engine.py").read_bytes()
    (games / "snake" / "engine.py").write_text("raise RuntimeError('new source')")
    with tarfile.open(fileobj=BytesIO(store.path(digest).read_bytes()), mode="r:gz") as archive:
        assert archive.extractfile("engine.py").read() == original
