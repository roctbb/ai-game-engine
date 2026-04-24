from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_session, require_roles
from app.dependencies import ServiceContainer, get_container, get_games_root
from game_catalog.api.schemas import (
    ActivateVersionRequest,
    AddVersionRequest,
    GameDemoStrategyResponse,
    GameResponse,
    GameSlotTemplateResponse,
    GameTemplatesResponse,
    GameTopicsResponse,
    SingleTaskCatalogItemResponse,
    SingleTaskLeaderboardEntryResponse,
    SingleTaskLeaderboardResponse,
    SingleTaskSolvedSummaryEntryResponse,
    SingleTaskSolvedSummaryResponse,
    GameVersionResponse,
    PatchGameRequest,
    RegisterGameRequest,
    UpdateCatalogMetadataRequest,
)
from game_catalog.application.single_task_progress import SingleTaskProgressService
from game_catalog.application.service import RegisterGameInput
from game_catalog.domain.model import SlotDefinition
from game_catalog.infrastructure.manifest_loader import find_game_manifest_path, load_game_manifest
from identity.domain.model import UserRole
from shared.kernel import ConflictError, InvariantViolationError

router = APIRouter(prefix="/games", tags=["game_catalog"], dependencies=[Depends(get_current_session)])
progress_router = APIRouter(tags=["game_catalog"], dependencies=[Depends(get_current_session)])


def _map_game(game: object) -> GameResponse:
    from game_catalog.domain.model import Game

    typed = game if isinstance(game, Game) else None
    assert typed is not None
    return GameResponse(
        game_id=typed.game_id,
        slug=typed.slug,
        title=typed.title,
        mode=typed.mode,
        description=typed.description,
        difficulty=typed.difficulty,
        topics=list(typed.topics),
        catalog_metadata_status=typed.catalog_metadata_status,
        active_version_id=typed.active_version.version_id,
        versions=[
            GameVersionResponse(
                version_id=version.version_id,
                semver=version.semver,
                required_slot_keys=list(version.required_slot_keys),
                required_worker_labels=dict(version.required_worker_labels),
            )
            for version in typed.versions.values()
        ],
    )


def _progress(container: ServiceContainer) -> SingleTaskProgressService:
    return SingleTaskProgressService(game_catalog=container.game_catalog, execution=container.execution)


@router.get("", response_model=list[GameResponse])
def list_games(container: ServiceContainer = Depends(get_container)) -> list[GameResponse]:
    return [_map_game(item) for item in container.game_catalog.list_games()]


@router.post("", response_model=GameResponse)
def register_game(
    request: RegisterGameRequest,
    _: object = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> GameResponse:
    game = container.game_catalog.register_game(
        RegisterGameInput(
            slug=request.slug,
            title=request.title,
            mode=request.mode,
            semver=request.semver,
            description=request.description,
            difficulty=request.difficulty,
            topics=tuple(request.topics),
            required_worker_labels=dict(request.required_worker_labels),
            catalog_metadata_status=request.catalog_metadata_status,
            required_slots=tuple(
                SlotDefinition(key=slot.key, title=slot.title, required=slot.required)
                for slot in request.required_slots
            ),
        )
    )
    return _map_game(game)


@router.get("/{game_id}", response_model=GameResponse)
def get_game(game_id: str, container: ServiceContainer = Depends(get_container)) -> GameResponse:
    return _map_game(container.game_catalog.get_game(game_id))


@router.patch("/{game_id}", response_model=GameResponse)
def patch_game(
    game_id: str,
    request: PatchGameRequest,
    _: object = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> GameResponse:
    game = container.game_catalog.update_game(
        game_id=game_id,
        title=request.title,
        description=request.description,
        difficulty=request.difficulty,
        topics=tuple(request.topics) if request.topics is not None else None,
        catalog_metadata_status=request.catalog_metadata_status,
    )
    return _map_game(game)


@router.get("/{game_id}/versions", response_model=list[GameVersionResponse])
def list_game_versions(game_id: str, container: ServiceContainer = Depends(get_container)) -> list[GameVersionResponse]:
    game = container.game_catalog.get_game(game_id)
    return [
        GameVersionResponse(
            version_id=version.version_id,
            semver=version.semver,
            required_slot_keys=list(version.required_slot_keys),
            required_worker_labels=dict(version.required_worker_labels),
        )
        for version in game.versions.values()
    ]


@router.get("/{game_id}/versions/{version_id}", response_model=GameVersionResponse)
def get_game_version(
    game_id: str,
    version_id: str,
    container: ServiceContainer = Depends(get_container),
) -> GameVersionResponse:
    version = container.game_catalog.get_version(game_id=game_id, version_id=version_id)
    return GameVersionResponse(
        version_id=version.version_id,
        semver=version.semver,
        required_slot_keys=list(version.required_slot_keys),
        required_worker_labels=dict(version.required_worker_labels),
    )


@router.get("/{game_id}/topics", response_model=GameTopicsResponse)
def get_game_topics(game_id: str, container: ServiceContainer = Depends(get_container)) -> GameTopicsResponse:
    game = container.game_catalog.get_game(game_id)
    return GameTopicsResponse(game_id=game.game_id, topics=list(game.topics))


@router.get("/{game_id}/templates", response_model=GameTemplatesResponse)
def get_game_templates(game_id: str, container: ServiceContainer = Depends(get_container)) -> GameTemplatesResponse:
    game = container.game_catalog.get_game(game_id)
    code_api_mode: str = "script_based" if game.mode.value == "single_task" else "turn_based"
    player_instruction: str | None = None
    try:
        manifest_path = find_game_manifest_path(games_root=get_games_root(), game_id=game.slug)
        manifest = load_game_manifest(manifest_path)
    except InvariantViolationError:
        manifest = None
    if manifest is not None:
        code_api_mode = manifest.code_api_mode
        player_instruction = manifest.player_instruction
        demo_strategies = [
            GameDemoStrategyResponse(
                strategy_id=strategy.id,
                slot_key=strategy.slot_key,
                title=strategy.title,
                language=strategy.language,
                description=strategy.description,
                code=(manifest_path.parent / strategy.path).read_text(encoding="utf-8"),
            )
            for strategy in manifest.demo_strategies
        ]
    else:
        demo_strategies = []

    active_slots = game.active_version.required_slots
    templates = [
        GameSlotTemplateResponse(
            slot_key=slot.key,
            language="python",
            code=_build_slot_template_code(slot_key=slot.key, code_api_mode=code_api_mode),
        )
        for slot in active_slots
    ]
    return GameTemplatesResponse(
        game_id=game.game_id,
        game_slug=game.slug,
        code_api_mode=code_api_mode,
        player_instruction=player_instruction,
        templates=templates,
        demo_strategies=demo_strategies,
    )


@router.post("/{game_id}/versions", response_model=GameResponse)
def add_version(
    game_id: str,
    request: AddVersionRequest,
    _: object = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> GameResponse:
    container.game_catalog.add_game_version(
        game_id=game_id,
        semver=request.semver,
        required_worker_labels=dict(request.required_worker_labels),
        required_slots=tuple(
            SlotDefinition(key=slot.key, title=slot.title, required=slot.required)
            for slot in request.required_slots
        ),
    )
    return _map_game(container.game_catalog.get_game(game_id))


@router.post("/{game_id}/activate", response_model=GameResponse)
def activate_version(
    game_id: str,
    request: ActivateVersionRequest,
    _: object = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> GameResponse:
    if container.competition.has_running_competition_for_game(game_id=game_id):
        raise ConflictError("Нельзя обновлять активную игру во время running-соревнования")
    game = container.game_catalog.activate_game_version(game_id=game_id, version_id=request.version_id)
    return _map_game(game)


@router.patch("/{game_id}/catalog-metadata", response_model=GameResponse)
def update_catalog_metadata(
    game_id: str,
    request: UpdateCatalogMetadataRequest,
    _: object = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> GameResponse:
    game = container.game_catalog.update_catalog_metadata(
        game_id=game_id,
        description=request.description,
        difficulty=request.difficulty,
        topics=tuple(request.topics),
        catalog_metadata_status=request.catalog_metadata_status,
    )
    return _map_game(game)


@progress_router.get("/catalog/single-tasks", response_model=list[SingleTaskCatalogItemResponse])
def list_single_task_catalog(container: ServiceContainer = Depends(get_container)) -> list[SingleTaskCatalogItemResponse]:
    items = _progress(container).build_single_task_catalog_items()
    return [
        SingleTaskCatalogItemResponse(
            game_id=item.game_id,
            slug=item.slug,
            title=item.title,
                description=item.description,
                difficulty=item.difficulty,
                topics=list(item.topics),
                catalog_metadata_status=item.catalog_metadata_status,
                attempts_finished=item.attempts_finished,
                solved_users=item.solved_users,
                has_score_model=item.has_score_model,
        )
        for item in items
    ]


@progress_router.get("/catalog/single-tasks/solved-summary", response_model=SingleTaskSolvedSummaryResponse)
def get_single_task_solved_summary(
    limit: int = 20,
    container: ServiceContainer = Depends(get_container),
) -> SingleTaskSolvedSummaryResponse:
    summary = _progress(container).build_solved_summary(limit=max(1, min(limit, 200)))
    return SingleTaskSolvedSummaryResponse(
        total_single_tasks=summary.total_single_tasks,
        entries=[
            SingleTaskSolvedSummaryEntryResponse(
                place=entry.place,
                user_id=entry.user_id,
                solved_tasks_count=entry.solved_tasks_count,
                solved_game_ids=list(entry.solved_game_ids),
            )
            for entry in summary.entries
        ],
    )


@progress_router.get("/single-tasks/{game_id}/leaderboard", response_model=SingleTaskLeaderboardResponse)
def get_single_task_leaderboard(
    game_id: str,
    limit: int = 20,
    container: ServiceContainer = Depends(get_container),
) -> SingleTaskLeaderboardResponse:
    leaderboard = _progress(container).build_leaderboard(game_id=game_id, limit=max(1, min(limit, 200)))
    return SingleTaskLeaderboardResponse(
        game_id=leaderboard.game_id,
        leaderboard_kind=leaderboard.leaderboard_kind,
        entries=[
            SingleTaskLeaderboardEntryResponse(
                place=entry.place,
                user_id=entry.user_id,
                solved=entry.solved,
                solved_attempts=entry.solved_attempts,
                finished_attempts=entry.finished_attempts,
                best_score=entry.best_score,
                best_run_id=entry.best_run_id,
                last_finished_at=entry.last_finished_at,
            )
            for entry in leaderboard.entries
        ],
    )


def _build_slot_template_code(*, slot_key: str, code_api_mode: str) -> str:
    function_name = _resolve_template_function_name(slot_key=slot_key, code_api_mode=code_api_mode)
    if function_name == "place_tower":
        default_return = "0"
    elif function_name == "make_support":
        default_return = '"none"'
    else:
        default_return = '"stay"'
    return (
        f"def {function_name}(state):\n"
        f"    \"\"\"Starter template for slot '{slot_key}'.\"\"\"\n"
        "    # Добавьте вашу стратегию принятия решения\n"
        f"    return {default_return}\n"
    )


def _resolve_template_function_name(*, slot_key: str, code_api_mode: str) -> str:
    normalized = slot_key.strip().lower()
    if normalized == "defender":
        return "place_tower"
    if normalized == "support":
        return "make_support"
    if code_api_mode == "script_based":
        return "make_move"
    return "make_choice"
