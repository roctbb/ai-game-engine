from __future__ import annotations

from dataclasses import dataclass, field

from game_catalog.application.repositories import GameRepository
from game_catalog.domain.model import (
    CatalogMetadataStatus,
    Game,
    GameMode,
    GameVersion,
    SlotDefinition,
    evaluate_slot_schema_compatibility,
)
from shared.kernel import ConflictError, InvariantViolationError, NotFoundError


@dataclass(slots=True)
class RegisterGameInput:
    slug: str
    title: str
    mode: GameMode
    semver: str
    required_slots: tuple[SlotDefinition, ...]
    required_worker_labels: dict[str, str] = field(default_factory=dict)
    description: str | None = None
    difficulty: str | None = None
    topics: tuple[str, ...] = ()
    catalog_metadata_status: CatalogMetadataStatus | None = None


class GameCatalogService:
    def __init__(self, repository: GameRepository) -> None:
        self._repository = repository

    def register_game(self, data: RegisterGameInput) -> Game:
        if self._repository.get_by_slug(data.slug) is not None:
            raise ConflictError(f"Игра со slug={data.slug} уже зарегистрирована")

        game = Game.create(
            slug=data.slug,
            title=data.title,
            mode=data.mode,
            description=data.description,
            difficulty=data.difficulty,
            topics=data.topics,
            catalog_metadata_status=data.catalog_metadata_status,
        )
        game.add_version(
            semver=data.semver,
            required_slots=data.required_slots,
            required_worker_labels=data.required_worker_labels,
        )
        self._repository.save(game)
        return game

    def update_catalog_metadata(
        self,
        game_id: str,
        *,
        description: str | None,
        difficulty: str | None,
        topics: tuple[str, ...],
        catalog_metadata_status: CatalogMetadataStatus | None = None,
    ) -> Game:
        game = self._get_game(game_id)
        game.description = description.strip() if description is not None and description.strip() else None
        game.difficulty = difficulty.strip().lower() if difficulty is not None and difficulty.strip() else None
        game.topics = tuple(topic.strip() for topic in topics if topic.strip())
        if catalog_metadata_status is not None:
            game.catalog_metadata_status = catalog_metadata_status
        if game.mode is GameMode.SINGLE_TASK:
            if (
                game.catalog_metadata_status is CatalogMetadataStatus.READY
                and not game.has_required_single_task_catalog_metadata()
            ):
                raise InvariantViolationError(
                    "single_task не может иметь catalog_metadata_status=ready без description/difficulty/topics"
                )
        self._repository.save(game)
        return game

    def update_game(
        self,
        game_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        difficulty: str | None = None,
        topics: tuple[str, ...] | None = None,
        catalog_metadata_status: CatalogMetadataStatus | None = None,
    ) -> Game:
        game = self._get_game(game_id)
        if title is not None:
            normalized_title = title.strip()
            if not normalized_title:
                raise InvariantViolationError("title не может быть пустым")
            game.title = normalized_title

        if description is not None:
            game.description = description.strip() if description.strip() else None
        if difficulty is not None:
            game.difficulty = difficulty.strip().lower() if difficulty.strip() else None
        if topics is not None:
            game.topics = tuple(topic.strip() for topic in topics if topic.strip())
        if catalog_metadata_status is not None:
            game.catalog_metadata_status = catalog_metadata_status

        if (
            game.mode is GameMode.SINGLE_TASK
            and game.catalog_metadata_status is CatalogMetadataStatus.READY
            and not game.has_required_single_task_catalog_metadata()
        ):
            raise InvariantViolationError(
                "single_task не может иметь catalog_metadata_status=ready без description/difficulty/topics"
            )

        self._repository.save(game)
        return game

    def add_game_version(
        self,
        game_id: str,
        semver: str,
        required_slots: tuple[SlotDefinition, ...],
        required_worker_labels: dict[str, str] | None = None,
    ) -> GameVersion:
        game = self._get_game(game_id)
        version = game.add_version(
            semver=semver,
            required_slots=required_slots,
            required_worker_labels=required_worker_labels,
        )
        self._repository.save(game)
        return version

    def activate_game_version(self, game_id: str, version_id: str) -> Game:
        game = self._get_game(game_id)
        game.activate_version(version_id)
        self._repository.save(game)
        return game

    def get_game(self, game_id: str) -> Game:
        return self._get_game(game_id)

    def list_games(self) -> list[Game]:
        return self._repository.list()

    def get_version(self, game_id: str, version_id: str | None) -> GameVersion:
        game = self._get_game(game_id)
        if version_id is None:
            return game.active_version
        try:
            return game.versions[version_id]
        except KeyError as exc:
            raise NotFoundError(f"Версия {version_id} не найдена") from exc

    def assert_compatible_slot_schema(
        self, game_id: str, current_version_id: str, target_version_id: str
    ) -> None:
        current_version = self.get_version(game_id=game_id, version_id=current_version_id)
        target_version = self.get_version(game_id=game_id, version_id=target_version_id)
        compatible, reason = evaluate_slot_schema_compatibility(
            current_version=current_version,
            target_version=target_version,
        )
        if not compatible:
            detail = reason or "Несовместимая slot schema"
            raise ConflictError(f"GAME_SYNC_INCOMPATIBLE_SLOT_SCHEMA: {detail}")

    def _get_game(self, game_id: str) -> Game:
        game = self._repository.get(game_id)
        if game is None:
            raise NotFoundError(f"Игра {game_id} не найдена")
        return game
