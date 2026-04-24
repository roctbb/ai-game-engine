from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from game_catalog.domain.model import Game, GameMode, SlotDefinition
from game_catalog.infrastructure.sqlalchemy_repository import SqlAlchemyGameRepository
from shared.db.base import Base
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

    repository.save(lobby)

    loaded = repository.get(lobby.lobby_id)
    assert loaded is not None
    assert loaded.teams['team-1'].ready is True

    listed = repository.list()
    assert len(listed) == 1
    assert listed[0].lobby_id == lobby.lobby_id
