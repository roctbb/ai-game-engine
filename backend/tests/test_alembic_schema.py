from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_all_v2_tables_and_columns(tmp_path: Path, monkeypatch) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "alembic_v2.sqlite3"
    db_url = f"sqlite+pysqlite:///{db_path}"

    monkeypatch.setenv("DATABASE_URL_OVERRIDE", db_url)

    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "administration_game_sources",
        "administration_game_source_syncs",
        "catalog_games",
        "catalog_game_versions",
        "workspace_teams",
        "workspace_team_snapshots",
        "training_lobbies",
        "competitions",
        "execution_runs",
        "execution_match_executions",
        "execution_workers",
        "execution_builds",
        "spectator_replays",
        "identity_sessions",
        "alembic_version",
    }
    assert expected_tables.issubset(table_names)

    catalog_columns = {item["name"] for item in inspector.get_columns("catalog_games")}
    assert {
        "learning_section",
        "min_players_per_match",
        "max_players_per_match",
    }.issubset(catalog_columns)

    assert {"catalog_metadata_status", "is_hidden"}.isdisjoint(catalog_columns)

    lobby_columns = {item["name"] for item in inspector.get_columns("training_lobbies")}
    assert "last_scheduled_run_ids_json" in lobby_columns

    competition_columns = {item["name"] for item in inspector.get_columns("competitions")}
    assert {
        "lobby_id",
        "tie_break_policy",
        "code_policy",
        "advancement_top_k",
        "min_match_size",
        "match_size",
        "last_scheduled_run_ids_json",
    }.issubset(competition_columns)

    replay_columns = {item["name"] for item in inspector.get_columns("spectator_replays")}
    assert {"run_id", "frames_json", "events_json", "summary_json"}.issubset(replay_columns)

    session_columns = {item["name"] for item in inspector.get_columns("identity_sessions")}
    assert {
        "session_id",
        "external_user_id",
        "nickname",
        "role",
        "provider",
        "created_at",
    }.issubset(session_columns)

    run_indexes = {item["name"] for item in inspector.get_indexes("execution_runs")}
    run_columns = {item["name"] for item in inspector.get_columns("execution_runs")}
    assert {"revision", "lease_generation", "dispatch_pending", "completion_pending"} <= run_columns
    assert "uq_execution_single_task_active_user" in run_indexes
    assert {
        "ix_execution_runs_lobby_id",
        "ix_execution_runs_lobby_kind_created_at",
        "ix_execution_runs_match_execution_id",
        "ix_execution_runs_match_primary_run_id",
    }.issubset(run_indexes)

    match_columns = {item["name"] for item in inspector.get_columns("execution_match_executions")}
    assert {"match_execution_id", "primary_run_id", "run_ids", "result_payload"}.issubset(
        match_columns
    )

    replay_indexes = {item["name"] for item in inspector.get_indexes("spectator_replays")}
    assert "ix_spectator_replays_game_kind_updated_at" in replay_indexes


def test_reliability_migration_upgrades_existing_attempts_and_can_be_reapplied(
    tmp_path, monkeypatch
):
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import MetaData, Table, select

    backend_root = Path(__file__).resolve().parents[1]
    url = f"sqlite+pysqlite:///{tmp_path / 'upgrade.sqlite'}"
    monkeypatch.setenv("DATABASE_URL_OVERRIDE", url)
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(cfg, "0014_run_execution_options")
    engine = create_engine(url)
    table = Table("execution_runs", MetaData(), autoload_with=engine)
    now = datetime.now(tz=UTC)
    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                dict(
                    run_id=name,
                    team_id="team",
                    game_id="game",
                    requested_by="same-user",
                    run_kind="single_task",
                    status="queued",
                    revisions_by_slot={},
                    execution_options={},
                    created_at=now + timedelta(seconds=index),
                )
                for index, name in enumerate(("oldest", "newer"))
            ],
        )
    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            dict(
                run_id="orphan-running",
                team_id="team",
                game_id="game",
                requested_by="other-user",
                run_kind="single_task",
                status="running",
                revisions_by_slot={},
                execution_options={},
                created_at=now,
            ),
        )
    command.upgrade(cfg, "head")
    upgraded = Table("execution_runs", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        rows = {row.run_id: row for row in connection.execute(select(upgraded))}
    assert rows["oldest"].status == "queued"
    assert rows["oldest"].dispatch_pending
    assert rows["newer"].status == "canceled"
    assert rows["newer"].completion_pending
    assert rows["orphan-running"].status == "queued"
    assert rows["orphan-running"].dispatch_pending
    command.downgrade(cfg, "0014_run_execution_options")
    command.upgrade(cfg, "head")
    engine.dispose()


def test_catalog_visibility_migration_preserves_all_tasks_and_versions(tmp_path, monkeypatch):
    from datetime import UTC, datetime
    from sqlalchemy import MetaData, Table, select

    backend_root = Path(__file__).resolve().parents[1]
    url = f"sqlite+pysqlite:///{tmp_path / 'catalog-visibility.sqlite'}"
    monkeypatch.setenv("DATABASE_URL_OVERRIDE", url)
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(cfg, "0018_competition_presentation")
    engine = create_engine(url)
    games = Table("catalog_games", MetaData(), autoload_with=engine)
    versions = Table("catalog_game_versions", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        for status in ("draft", "ready", "archived"):
            connection.execute(games.insert(), dict(
                game_id=status, slug=f"task-{status}", title=status, mode="single_task",
                topics=[], catalog_metadata_status=status, is_hidden=True,
            ))
            connection.execute(versions.insert(), dict(
                version_id=f"version-{status}", game_id=status, semver="1.0.0",
                required_slots_json=[], required_worker_labels_json={}, created_at=datetime.now(UTC),
            ))
    command.upgrade(cfg, "head")
    upgraded = Table("catalog_games", MetaData(), autoload_with=engine)
    assert {"catalog_metadata_status", "is_hidden"}.isdisjoint(upgraded.c.keys())
    with engine.connect() as connection:
        assert set(connection.scalars(select(upgraded.c.game_id))) == {"draft", "ready", "archived"}
        assert set(connection.scalars(select(versions.c.version_id))) == {
            "version-draft", "version-ready", "version-archived",
        }
    command.downgrade(cfg, "0018_competition_presentation")
    restored = Table("catalog_games", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        rows = connection.execute(select(restored)).all()
        assert len(rows) == 3
        assert all(row.catalog_metadata_status == "ready" and not row.is_hidden for row in rows)
    command.upgrade(cfg, "head")
    engine.dispose()
