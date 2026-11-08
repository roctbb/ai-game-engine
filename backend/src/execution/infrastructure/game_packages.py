"""Immutable, content-addressed game packages shared by API and matchmaker."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
from pathlib import Path
import re
import tarfile
import tempfile

from execution.domain.model import Run
from game_catalog.application.service import GameCatalogService
from game_catalog.infrastructure.manifest_loader import find_game_manifest_path, load_game_manifest
from shared.kernel import NotFoundError, InvariantViolationError


class GamePackageStore:
    def __init__(
        self, game_catalog: GameCatalogService, games_root: Path, packages_root: Path
    ) -> None:
        self._catalog = game_catalog
        self._games_root = games_root
        self._packages_root = packages_root

    def freeze(self, run: Run) -> None:
        if run.execution_options.get("package_digest"):
            self.path(str(run.execution_options["package_digest"]))
            return
        game = self._catalog.get_game(run.game_id)
        try:
            manifest_path = find_game_manifest_path(self._games_root, game.slug)
        except InvariantViolationError:
            return  # Catalog-only games have no executable package.
        manifest = load_game_manifest(manifest_path)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for path in sorted(manifest_path.parent.rglob("*")):
                relative = path.relative_to(manifest_path.parent)
                if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                    continue
                if not path.is_file() or path.is_symlink() or path.suffix == ".pyc":
                    continue
                data = path.read_bytes()
                info = tarfile.TarInfo(str(relative))
                info.size, info.mode = len(data), 0o644
                archive.addfile(info, io.BytesIO(data))
        data = gzip.compress(buffer.getvalue(), mtime=0)
        digest = hashlib.sha256(data).hexdigest()
        self._packages_root.mkdir(parents=True, exist_ok=True)
        target = self._packages_root / f"{digest}.tar.gz"
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=self._packages_root, delete=False) as output:
                temporary = Path(output.name)
                output.write(data)
            os.replace(temporary, target)
        run.execution_options.update(
            {
                "package_digest": digest,
                "engine_entrypoint": manifest.engine_entrypoint,
                "renderer_entrypoint": manifest.renderer_entrypoint,
                "code_api_mode": manifest.code_api_mode,
                "game_package_dir": manifest_path.parent.name,
            }
        )

    def path(self, digest: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise NotFoundError("Некорректный digest игрового пакета")
        path = self._packages_root / f"{digest}.tar.gz"
        if not path.is_file():
            raise NotFoundError("Зафиксированный игровой пакет не найден")
        return path
