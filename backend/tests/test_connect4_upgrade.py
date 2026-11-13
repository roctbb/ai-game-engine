from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from competition.infrastructure.sqlalchemy_models import CompetitionOrm
from execution.infrastructure.sqlalchemy_models import MatchExecutionOrm, RunOrm
from game_catalog.infrastructure.sqlalchemy_models import CatalogGameOrm, CatalogGameVersionOrm
from shared.db.base import Base
from spectator_replay.infrastructure.sqlalchemy_models import ReplayOrm
from team_workspace.infrastructure.sqlalchemy_models import (
    WorkspaceTeamOrm,
    WorkspaceTeamSnapshotOrm,
)
from training_lobby.infrastructure.sqlalchemy_models import LobbyOrm


@pytest.fixture
def saved_game(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/upgrade_tic_tac_toe_connect4.py"
    spec = importlib.util.spec_from_file_location("connect4_upgrade", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    legacy = "def make_choice(field, role):\n    return 2, 2\n"
    monkeypatch.setattr(
        migration, "LEGACY_DEMO_SHA256", hashlib.sha256(legacy.encode()).hexdigest()
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        for game_id, slug in [("ttt", "ttt_connect5_v1"), ("other", "other")]:
            session.add(
                CatalogGameOrm(
                    game_id=game_id,
                    slug=slug,
                    title=slug,
                    mode="multiplayer",
                    active_version_id="v2" if game_id == "ttt" else "other-v",
                )
            )
        session.add_all(
            [
                CatalogGameVersionOrm(
                    version_id=version, game_id=game, semver=semver, created_at=now
                )
                for version, game, semver in [
                    ("v1", "ttt", "1.0.0"),
                    ("v2", "ttt", "2.0.0"),
                    ("other-v", "other", "1.0.0"),
                ]
            ]
        )
        for team_id, owner, code in [
            ("student", "student", legacy),
            ("demo", "bot:lobby:1", legacy),
            ("edited", "bot:lobby:2", legacy + "# teacher edit\n"),
        ]:
            session.add(
                WorkspaceTeamOrm(
                    team_id=team_id,
                    game_id="ttt",
                    name=team_id,
                    captain_user_id=owner,
                    slots_json={
                        "bot": {
                            "code": code,
                            "revision": 3,
                            "updated_at": now.isoformat(),
                        }
                    },
                )
            )
        session.add(
            WorkspaceTeamSnapshotOrm(
                snapshot_id="snapshot",
                team_id="student",
                game_id="ttt",
                version_id="v1",
                codes_by_slot_json={"bot": legacy},
                revisions_by_slot_json={"bot": 3},
                created_at=now,
            )
        )
        for lobby_id, game in [("lobby", "ttt"), ("other-lobby", "other")]:
            session.add(
                LobbyOrm(
                    lobby_id=lobby_id,
                    game_id=game,
                    game_version_id="v1",
                    title=lobby_id,
                    kind="training",
                    access="public",
                    max_teams=10,
                    status="open",
                    teams_json={"student": {"ready": True}},
                    last_scheduled_run_ids_json=[game + "-run"],
                    last_scheduled_match_groups_json=[[game + "-run"]],
                    cumulative_stats_by_team_json={"student": {"wins": 4, "matches_total": 6}},
                    created_at=now,
                )
            )
            session.add(
                RunOrm(
                    run_id=game + "-run",
                    team_id="student",
                    game_id=game,
                    requested_by="student",
                    run_kind="training_match",
                    lobby_id=lobby_id,
                    status="finished",
                    target_version_id="v1",
                    created_at=now,
                )
            )
            session.add(
                ReplayOrm(
                    replay_id=game + "-replay",
                    run_id=game + "-run",
                    game_id=game,
                    run_kind="training_match",
                    status="finished",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                MatchExecutionOrm(
                    match_execution_id=game + "-match",
                    primary_run_id=game + "-run",
                    run_ids=[game + "-run"],
                    game_id=game,
                    run_kind="training_match",
                    lobby_id=lobby_id,
                    status="finished",
                    created_at=now,
                )
            )
    yield engine, migration
    engine.dispose()


def test_upgrade_plan_does_not_mutate_data(saved_game):
    engine, migration = saved_game
    report = migration.upgrade_matches(engine, demo_code="new demo")
    assert report["runs"] == report["replays"] == report["match_executions"] == 1
    assert report["demo_bots_updated"] == 1 and report["applied"] is False
    with Session(engine) as session:
        assert session.get(RunOrm, "ttt-run") is not None
        assert session.get(LobbyOrm, "lobby").game_version_id == "v1"


def test_upgrade_preserves_members_player_codes_snapshots_and_other_games(saved_game):
    engine, migration = saved_game
    with Session(engine) as session:
        members = deepcopy(session.get(LobbyOrm, "lobby").teams_json)
        student = deepcopy(session.get(WorkspaceTeamOrm, "student").slots_json)
        edited = deepcopy(session.get(WorkspaceTeamOrm, "edited").slots_json)
    report = migration.upgrade_matches(engine, demo_code="new demo", apply=True)
    assert report["applied"] is True
    with Session(engine) as session:
        for model in [RunOrm, ReplayOrm, MatchExecutionOrm]:
            assert (
                session.scalar(
                    select(func.count()).select_from(model).where(model.game_id == "ttt")
                )
                == 0
            )
            assert (
                session.scalar(
                    select(func.count()).select_from(model).where(model.game_id == "other")
                )
                == 1
            )
        lobby = session.get(LobbyOrm, "lobby")
        assert lobby.teams_json == members
        assert lobby.cumulative_stats_by_team_json == {}
        assert lobby.last_scheduled_run_ids_json == lobby.last_scheduled_match_groups_json == []
        assert lobby.game_version_id == "v2"
        assert session.get(LobbyOrm, "other-lobby").cumulative_stats_by_team_json != {}
        assert session.get(WorkspaceTeamOrm, "student").slots_json == student
        assert session.get(WorkspaceTeamOrm, "edited").slots_json == edited
        assert session.get(WorkspaceTeamSnapshotOrm, "snapshot") is not None
        demo = session.get(WorkspaceTeamOrm, "demo").slots_json["bot"]
        assert demo["code"] == "new demo\n" and demo["revision"] == 4


@pytest.mark.parametrize(
    "status,version,expected",
    [
        ("running", "v1", "активных матчей"),
        ("finished", "v2", "повторный сброс запрещён"),
    ],
)
def test_upgrade_refuses_active_or_new_rule_matches(saved_game, status, version, expected):
    engine, migration = saved_game
    with Session(engine) as session, session.begin():
        run = session.get(RunOrm, "ttt-run")
        run.status, run.target_version_id = status, version
    with pytest.raises(RuntimeError, match=expected):
        migration.upgrade_matches(engine, demo_code="new demo", apply=True)
    with Session(engine) as session:
        assert session.get(RunOrm, "ttt-run") is not None
        assert session.get(LobbyOrm, "lobby").cumulative_stats_by_team_json != {}


def test_upgrade_refuses_unfinished_competition(saved_game):
    engine, migration = saved_game
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        session.add(
            CompetitionOrm(
                competition_id="competition",
                game_id="ttt",
                game_version_id="v1",
                title="Series",
                format="single_elimination",
                tie_break_policy="manual",
                advancement_top_k=1,
                match_size=2,
                status="running",
                created_at=now,
                updated_at=now,
            )
        )
    with pytest.raises(RuntimeError, match="завершите соревнования"):
        migration.upgrade_matches(engine, demo_code="new demo", apply=True)
