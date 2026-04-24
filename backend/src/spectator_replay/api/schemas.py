from __future__ import annotations

from pydantic import BaseModel

from execution.domain.model import RunKind, RunStatus
from spectator_replay.domain.model import ReplayVisibility


class ReplayResponse(BaseModel):
    replay_id: str
    run_id: str
    game_id: str
    run_kind: RunKind
    status: RunStatus
    visibility: ReplayVisibility
    frames: list[dict[str, object]]
    events: list[dict[str, object]]
    summary: dict[str, object]
    created_at: object
    updated_at: object
