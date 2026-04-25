from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from game_catalog.domain.model import CatalogMetadataStatus, Game, GameMode, GameVersion, SlotDefinition
from game_catalog.infrastructure.sqlalchemy_models import CatalogGameOrm, CatalogGameVersionOrm


class SqlAlchemyGameRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, game: Game) -> None:
        with self._session_factory.begin() as session:
            existing_game = session.get(CatalogGameOrm, game.game_id)
            if existing_game is None:
                existing_game = CatalogGameOrm(
                    game_id=game.game_id,
                    slug=game.slug,
                    title=game.title,
                    mode=game.mode.value,
                    description=game.description,
                    difficulty=game.difficulty,
                    learning_section=game.learning_section,
                    topics=list(game.topics),
                    catalog_metadata_status=game.catalog_metadata_status.value,
                    active_version_id=game.active_version_id,
                )
                session.add(existing_game)
            else:
                existing_game.slug = game.slug
                existing_game.title = game.title
                existing_game.mode = game.mode.value
                existing_game.description = game.description
                existing_game.difficulty = game.difficulty
                existing_game.learning_section = game.learning_section
                existing_game.topics = list(game.topics)
                existing_game.catalog_metadata_status = game.catalog_metadata_status.value
                existing_game.active_version_id = game.active_version_id

            existing_versions = session.scalars(
                select(CatalogGameVersionOrm).where(CatalogGameVersionOrm.game_id == game.game_id)
            ).all()
            incoming_version_ids = set(game.versions.keys())
            for existing in existing_versions:
                if existing.version_id not in incoming_version_ids:
                    session.delete(existing)

            for version in game.versions.values():
                session.merge(_map_version_to_orm(game_id=game.game_id, version=version))

    def get(self, game_id: str) -> Game | None:
        with self._session_factory() as session:
            game_row = session.get(CatalogGameOrm, game_id)
            if game_row is None:
                return None
            version_rows = session.scalars(
                select(CatalogGameVersionOrm).where(CatalogGameVersionOrm.game_id == game_row.game_id)
            ).all()
            return _map_game_from_rows(game_row, version_rows)

    def get_by_slug(self, slug: str) -> Game | None:
        with self._session_factory() as session:
            game_row = session.scalar(select(CatalogGameOrm).where(CatalogGameOrm.slug == slug))
            if game_row is None:
                return None
            version_rows = session.scalars(
                select(CatalogGameVersionOrm).where(CatalogGameVersionOrm.game_id == game_row.game_id)
            ).all()
            return _map_game_from_rows(game_row, version_rows)

    def list(self) -> list[Game]:
        with self._session_factory() as session:
            game_rows = session.scalars(select(CatalogGameOrm).order_by(CatalogGameOrm.slug)).all()
            if not game_rows:
                return []

            result: list[Game] = []
            for game_row in game_rows:
                version_rows = session.scalars(
                    select(CatalogGameVersionOrm).where(CatalogGameVersionOrm.game_id == game_row.game_id)
                ).all()
                result.append(_map_game_from_rows(game_row, version_rows))
            return result


def _map_version_to_orm(game_id: str, version: GameVersion) -> CatalogGameVersionOrm:
    return CatalogGameVersionOrm(
        version_id=version.version_id,
        game_id=game_id,
        semver=version.semver,
        required_slots_json=[
            {
                "key": slot.key,
                "title": slot.title,
                "required": slot.required,
            }
            for slot in version.required_slots
        ],
        required_worker_labels_json=dict(version.required_worker_labels),
        created_at=version.created_at,
    )


def _map_game_from_rows(
    game_row: CatalogGameOrm, version_rows: list[CatalogGameVersionOrm]
) -> Game:
    versions: dict[str, GameVersion] = {}
    for version_row in version_rows:
        slots = tuple(
            SlotDefinition(
                key=str(item["key"]),
                title=str(item["title"]),
                required=bool(item.get("required", True)),
            )
            for item in (version_row.required_slots_json or [])
        )
        versions[version_row.version_id] = GameVersion(
            version_id=version_row.version_id,
            semver=version_row.semver,
            required_slots=slots,
            required_worker_labels=dict(version_row.required_worker_labels_json or {}),
            created_at=version_row.created_at,
        )

    return Game(
        game_id=game_row.game_id,
        slug=game_row.slug,
        title=game_row.title,
        mode=GameMode(game_row.mode),
        description=game_row.description,
        difficulty=game_row.difficulty,
        learning_section=game_row.learning_section,
        topics=tuple(game_row.topics or []),
        catalog_metadata_status=CatalogMetadataStatus(game_row.catalog_metadata_status or "ready"),
        versions=versions,
        active_version_id=game_row.active_version_id,
    )
