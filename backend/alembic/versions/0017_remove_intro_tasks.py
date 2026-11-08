"""Remove retired one-shot exercises and their associated data."""

from alembic import op
import sqlalchemy as sa

revision = "0017_remove_intro_tasks"
down_revision = "0016_lease_generation_bigint"
branch_labels = None
depends_on = None

REMOVED_SLUGS = (
    "battery_robot_lite_v1",
    "boss_pattern_v1",
    "command_tape_v1",
    "crystal_corridor_v1",
    "farm_grid_v1",
    "farm_row_v1",
    "gate_guard_v1",
    "gravity_apples_v1",
    "hero_inventory_v1",
    "laser_mirrors_v1",
    "miner_backpack_v1",
    "minesweeper_numbers_v1",
    "patrol_guard_v1",
    "pixel_painter_v1",
    "potion_maker_v1",
    "priority_tower_v1",
    "rune_decoder_v1",
    "space_queue_v1",
    "treasure_scanner_v1",
    "wall_archer_v1",
    "weakest_enemy_v1",
)


def upgrade() -> None:
    connection = op.get_bind()
    games = sa.table("catalog_games", sa.column("game_id"), sa.column("slug"), sa.column("mode"))
    game_ids = list(
        connection.scalars(
            sa.select(games.c.game_id).where(
                games.c.slug.in_(REMOVED_SLUGS), games.c.mode == "single_task"
            )
        )
    )
    if not game_ids:
        return
    runs = sa.table("execution_runs", sa.column("game_id"), sa.column("status"))
    if connection.scalar(
        sa.select(sa.func.count())
        .select_from(runs)
        .where(runs.c.game_id.in_(game_ids), runs.c.status.in_(("queued", "running")))
    ):
        raise RuntimeError("Stop active runs of retired introductory tasks before migrating")
    # Delete dependants first, including databases where FK cascades are disabled.
    for name in (
        "spectator_replays",
        "execution_match_executions",
        "execution_runs",
        "competitions",
        "training_lobbies",
        "workspace_team_snapshots",
        "workspace_teams",
        "catalog_game_versions",
        "catalog_games",
    ):
        table = sa.table(name, sa.column("game_id"))
        connection.execute(sa.delete(table).where(table.c.game_id.in_(game_ids)))


def downgrade() -> None:
    # No schema changes. Deleted content and attempts can only be restored from backup.
    pass
