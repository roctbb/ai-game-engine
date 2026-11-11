from shared.kernel import utc_now
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from execution.domain.model import RunKind, RunStatus
from competition.domain.model import Competition, CompetitionCodePolicy, CompetitionFormat, CompetitionPresentationMode, TieBreakPolicy
from competition.infrastructure.sqlalchemy_repository import SqlAlchemyCompetitionRepository
from game_catalog.domain.model import Game, GameMode, SlotDefinition
from game_catalog.infrastructure.sqlalchemy_repository import SqlAlchemyGameRepository
from shared.db.base import Base
from spectator_replay.domain.model import ReplayRecord, ReplayVisibility
from spectator_replay.infrastructure.sqlalchemy_repository import SqlAlchemyReplayRepository
from team_workspace.domain.model import Team
from team_workspace.infrastructure.sqlalchemy_repository import (
    SqlAlchemyTeamRepository,
    SqlAlchemyTeamSnapshotRepository,
)
from training_lobby.domain.model import Lobby, LobbyAccess, LobbyKind
from training_lobby.infrastructure.sqlalchemy_repository import SqlAlchemyLobbyRepository


def _build_session_factory() -> sessionmaker:
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_sqlalchemy_game_repository_roundtrip() -> None:
    session_factory = _build_session_factory()
    repository = SqlAlchemyGameRepository(session_factory)

    game = Game.create(slug='maze_test', title='Maze', mode=GameMode.SINGLE_TASK)
    version = game.add_version(
        semver='1.0.0',
        required_slots=(SlotDefinition(key='agent', title='Agent', required=True),),
    )
    game.activate_version(version.version_id)

    repository.save(game)

    loaded = repository.get(game.game_id)
    assert loaded is not None
    assert loaded.slug == 'maze_test'
    assert loaded.active_version.semver == '1.0.0'
    assert loaded.active_version.required_slot_keys == ('agent',)


def test_competition_broadcast_timeline_survives_repository_reload() -> None:
    repository = SqlAlchemyCompetitionRepository(_build_session_factory())
    competition = Competition.create(
        game_id='game-1', game_version_id='v1', title='Показ', format=CompetitionFormat.SINGLE_ELIMINATION,
        tie_break_policy=TieBreakPolicy.MANUAL, code_policy=CompetitionCodePolicy.LOCKED_ON_START,
        advancement_top_k=1, min_match_size=2, match_size=2,
        presentation_mode=CompetitionPresentationMode.SEQUENTIAL,
    )
    match = competition.seed_first_round(['team-a', 'team-b']).matches[0]
    match.show_started_at = utc_now()
    match.show_reveal_at = match.show_started_at + timedelta(seconds=10)
    match.show_ends_at = match.show_reveal_at + timedelta(seconds=2)
    repository.save(competition)
    loaded = repository.get(competition.competition_id)
    assert loaded.presentation_mode is CompetitionPresentationMode.SEQUENTIAL
    stored = loaded.rounds[0].matches[0]
    assert (stored.show_started_at, stored.show_reveal_at, stored.show_ends_at) == (
        match.show_started_at, match.show_reveal_at, match.show_ends_at,
    )


def test_sqlalchemy_replay_repository_preserves_identity_when_writers_overlap() -> None:
    repository = SqlAlchemyReplayRepository(_build_session_factory())
    first = ReplayRecord.create('run-1', 'game-1', RunKind.TRAINING_MATCH, RunStatus.FINISHED,
                                ReplayVisibility.PRIVATE, [{'tick': 0}], [], {})
    other = ReplayRecord.create('run-1', 'game-1', RunKind.TRAINING_MATCH, RunStatus.FINISHED,
                                ReplayVisibility.PUBLIC, [{'tick': 1}], [], {})
    repository.save(first)
    original = repository.get_by_run_id('run-1')
    repository.save(other)
    repository.save(first)  # a stale retry must not replace the newer frames
    replay = repository.get_by_run_id('run-1')
    assert replay.replay_id == first.replay_id
    assert replay.created_at == original.created_at
    assert replay.frames == [{'tick': 1}]
    assert replay.visibility is ReplayVisibility.PRIVATE


def test_sqlalchemy_team_and_snapshot_repository_roundtrip() -> None:
    session_factory = _build_session_factory()
    team_repository = SqlAlchemyTeamRepository(session_factory)
    snapshot_repository = SqlAlchemyTeamSnapshotRepository(session_factory)

    team = Team.create(game_id='game-1', name='Alpha', captain_user_id='captain-1')
    team.update_slot_code(actor_user_id='captain-1', slot_key='bot', code='print(1)')
    team_repository.save(team)

    loaded_team = team_repository.get(team.team_id)
    assert loaded_team is not None
    assert loaded_team.slots['bot'].revision == 1

    snapshot = loaded_team.create_snapshot(version_id='v1', required_slot_keys=('bot',))
    snapshot_repository.save(snapshot)

    loaded_snapshot = snapshot_repository.latest_for_team(team.team_id)
    assert loaded_snapshot is not None
    assert loaded_snapshot.snapshot_id == snapshot.snapshot_id
    assert loaded_snapshot.revisions_by_slot['bot'] == 1


def test_sqlalchemy_lobby_repository_roundtrip() -> None:
    session_factory = _build_session_factory()
    repository = SqlAlchemyLobbyRepository(session_factory)

    lobby = Lobby.create(
        game_id='game-1',
        game_version_id='v1',
        title='Lobby A',
        kind=LobbyKind.TRAINING,
        access=LobbyAccess.PUBLIC,
        access_code=None,
        max_teams=8,
    )
    lobby.join_team('team-1')
    lobby.mark_ready(team_id='team-1', ready=True)
    lobby.teams['team-1'].last_seen_at = utc_now()

    repository.save(lobby)

    loaded = repository.get(lobby.lobby_id)
    assert loaded is not None
    assert loaded.teams['team-1'].ready is True
    assert loaded.teams['team-1'].last_seen_at == lobby.teams['team-1'].last_seen_at
    assert loaded.teams['team-1'].queued_at == lobby.teams['team-1'].queued_at

    listed = repository.list()
    assert len(listed) == 1
    assert listed[0].lobby_id == lobby.lobby_id
