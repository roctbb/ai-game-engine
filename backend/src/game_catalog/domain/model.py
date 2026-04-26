from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from shared.kernel import ConflictError, InvariantViolationError, NotFoundError, new_id, utc_now


class GameMode(StrEnum):
    SINGLE_TASK = "single_task"
    MULTIPLAYER = "multiplayer"
    # Legacy values kept for backward compatibility with existing DB rows and old manifests.
    SMALL_MATCH = "small_match"
    MASSIVE_LOBBY = "massive_lobby"


class CatalogMetadataStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class SlotDefinition:
    key: str
    title: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class GameVersion:
    version_id: str
    semver: str
    required_slots: tuple[SlotDefinition, ...]
    required_worker_labels: dict[str, str]
    created_at: object

    @property
    def required_slot_keys(self) -> tuple[str, ...]:
        return tuple(slot.key for slot in self.required_slots if slot.required)

    @property
    def slots_by_key(self) -> dict[str, SlotDefinition]:
        return {slot.key: slot for slot in self.required_slots}


@dataclass(slots=True)
class Game:
    game_id: str
    slug: str
    title: str
    mode: GameMode
    description: str | None = None
    difficulty: str | None = None
    learning_section: str | None = None
    topics: tuple[str, ...] = ()
    min_players_per_match: int | None = None
    max_players_per_match: int | None = None
    catalog_metadata_status: CatalogMetadataStatus = CatalogMetadataStatus.READY
    versions: dict[str, GameVersion] = field(default_factory=dict)
    active_version_id: str | None = None

    @staticmethod
    def create(
        slug: str,
        title: str,
        mode: GameMode,
        description: str | None = None,
        difficulty: str | None = None,
        learning_section: str | None = None,
        topics: tuple[str, ...] = (),
        min_players_per_match: int | None = None,
        max_players_per_match: int | None = None,
        catalog_metadata_status: CatalogMetadataStatus | None = None,
    ) -> "Game":
        normalized_topics = tuple(topic.strip() for topic in topics if topic.strip())
        normalized_description = description.strip() if description is not None else None
        normalized_difficulty = difficulty.strip().lower() if difficulty is not None else None
        normalized_learning_section = learning_section.strip() if learning_section is not None else None
        resolved_mode = GameMode.SINGLE_TASK if mode is GameMode.SINGLE_TASK else GameMode.MULTIPLAYER
        resolved_min_players, resolved_max_players = _resolve_match_player_bounds(
            mode=mode,
            min_players_per_match=min_players_per_match,
            max_players_per_match=max_players_per_match,
        )
        resolved_status = catalog_metadata_status
        if resolved_status is None:
            if (
                resolved_mode is GameMode.SINGLE_TASK
                and (
                    not normalized_description
                    or not normalized_difficulty
                    or not normalized_learning_section
                    or len(normalized_topics) == 0
                )
            ):
                resolved_status = CatalogMetadataStatus.DRAFT
            else:
                resolved_status = CatalogMetadataStatus.READY
        return Game(
            game_id=new_id("game"),
            slug=slug,
            title=title,
            mode=resolved_mode,
            description=normalized_description or None,
            difficulty=normalized_difficulty or None,
            learning_section=normalized_learning_section or None,
            topics=normalized_topics,
            min_players_per_match=resolved_min_players,
            max_players_per_match=resolved_max_players,
            catalog_metadata_status=resolved_status,
        )

    @property
    def is_multiplayer(self) -> bool:
        return self.mode in {GameMode.MULTIPLAYER, GameMode.SMALL_MATCH, GameMode.MASSIVE_LOBBY}

    @property
    def match_player_bounds(self) -> tuple[int, int]:
        return _resolve_match_player_bounds(
            mode=self.mode,
            min_players_per_match=self.min_players_per_match,
            max_players_per_match=self.max_players_per_match,
        )

    def set_match_player_bounds(
        self,
        *,
        min_players_per_match: int | None,
        max_players_per_match: int | None,
    ) -> None:
        self.min_players_per_match, self.max_players_per_match = _resolve_match_player_bounds(
            mode=self.mode,
            min_players_per_match=min_players_per_match,
            max_players_per_match=max_players_per_match,
        )

    def has_required_single_task_catalog_metadata(self) -> bool:
        return bool(self.description and self.difficulty and self.learning_section and self.topics)

    def add_version(
        self,
        semver: str,
        required_slots: tuple[SlotDefinition, ...],
        required_worker_labels: dict[str, str] | None = None,
    ) -> GameVersion:
        if any(version.semver == semver for version in self.versions.values()):
            raise ConflictError(f"Версия {semver} уже существует для игры {self.slug}")

        keys = [slot.key for slot in required_slots if slot.required]
        if len(set(keys)) != len(keys):
            raise InvariantViolationError("Обязательные слоты не должны дублироваться")

        labels = {
            str(key).strip(): str(value).strip()
            for key, value in (required_worker_labels or {}).items()
            if str(key).strip() and str(value).strip()
        }

        version = GameVersion(
            version_id=new_id("gver"),
            semver=semver,
            required_slots=required_slots,
            required_worker_labels=labels,
            created_at=utc_now(),
        )
        self.versions[version.version_id] = version
        if self.active_version_id is None:
            self.active_version_id = version.version_id
        return version

    def activate_version(self, version_id: str) -> None:
        if version_id not in self.versions:
            raise NotFoundError(f"Версия {version_id} не найдена")
        self.active_version_id = version_id

    @property
    def active_version(self) -> GameVersion:
        if self.active_version_id is None:
            raise InvariantViolationError("У игры нет активной версии")
        try:
            return self.versions[self.active_version_id]
        except KeyError as exc:
            raise InvariantViolationError("Активная версия отсутствует в реестре") from exc


def evaluate_slot_schema_compatibility(
    current_version: GameVersion, target_version: GameVersion
) -> tuple[bool, str | None]:
    current_slots = current_version.slots_by_key
    target_slots = target_version.slots_by_key

    for key, slot in current_slots.items():
        target_slot = target_slots.get(key)
        if target_slot is None:
            return False, f"Слот '{key}' отсутствует в новой версии"
        if slot.required and not target_slot.required:
            return False, f"Обязательный слот '{key}' не может стать необязательным"
        if not slot.required and target_slot.required:
            return False, f"Слот '{key}' не может стать обязательным"

    for key, target_slot in target_slots.items():
        if key not in current_slots and target_slot.required:
            return False, f"Новый обязательный слот '{key}' недопустим в v2"

    return True, None


def _resolve_match_player_bounds(
    *,
    mode: GameMode,
    min_players_per_match: int | None,
    max_players_per_match: int | None,
) -> tuple[int | None, int | None]:
    if mode is GameMode.SINGLE_TASK:
        return None, None

    legacy_min: int | None = None
    legacy_max: int | None = None
    if mode is GameMode.SMALL_MATCH:
        legacy_min = 2
        legacy_max = 2
    elif mode is GameMode.MASSIVE_LOBBY:
        legacy_min = 2
        legacy_max = 64

    resolved_min = min_players_per_match if min_players_per_match is not None else legacy_min
    resolved_max = max_players_per_match if max_players_per_match is not None else legacy_max
    if resolved_min is None or resolved_max is None:
        raise InvariantViolationError("Для multiplayer игры нужно указать min/max игроков в матче")
    if resolved_min < 2:
        raise InvariantViolationError("min_players_per_match должен быть >= 2")
    if resolved_max < resolved_min:
        raise InvariantViolationError("max_players_per_match должен быть >= min_players_per_match")
    if resolved_max > 64:
        raise InvariantViolationError("max_players_per_match должен быть <= 64")
    return resolved_min, resolved_max
