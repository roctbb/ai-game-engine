from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from administration.application.service import AdministrationService
from administration.infrastructure.http_builder_gateway import HttpBuilderGateway
from administration.infrastructure.in_memory_repository import (
    InMemoryGameSourceRepository,
    InMemoryGameSourceSyncRepository,
)
from administration.infrastructure.noop_builder_gateway import NoopBuilderGateway
from administration.infrastructure.sqlalchemy_repository import (
    SqlAlchemyGameSourceRepository,
    SqlAlchemyGameSourceSyncRepository,
)
from antiplagiarism.application.service import AntiplagiarismService
from competition.application.service import CompetitionService
from competition.infrastructure.in_memory_repository import InMemoryCompetitionRepository
from competition.infrastructure.sqlalchemy_repository import SqlAlchemyCompetitionRepository
from execution.application.service import (
    CreateRunInput,
    ExecutionService,
    RegisterWorkerInput,
    UpdateWorkerStatusInput,
)
from execution.application.scheduler_gateway import NoopSchedulerGateway, SchedulerGateway
from execution.domain.model import RunKind, WorkerStatus
from execution.infrastructure.http_scheduler_gateway import HttpSchedulerGateway
from execution.infrastructure.in_memory_repository import (
    InMemoryBuildRepository,
    InMemoryRunRepository,
    InMemoryWorkerRepository,
)
from execution.infrastructure.sqlalchemy_repository import (
    SqlAlchemyBuildRepository,
    SqlAlchemyRunRepository,
    SqlAlchemyWorkerRepository,
)
from game_catalog.application.service import GameCatalogService
from game_catalog.domain.model import CatalogMetadataStatus, SlotDefinition
from game_catalog.infrastructure.in_memory_repository import InMemoryGameRepository
from game_catalog.infrastructure.manifest_loader import GameManifest, load_game_manifests
from game_catalog.infrastructure.sqlalchemy_repository import SqlAlchemyGameRepository
from identity.application.service import IdentityService
from identity.infrastructure.in_memory_repository import InMemorySessionRepository
from identity.infrastructure.sqlalchemy_repository import SqlAlchemySessionRepository
from spectator_replay.application.service import SpectatorReplayService
from spectator_replay.infrastructure.in_memory_repository import InMemoryReplayRepository
from spectator_replay.infrastructure.sqlalchemy_repository import SqlAlchemyReplayRepository
from shared.kernel import ConflictError
from team_workspace.application.service import TeamWorkspaceService
from team_workspace.infrastructure.in_memory_repository import (
    InMemoryTeamRepository,
    InMemoryTeamSnapshotRepository,
)
from team_workspace.infrastructure.sqlalchemy_repository import (
    SqlAlchemyTeamRepository,
    SqlAlchemyTeamSnapshotRepository,
)
from training_lobby.application.service import TrainingLobbyService
from training_lobby.infrastructure.in_memory_repository import InMemoryLobbyRepository
from training_lobby.infrastructure.sqlalchemy_repository import SqlAlchemyLobbyRepository
from shared.config.settings import settings
from shared.db.base import Base
from shared.db.session import create_sqlalchemy_engine
import shared.db.models as _db_models
from sqlalchemy.orm import sessionmaker


REMOVED_MANIFEST_GAME_SLUGS = {
    "archer_duel_lite_v1",
    "beacon_duel_v1",
    "blinking_gem_duel_v1",
    "hill_control_v1",
    "jump_gem_duel_v1",
    "relic_delivery_duel_v1",
    "template_v1",
}


@dataclass(slots=True)
class ServiceContainer:
    administration: AdministrationService
    game_catalog: GameCatalogService
    team_workspace: TeamWorkspaceService
    training_lobby: TrainingLobbyService
    competition: CompetitionService
    antiplagiarism: AntiplagiarismService
    spectator_replay: SpectatorReplayService
    execution: ExecutionService
    identity: IdentityService

    @staticmethod
    def execution_create_run_input(
        team_id: str,
        game_id: str,
        requested_by: str,
        run_kind: RunKind,
        lobby_id: str | None,
        version_id: str | None = None,
    ) -> CreateRunInput:
        return CreateRunInput(
            team_id=team_id,
            game_id=game_id,
            requested_by=requested_by,
            run_kind=run_kind,
            lobby_id=lobby_id,
            version_id=version_id,
        )

    @staticmethod
    def execution_register_worker_input(
        worker_id: str,
        hostname: str,
        capacity_total: int,
        labels: dict[str, str],
    ) -> RegisterWorkerInput:
        return RegisterWorkerInput(
            worker_id=worker_id,
            hostname=hostname,
            capacity_total=capacity_total,
            labels=labels,
        )

    @staticmethod
    def execution_update_worker_status_input(
        worker_id: str,
        status: WorkerStatus,
    ) -> UpdateWorkerStatusInput:
        return UpdateWorkerStatusInput(
            worker_id=worker_id,
            status=status,
        )


def _build_container() -> ServiceContainer:
    use_core_sqlalchemy = settings.core_repository_backend == "sqlalchemy"
    use_execution_sqlalchemy = settings.execution_repository_backend == "sqlalchemy"
    use_session_sqlalchemy = settings.session_repository_backend == "sqlalchemy"
    use_any_sqlalchemy = use_core_sqlalchemy or use_execution_sqlalchemy or use_session_sqlalchemy

    sql_session_factory = None
    if use_any_sqlalchemy:
        _ = _db_models
        sql_engine = create_sqlalchemy_engine()
        if (
            use_core_sqlalchemy
            and settings.core_repository_auto_create_tables
            or use_execution_sqlalchemy
            and settings.execution_repository_auto_create_tables
            or use_session_sqlalchemy
            and settings.session_repository_auto_create_tables
        ):
            Base.metadata.create_all(bind=sql_engine)
        sql_session_factory = sessionmaker(bind=sql_engine, autocommit=False, autoflush=False)

    if use_core_sqlalchemy:
        assert sql_session_factory is not None
        game_source_repo = SqlAlchemyGameSourceRepository(sql_session_factory)
        game_source_sync_repo = SqlAlchemyGameSourceSyncRepository(sql_session_factory)
        game_repo = SqlAlchemyGameRepository(sql_session_factory)
        team_repo = SqlAlchemyTeamRepository(sql_session_factory)
        team_snapshot_repo = SqlAlchemyTeamSnapshotRepository(sql_session_factory)
        lobby_repo = SqlAlchemyLobbyRepository(sql_session_factory)
        competition_repo = SqlAlchemyCompetitionRepository(sql_session_factory)
        replay_repo = SqlAlchemyReplayRepository(sql_session_factory)
    else:
        game_source_repo = InMemoryGameSourceRepository()
        game_source_sync_repo = InMemoryGameSourceSyncRepository()
        game_repo = InMemoryGameRepository()
        team_repo = InMemoryTeamRepository()
        team_snapshot_repo = InMemoryTeamSnapshotRepository()
        lobby_repo = InMemoryLobbyRepository()
        competition_repo = InMemoryCompetitionRepository()
        replay_repo = InMemoryReplayRepository()

    if use_execution_sqlalchemy:
        assert sql_session_factory is not None
        run_repo = SqlAlchemyRunRepository(sql_session_factory)
        worker_repo = SqlAlchemyWorkerRepository(sql_session_factory)
        build_repo = SqlAlchemyBuildRepository(sql_session_factory)
    else:
        run_repo = InMemoryRunRepository()
        worker_repo = InMemoryWorkerRepository()
        build_repo = InMemoryBuildRepository()

    if use_session_sqlalchemy:
        assert sql_session_factory is not None
        session_repo = SqlAlchemySessionRepository(sql_session_factory)
    else:
        session_repo = InMemorySessionRepository()
    scheduler_gateway: SchedulerGateway
    if settings.scheduler_service_url:
        scheduler_gateway = HttpSchedulerGateway(settings.scheduler_service_url)
    else:
        scheduler_gateway = NoopSchedulerGateway()
    if settings.builder_service_url:
        builder_gateway = HttpBuilderGateway(settings.builder_service_url)
    else:
        builder_gateway = NoopBuilderGateway()

    administration = AdministrationService(
        source_repository=game_source_repo,
        source_sync_repository=game_source_sync_repo,
        builder_gateway=builder_gateway,
    )
    game_catalog = GameCatalogService(repository=game_repo)
    spectator_replay = SpectatorReplayService(repository=replay_repo)
    team_workspace = TeamWorkspaceService(
        team_repository=team_repo,
        snapshot_repository=team_snapshot_repo,
        game_catalog=game_catalog,
    )
    execution = ExecutionService(
        run_repository=run_repo,
        worker_repository=worker_repo,
        build_repository=build_repo,
        scheduler_gateway=scheduler_gateway,
        workspace_service=team_workspace,
        game_catalog=game_catalog,
        run_replay_recorder=spectator_replay,
    )
    training_lobby = TrainingLobbyService(
        repository=lobby_repo,
        game_catalog=game_catalog,
        team_workspace=team_workspace,
        execution=execution,
    )
    competition = CompetitionService(
        repository=competition_repo,
        game_catalog=game_catalog,
        team_workspace=team_workspace,
        execution=execution,
    )
    antiplagiarism = AntiplagiarismService(
        competition=competition,
        execution=execution,
        team_workspace=team_workspace,
    )
    identity = IdentityService(sessions=session_repo)

    _seed_manifest_games(game_catalog)

    return ServiceContainer(
        administration=administration,
        game_catalog=game_catalog,
        team_workspace=team_workspace,
        training_lobby=training_lobby,
        competition=competition,
        antiplagiarism=antiplagiarism,
        spectator_replay=spectator_replay,
        execution=execution,
        identity=identity,
    )


def _seed_manifest_games(game_catalog: GameCatalogService) -> None:
    games_root = get_games_root()
    for manifest in load_game_manifests(games_root):
        try:
            game_catalog.register_game(manifest.to_register_input())
        except ConflictError:
            _update_existing_game(game_catalog, manifest)
    _archive_removed_manifest_games(game_catalog)


def _archive_removed_manifest_games(game_catalog: GameCatalogService) -> None:
    for slug in REMOVED_MANIFEST_GAME_SLUGS:
        game = game_catalog.get_game_by_slug(slug)
        if game is None or game.catalog_metadata_status is CatalogMetadataStatus.ARCHIVED:
            continue
        game_catalog.update_game(game.game_id, catalog_metadata_status=CatalogMetadataStatus.ARCHIVED)


def _update_existing_game(game_catalog: GameCatalogService, manifest: GameManifest) -> None:
    game = game_catalog.get_game_by_slug(manifest.id)
    if game is None:
        return
    reg = manifest.to_register_input()
    game_catalog.sync_metadata_from_manifest(game.game_id, reg)

    active = game.versions.get(game.active_version_id or "")
    if active and active.semver == manifest.semver:
        return
    try:
        version = game_catalog.add_game_version(
            game_id=game.game_id,
            semver=manifest.semver,
            required_slots=reg.required_slots,
            required_worker_labels=dict(reg.required_worker_labels),
        )
        game_catalog.activate_game_version(game.game_id, version.version_id)
    except ConflictError:
        pass


def get_games_root() -> Path:
    if settings.games_root:
        return Path(settings.games_root).resolve()
    return Path(__file__).resolve().parents[3] / "games"


_CONTAINER = _build_container()


def get_container() -> ServiceContainer:
    return _CONTAINER
