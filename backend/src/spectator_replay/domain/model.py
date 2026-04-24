from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from execution.domain.model import RunKind, RunStatus
from shared.kernel import NotFoundError, new_id, utc_now


class ReplayVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass(slots=True)
class ReplayRecord:
    replay_id: str
    run_id: str
    game_id: str
    run_kind: RunKind
    status: RunStatus
    visibility: ReplayVisibility
    frames: list[dict[str, object]]
    events: list[dict[str, object]]
    summary: dict[str, object]
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)

    @staticmethod
    def create(
        run_id: str,
        game_id: str,
        run_kind: RunKind,
        status: RunStatus,
        visibility: ReplayVisibility,
        frames: list[dict[str, object]],
        events: list[dict[str, object]],
        summary: dict[str, object],
    ) -> "ReplayRecord":
        return ReplayRecord(
            replay_id=new_id("replay"),
            run_id=run_id,
            game_id=game_id,
            run_kind=run_kind,
            status=status,
            visibility=visibility,
            frames=frames,
            events=events,
            summary=summary,
        )

    def update_content(
        self,
        status: RunStatus,
        frames: list[dict[str, object]],
        events: list[dict[str, object]],
        summary: dict[str, object],
    ) -> None:
        self.status = status
        self.frames = frames
        self.events = events
        self.summary = summary
        self.updated_at = utc_now()


def require_replay(value: ReplayRecord | None, run_id: str) -> ReplayRecord:
    if value is None:
        raise NotFoundError(f"Replay для run {run_id} не найден")
    return value

