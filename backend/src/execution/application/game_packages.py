from pathlib import Path
from typing import Protocol

from execution.domain.model import Run


class GamePackageProvider(Protocol):
    def freeze(self, run: Run) -> None: ...

    def path(self, digest: str) -> Path: ...
