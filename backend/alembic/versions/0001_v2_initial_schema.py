"""v2 initial schema for core + execution contexts."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_v2_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_games",
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=True),
        sa.Column("learning_section", sa.String(length=80), nullable=True),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("min_players_per_match", sa.Integer(), nullable=True),
        sa.Column("max_players_per_match", sa.Integer(), nullable=True),
        sa.Column("catalog_metadata_status", sa.String(length=32), nullable=False),
        sa.Column("active_version_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("game_id"),
    )
    op.create_index("ix_catalog_games_slug", "catalog_games", ["slug"], unique=True)
    op.create_index("ix_catalog_games_mode", "catalog_games", ["mode"], unique=False)
    op.create_index("ix_catalog_games_difficulty", "catalog_games", ["difficulty"], unique=False)
    op.create_index("ix_catalog_games_learning_section", "catalog_games", ["learning_section"], unique=False)
    op.create_index(
        "ix_catalog_games_catalog_metadata_status",
        "catalog_games",
        ["catalog_metadata_status"],
        unique=False,
    )

    op.create_table(
        "catalog_game_versions",
        sa.Column("version_id", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("semver", sa.String(length=64), nullable=False),
        sa.Column("required_slots_json", sa.JSON(), nullable=False),
        sa.Column("required_worker_labels_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["catalog_games.game_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index("ix_catalog_game_versions_game_id", "catalog_game_versions", ["game_id"], unique=False)
    op.create_index("ix_catalog_game_versions_semver", "catalog_game_versions", ["semver"], unique=False)
    op.create_index(
        "ix_catalog_game_versions_created_at", "catalog_game_versions", ["created_at"], unique=False
    )

    op.create_table(
        "administration_game_sources",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_sync_status", sa.String(length=32), nullable=False),
        sa.Column("last_synced_commit_sha", sa.String(length=120), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index(
        "ix_administration_game_sources_source_type",
        "administration_game_sources",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_sources_status",
        "administration_game_sources",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_sources_last_sync_status",
        "administration_game_sources",
        ["last_sync_status"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_sources_created_by",
        "administration_game_sources",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_sources_created_at",
        "administration_game_sources",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_sources_updated_at",
        "administration_game_sources",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "administration_game_source_syncs",
        sa.Column("sync_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("build_id", sa.String(length=64), nullable=True),
        sa.Column("image_digest", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("commit_sha", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["administration_game_sources.source_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("sync_id"),
    )
    op.create_index(
        "ix_administration_game_source_syncs_source_id",
        "administration_game_source_syncs",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_source_syncs_requested_by",
        "administration_game_source_syncs",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_source_syncs_status",
        "administration_game_source_syncs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_source_syncs_started_at",
        "administration_game_source_syncs",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        "ix_administration_game_source_syncs_finished_at",
        "administration_game_source_syncs",
        ["finished_at"],
        unique=False,
    )

    op.create_table(
        "workspace_teams",
        sa.Column("team_id", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("captain_user_id", sa.String(length=120), nullable=False),
        sa.Column("slots_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("team_id"),
    )
    op.create_index("ix_workspace_teams_game_id", "workspace_teams", ["game_id"], unique=False)
    op.create_index(
        "ix_workspace_teams_captain_user_id", "workspace_teams", ["captain_user_id"], unique=False
    )

    op.create_table(
        "workspace_team_snapshots",
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("team_id", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("version_id", sa.String(length=64), nullable=False),
        sa.Column("codes_by_slot_json", sa.JSON(), nullable=False),
        sa.Column("revisions_by_slot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["workspace_teams.team_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "ix_workspace_team_snapshots_team_id", "workspace_team_snapshots", ["team_id"], unique=False
    )
    op.create_index(
        "ix_workspace_team_snapshots_game_id", "workspace_team_snapshots", ["game_id"], unique=False
    )
    op.create_index(
        "ix_workspace_team_snapshots_version_id", "workspace_team_snapshots", ["version_id"], unique=False
    )
    op.create_index(
        "ix_workspace_team_snapshots_created_at",
        "workspace_team_snapshots",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "training_lobbies",
        sa.Column("lobby_id", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("game_version_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("access", sa.String(length=32), nullable=False),
        sa.Column("access_code", sa.String(length=120), nullable=True),
        sa.Column("max_teams", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("teams_json", sa.JSON(), nullable=False),
        sa.Column("last_scheduled_run_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("lobby_id"),
    )
    op.create_index("ix_training_lobbies_game_id", "training_lobbies", ["game_id"], unique=False)
    op.create_index(
        "ix_training_lobbies_game_version_id", "training_lobbies", ["game_version_id"], unique=False
    )
    op.create_index("ix_training_lobbies_kind", "training_lobbies", ["kind"], unique=False)
    op.create_index("ix_training_lobbies_access", "training_lobbies", ["access"], unique=False)
    op.create_index("ix_training_lobbies_status", "training_lobbies", ["status"], unique=False)
    op.create_index("ix_training_lobbies_created_at", "training_lobbies", ["created_at"], unique=False)

    op.create_table(
        "competitions",
        sa.Column("competition_id", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("game_version_id", sa.String(length=64), nullable=False),
        sa.Column("lobby_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("tie_break_policy", sa.String(length=32), nullable=False),
        sa.Column("code_policy", sa.String(length=32), nullable=False),
        sa.Column("advancement_top_k", sa.Integer(), nullable=False),
        sa.Column("min_match_size", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("match_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("entrants_json", sa.JSON(), nullable=False),
        sa.Column("rounds_json", sa.JSON(), nullable=False),
        sa.Column("current_round_index", sa.Integer(), nullable=True),
        sa.Column("winner_team_ids_json", sa.JSON(), nullable=False),
        sa.Column("pending_reason", sa.Text(), nullable=True),
        sa.Column("last_scheduled_run_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("competition_id"),
    )
    op.create_index("ix_competitions_game_id", "competitions", ["game_id"], unique=False)
    op.create_index("ix_competitions_game_version_id", "competitions", ["game_version_id"], unique=False)
    op.create_index("ix_competitions_lobby_id", "competitions", ["lobby_id"], unique=False)
    op.create_index("ix_competitions_format", "competitions", ["format"], unique=False)
    op.create_index("ix_competitions_status", "competitions", ["status"], unique=False)
    op.create_index("ix_competitions_created_at", "competitions", ["created_at"], unique=False)
    op.create_index("ix_competitions_updated_at", "competitions", ["updated_at"], unique=False)

    op.create_table(
        "execution_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("team_id", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("run_kind", sa.String(length=32), nullable=False),
        sa.Column("lobby_id", sa.String(length=64), nullable=True),
        sa.Column("target_version_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("snapshot_version_id", sa.String(length=64), nullable=True),
        sa.Column("revisions_by_slot", sa.JSON(), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_execution_runs_team_id", "execution_runs", ["team_id"], unique=False)
    op.create_index("ix_execution_runs_game_id", "execution_runs", ["game_id"], unique=False)
    op.create_index("ix_execution_runs_requested_by", "execution_runs", ["requested_by"], unique=False)
    op.create_index("ix_execution_runs_run_kind", "execution_runs", ["run_kind"], unique=False)
    op.create_index("ix_execution_runs_status", "execution_runs", ["status"], unique=False)
    op.create_index("ix_execution_runs_created_at", "execution_runs", ["created_at"], unique=False)

    op.create_table(
        "execution_workers",
        sa.Column("worker_id", sa.String(length=120), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("capacity_total", sa.Integer(), nullable=False),
        sa.Column("capacity_available", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_index("ix_execution_workers_status", "execution_workers", ["status"], unique=False)
    op.create_index(
        "ix_execution_workers_last_heartbeat_at", "execution_workers", ["last_heartbeat_at"], unique=False
    )

    op.create_table(
        "execution_builds",
        sa.Column("build_id", sa.String(length=64), nullable=False),
        sa.Column("game_source_id", sa.String(length=120), nullable=False),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("image_digest", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("build_id"),
    )
    op.create_index("ix_execution_builds_game_source_id", "execution_builds", ["game_source_id"], unique=False)
    op.create_index("ix_execution_builds_status", "execution_builds", ["status"], unique=False)
    op.create_index("ix_execution_builds_created_at", "execution_builds", ["created_at"], unique=False)
    op.create_index("ix_execution_builds_updated_at", "execution_builds", ["updated_at"], unique=False)

    op.create_table(
        "spectator_replays",
        sa.Column("replay_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("run_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("frames_json", sa.JSON(), nullable=False),
        sa.Column("events_json", sa.JSON(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("replay_id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_spectator_replays_run_id", "spectator_replays", ["run_id"], unique=True)
    op.create_index("ix_spectator_replays_game_id", "spectator_replays", ["game_id"], unique=False)
    op.create_index("ix_spectator_replays_run_kind", "spectator_replays", ["run_kind"], unique=False)
    op.create_index("ix_spectator_replays_status", "spectator_replays", ["status"], unique=False)
    op.create_index("ix_spectator_replays_created_at", "spectator_replays", ["created_at"], unique=False)
    op.create_index("ix_spectator_replays_updated_at", "spectator_replays", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_catalog_games_catalog_metadata_status", table_name="catalog_games")
    op.drop_index("ix_catalog_games_learning_section", table_name="catalog_games")
    op.drop_index("ix_catalog_games_difficulty", table_name="catalog_games")
    op.drop_index("ix_spectator_replays_updated_at", table_name="spectator_replays")
    op.drop_index("ix_spectator_replays_created_at", table_name="spectator_replays")
    op.drop_index("ix_spectator_replays_status", table_name="spectator_replays")
    op.drop_index("ix_spectator_replays_run_kind", table_name="spectator_replays")
    op.drop_index("ix_spectator_replays_game_id", table_name="spectator_replays")
    op.drop_index("ix_spectator_replays_run_id", table_name="spectator_replays")
    op.drop_table("spectator_replays")

    op.drop_index("ix_execution_builds_updated_at", table_name="execution_builds")
    op.drop_index("ix_execution_builds_created_at", table_name="execution_builds")
    op.drop_index("ix_execution_builds_status", table_name="execution_builds")
    op.drop_index("ix_execution_builds_game_source_id", table_name="execution_builds")
    op.drop_table("execution_builds")

    op.drop_index("ix_execution_workers_last_heartbeat_at", table_name="execution_workers")
    op.drop_index("ix_execution_workers_status", table_name="execution_workers")
    op.drop_table("execution_workers")

    op.drop_index("ix_execution_runs_created_at", table_name="execution_runs")
    op.drop_index("ix_execution_runs_status", table_name="execution_runs")
    op.drop_index("ix_execution_runs_run_kind", table_name="execution_runs")
    op.drop_index("ix_execution_runs_requested_by", table_name="execution_runs")
    op.drop_index("ix_execution_runs_game_id", table_name="execution_runs")
    op.drop_index("ix_execution_runs_team_id", table_name="execution_runs")
    op.drop_table("execution_runs")

    op.drop_index("ix_training_lobbies_created_at", table_name="training_lobbies")
    op.drop_index("ix_training_lobbies_status", table_name="training_lobbies")
    op.drop_index("ix_training_lobbies_access", table_name="training_lobbies")
    op.drop_index("ix_training_lobbies_kind", table_name="training_lobbies")
    op.drop_index("ix_training_lobbies_game_version_id", table_name="training_lobbies")
    op.drop_index("ix_training_lobbies_game_id", table_name="training_lobbies")
    op.drop_table("training_lobbies")

    op.drop_index("ix_competitions_updated_at", table_name="competitions")
    op.drop_index("ix_competitions_created_at", table_name="competitions")
    op.drop_index("ix_competitions_status", table_name="competitions")
    op.drop_index("ix_competitions_format", table_name="competitions")
    op.drop_index("ix_competitions_lobby_id", table_name="competitions")
    op.drop_index("ix_competitions_game_version_id", table_name="competitions")
    op.drop_index("ix_competitions_game_id", table_name="competitions")
    op.drop_table("competitions")

    op.drop_index("ix_workspace_team_snapshots_created_at", table_name="workspace_team_snapshots")
    op.drop_index("ix_workspace_team_snapshots_version_id", table_name="workspace_team_snapshots")
    op.drop_index("ix_workspace_team_snapshots_game_id", table_name="workspace_team_snapshots")
    op.drop_index("ix_workspace_team_snapshots_team_id", table_name="workspace_team_snapshots")
    op.drop_table("workspace_team_snapshots")

    op.drop_index("ix_workspace_teams_captain_user_id", table_name="workspace_teams")
    op.drop_index("ix_workspace_teams_game_id", table_name="workspace_teams")
    op.drop_table("workspace_teams")

    op.drop_index("ix_catalog_game_versions_created_at", table_name="catalog_game_versions")
    op.drop_index("ix_catalog_game_versions_semver", table_name="catalog_game_versions")
    op.drop_index("ix_catalog_game_versions_game_id", table_name="catalog_game_versions")
    op.drop_table("catalog_game_versions")

    op.drop_index(
        "ix_administration_game_source_syncs_finished_at",
        table_name="administration_game_source_syncs",
    )
    op.drop_index(
        "ix_administration_game_source_syncs_started_at",
        table_name="administration_game_source_syncs",
    )
    op.drop_index(
        "ix_administration_game_source_syncs_status",
        table_name="administration_game_source_syncs",
    )
    op.drop_index(
        "ix_administration_game_source_syncs_requested_by",
        table_name="administration_game_source_syncs",
    )
    op.drop_index(
        "ix_administration_game_source_syncs_source_id",
        table_name="administration_game_source_syncs",
    )
    op.drop_table("administration_game_source_syncs")

    op.drop_index(
        "ix_administration_game_sources_updated_at",
        table_name="administration_game_sources",
    )
    op.drop_index(
        "ix_administration_game_sources_created_at",
        table_name="administration_game_sources",
    )
    op.drop_index(
        "ix_administration_game_sources_created_by",
        table_name="administration_game_sources",
    )
    op.drop_index(
        "ix_administration_game_sources_last_sync_status",
        table_name="administration_game_sources",
    )
    op.drop_index(
        "ix_administration_game_sources_status",
        table_name="administration_game_sources",
    )
    op.drop_index(
        "ix_administration_game_sources_source_type",
        table_name="administration_game_sources",
    )
    op.drop_table("administration_game_sources")

    op.drop_index("ix_catalog_games_mode", table_name="catalog_games")
    op.drop_index("ix_catalog_games_slug", table_name="catalog_games")
    op.drop_table("catalog_games")
