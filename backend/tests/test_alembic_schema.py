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
        "execution_workers",
        "execution_builds",
        "spectator_replays",
        "identity_sessions",
        "alembic_version",
    }
    assert expected_tables.issubset(table_names)

    catalog_columns = {item["name"] for item in inspector.get_columns("catalog_games")}
    assert {"learning_section", "min_players_per_match", "max_players_per_match"}.issubset(catalog_columns)

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
    assert {"session_id", "external_user_id", "nickname", "role", "provider", "created_at"}.issubset(
        session_columns
    )

    run_indexes = {item["name"] for item in inspector.get_indexes("execution_runs")}
    assert {
        "ix_execution_runs_lobby_id",
        "ix_execution_runs_lobby_kind_created_at",
    }.issubset(run_indexes)

    replay_indexes = {item["name"] for item in inspector.get_indexes("spectator_replays")}
    assert "ix_spectator_replays_game_kind_updated_at" in replay_indexes
