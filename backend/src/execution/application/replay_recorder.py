from __future__ import annotations

from typing import Protocol

from execution.domain.model import Run


class RunReplayRecorder(Protocol):
    def record_run(self, run: Run) -> None:
        ...


class NoopRunReplayRecorder:
    def record_run(self, run: Run) -> None:
        _ = run
        return None

