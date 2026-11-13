"""One-time transition to connect-four. Stop API/matchmaking before --apply.

Run against the new release after catalog seeding and a database backup.
The default is a read-only plan; --apply commits one transaction. Never run
automatically at startup: that would erase results after every deployment.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from competition.infrastructure.sqlalchemy_models import CompetitionOrm
from execution.infrastructure.sqlalchemy_models import MatchExecutionOrm, RunOrm
from game_catalog.infrastructure.sqlalchemy_models import (
    CatalogGameOrm,
    CatalogGameVersionOrm,
)
from spectator_replay.infrastructure.sqlalchemy_models import ReplayOrm
from team_workspace.infrastructure.sqlalchemy_models import WorkspaceTeamOrm
from training_lobby.infrastructure.sqlalchemy_models import LobbyOrm


LEGACY_DEMO_SHA256 = "d2e0a4467a48cd1e6a27b3466ad67f1cbe98119d52339dd62a6f78451c31c6a2"


def upgrade_matches(
    engine: Engine, *, demo_code: str, apply: bool = False
) -> dict[str, object]:
    with Session(engine) as session, session.begin():
        game = session.scalar(
            select(CatalogGameOrm)
            .where(
                CatalogGameOrm.slug == "ttt_connect5_v1",
            )
            .with_for_update()
        )
        if game is None:
            raise RuntimeError("Игра не найдена")
        version = session.get(CatalogGameVersionOrm, game.active_version_id)
        if version is None or version.semver != "2.0.0":
            raise RuntimeError("Сначала загрузите каталог версии 2.0.0")

        runs = session.execute(
            select(
                RunOrm.status,
                RunOrm.target_version_id,
                RunOrm.snapshot_version_id,
            ).where(RunOrm.game_id == game.game_id)
        ).all()
        if any(run.status in {"created", "queued", "running"} for run in runs):
            raise RuntimeError("Сначала дождитесь завершения активных матчей")
        if any(
            version.version_id in {run.target_version_id, run.snapshot_version_id}
            for run in runs
        ):
            raise RuntimeError(
                "Уже есть матчи по новым правилам: повторный сброс запрещён"
            )
        competitions = session.scalars(
            select(CompetitionOrm).where(
                CompetitionOrm.game_id == game.game_id,
            )
        ).all()
        if any(
            item.status in {"draft", "running", "paused", "completed"}
            for item in competitions
        ):
            raise RuntimeError("Сначала завершите соревнования этой игры")

        lobbies = session.scalars(
            select(LobbyOrm)
            .where(
                LobbyOrm.game_id == game.game_id,
            )
            .with_for_update()
        ).all()
        teams = session.scalars(
            select(WorkspaceTeamOrm)
            .where(
                WorkspaceTeamOrm.game_id == game.game_id,
            )
            .with_for_update()
        ).all()
        demo_bots = [
            team
            for team in teams
            if team.captain_user_id.startswith("bot:")
            and hashlib.sha256(
                str(team.slots_json.get("bot", {}).get("code", "")).rstrip().encode()
                + b"\n"
            ).hexdigest()
            == LEGACY_DEMO_SHA256
        ]
        report = {
            "game_id": game.game_id,
            "lobbies": len(lobbies),
            "players": len(teams),
            "runs": len(runs),
            "competitions": len(competitions),
            "replays": session.scalar(
                select(func.count())
                .select_from(ReplayOrm)
                .where(ReplayOrm.game_id == game.game_id)
            ),
            "match_executions": session.scalar(
                select(func.count())
                .select_from(MatchExecutionOrm)
                .where(MatchExecutionOrm.game_id == game.game_id)
            ),
            "demo_bots_updated": len(demo_bots),
            "applied": apply,
        }
        if not apply:
            return report

        session.execute(delete(ReplayOrm).where(ReplayOrm.game_id == game.game_id))
        session.execute(delete(RunOrm).where(RunOrm.game_id == game.game_id))
        session.execute(
            delete(MatchExecutionOrm).where(MatchExecutionOrm.game_id == game.game_id)
        )
        session.execute(
            delete(CompetitionOrm).where(CompetitionOrm.game_id == game.game_id)
        )
        for lobby in lobbies:
            lobby.game_version_id = version.version_id
            lobby.cumulative_stats_by_team_json = {}
            lobby.last_scheduled_run_ids_json = []
            lobby.last_scheduled_match_groups_json = []
        for team in demo_bots:
            slot = dict(team.slots_json["bot"])
            slot.update(
                code=demo_code.rstrip() + "\n",
                revision=int(slot.get("revision", 0)) + 1,
                updated_at=datetime.now(UTC).isoformat(),
            )
            team.slots_json = {**team.slots_json, "bot": slot}
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    # Seeding happens only when explicitly running this maintenance command.
    from app.dependencies import get_games_root
    from shared.db.session import create_sqlalchemy_engine

    demo = get_games_root() / "tic_tac_toe/examples/connect4_balanced.py"
    print(
        json.dumps(
            upgrade_matches(
                create_sqlalchemy_engine(), demo_code=demo.read_text(), apply=args.apply
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
