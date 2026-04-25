"""Import SQLAlchemy models here so Alembic can discover metadata later."""

from administration.infrastructure.sqlalchemy_models import GameSourceOrm, GameSourceSyncOrm
from competition.infrastructure.sqlalchemy_models import CompetitionOrm
from execution.infrastructure.sqlalchemy_models import BuildOrm, RunOrm, WorkerOrm
from game_catalog.infrastructure.sqlalchemy_models import CatalogGameOrm, CatalogGameVersionOrm
from identity.infrastructure.sqlalchemy_models import IdentitySessionOrm
from spectator_replay.infrastructure.sqlalchemy_models import ReplayOrm
from shared.db.base import Base
from team_workspace.infrastructure.sqlalchemy_models import WorkspaceTeamOrm, WorkspaceTeamSnapshotOrm
from training_lobby.infrastructure.sqlalchemy_models import LobbyOrm

__all__ = [
    "Base",
    "GameSourceOrm",
    "GameSourceSyncOrm",
    "RunOrm",
    "WorkerOrm",
    "BuildOrm",
    "ReplayOrm",
    "CompetitionOrm",
    "CatalogGameOrm",
    "CatalogGameVersionOrm",
    "IdentitySessionOrm",
    "WorkspaceTeamOrm",
    "WorkspaceTeamSnapshotOrm",
    "LobbyOrm",
]
