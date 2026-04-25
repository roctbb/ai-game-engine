from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from game_catalog.application.service import RegisterGameInput
from game_catalog.domain.model import CatalogMetadataStatus, GameMode, SlotDefinition
from shared.kernel import InvariantViolationError


class ManifestSlot(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    required: bool = True


class ManifestDemoStrategy(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    slot_key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    language: Literal["python"] = "python"
    path: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)


class GameManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=255)
    game_mode: GameMode
    semver: str = Field(min_length=1, max_length=32)
    code_api_mode: Literal["turn_based", "script_based"]
    engine_entrypoint: str = Field(min_length=1, max_length=255)
    slots: tuple[ManifestSlot, ...] = Field(min_length=1)
    renderer_entrypoint: str | None = Field(default=None, max_length=255)
    player_instruction: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=2000)
    difficulty: str | None = Field(default=None, max_length=32)
    topics: tuple[str, ...] = ()
    required_worker_labels: dict[str, str] = Field(default_factory=dict)
    catalog_metadata_status: CatalogMetadataStatus | None = None
    demo_strategies: tuple[ManifestDemoStrategy, ...] = ()

    @field_validator("slots")
    @classmethod
    def validate_unique_slot_keys(cls, slots: tuple[ManifestSlot, ...]) -> tuple[ManifestSlot, ...]:
        keys = [slot.key for slot in slots]
        if len(keys) != len(set(keys)):
            raise ValueError("slot keys must be unique")
        return slots

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, topics: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(topic.strip() for topic in topics if topic.strip())
        if len(normalized) != len(set(normalized)):
            raise ValueError("topics must be unique")
        return normalized

    @field_validator("required_worker_labels")
    @classmethod
    def validate_required_worker_labels(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, raw in value.items():
            label_key = str(key).strip()
            label_value = str(raw).strip()
            if not label_key or not label_value:
                raise ValueError("required_worker_labels must contain non-empty key/value")
            normalized[label_key] = label_value
        return normalized

    @model_validator(mode="after")
    def validate_demo_strategies(self) -> GameManifest:
        slot_keys = {slot.key for slot in self.slots}
        strategy_ids: set[str] = set()
        strategy_paths: set[str] = set()
        for strategy in self.demo_strategies:
            if strategy.slot_key not in slot_keys:
                raise ValueError(f"demo strategy {strategy.id} references unknown slot {strategy.slot_key}")
            if strategy.id in strategy_ids:
                raise ValueError("demo strategy ids must be unique")
            if strategy.path in strategy_paths:
                raise ValueError("demo strategy paths must be unique")
            strategy_ids.add(strategy.id)
            strategy_paths.add(strategy.path)
        return self

    def to_register_input(self) -> RegisterGameInput:
        return RegisterGameInput(
            slug=self.id,
            title=self.title,
            mode=self.game_mode,
            semver=self.semver,
            description=self.description,
            difficulty=self.difficulty,
            topics=self.topics,
            required_worker_labels=self.required_worker_labels,
            catalog_metadata_status=self.catalog_metadata_status,
            required_slots=tuple(
                SlotDefinition(key=slot.key, title=slot.title, required=slot.required)
                for slot in self.slots
            ),
        )


def load_game_manifests(games_root: Path, *, strict: bool = False) -> list[GameManifest]:
    manifests: list[GameManifest] = []
    if not games_root.exists():
        return manifests

    for manifest_path in sorted(games_root.glob("*/manifest.yaml")):
        try:
            manifests.append(load_game_manifest(manifest_path))
        except InvariantViolationError:
            if strict:
                raise
            continue
    return manifests


def find_game_manifest_path(games_root: Path, game_id: str) -> Path:
    for manifest_path in sorted(games_root.glob("*/manifest.yaml")):
        try:
            manifest = load_game_manifest(manifest_path)
        except InvariantViolationError:
            continue
        if manifest.id == game_id:
            return manifest_path
    raise InvariantViolationError(f"Manifest для игры {game_id} не найден")


def load_game_manifest(manifest_path: Path) -> GameManifest:
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise InvariantViolationError(f"Некорректный YAML manifest: {manifest_path}") from exc

    if not isinstance(raw, dict):
        raise InvariantViolationError(f"Manifest должен быть объектом: {manifest_path}")

    try:
        manifest = GameManifest.model_validate(raw)
    except ValidationError as exc:
        raise InvariantViolationError(f"Некорректный manifest {manifest_path}: {exc}") from exc

    _ensure_package_file(manifest_path.parent, manifest.engine_entrypoint, manifest_path)
    if manifest.renderer_entrypoint:
        _ensure_package_file(manifest_path.parent, manifest.renderer_entrypoint, manifest_path)
    for strategy in manifest.demo_strategies:
        _ensure_package_file(manifest_path.parent, strategy.path, manifest_path)
    return manifest


def _ensure_package_file(package_root: Path, relative_path: str, manifest_path: Path) -> None:
    candidate = (package_root / relative_path).resolve()
    package_root = package_root.resolve()
    if package_root not in candidate.parents or not candidate.is_file():
        raise InvariantViolationError(
            f"Manifest {manifest_path} ссылается на отсутствующий файл: {relative_path}"
        )
