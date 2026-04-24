from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from shared.kernel import ConflictError, InvariantViolationError, NotFoundError, new_id, utc_now


class GameMode(StrEnum):
    SINGLE_TASK = "single_task"
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
    topics: tuple[str, ...] = ()
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
        topics: tuple[str, ...] = (),
        catalog_metadata_status: CatalogMetadataStatus | None = None,
    ) -> "Game":
        normalized_topics = tuple(topic.strip() for topic in topics if topic.strip())
        normalized_description = description.strip() if description is not None else None
        normalized_difficulty = difficulty.strip().lower() if difficulty is not None else None
        resolved_status = catalog_metadata_status
        if resolved_status is None:
            if (
                mode is GameMode.SINGLE_TASK
                and (
                    not normalized_description
                    or not normalized_difficulty
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
            mode=mode,
            description=normalized_description or None,
            difficulty=normalized_difficulty or None,
            topics=normalized_topics,
            catalog_metadata_status=resolved_status,
        )

    def has_required_single_task_catalog_metadata(self) -> bool:
        return bool(self.description and self.difficulty and self.topics)

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
