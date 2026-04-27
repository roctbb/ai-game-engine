from __future__ import annotations

from dataclasses import dataclass

from execution.domain.model import Run, RunKind, RunStatus
from spectator_replay.application.repositories import ReplayRepository
from spectator_replay.domain.model import ReplayRecord, ReplayVisibility, require_replay

@dataclass(slots=True)
class ListReplaysQuery:
    game_id: str | None = None
    run_kind: RunKind | None = None
    limit: int = 50


class SpectatorReplayService:
    def __init__(self, repository: ReplayRepository) -> None:
        self._repository = repository

    def record_run(self, run: Run) -> None:
        if run.status is not RunStatus.FINISHED:
            self._repository.delete_by_run_ids([run.run_id])
            return

        frames, events, summary = _build_replay_payload(run)
        current = self._repository.get_by_run_id(run.run_id)
        if current is None:
            current = ReplayRecord.create(
                run_id=run.run_id,
                game_id=run.game_id,
                run_kind=run.run_kind,
                status=run.status,
                visibility=ReplayVisibility.PUBLIC,
                frames=frames,
                events=events,
                summary=summary,
            )
        else:
            current.update_content(
                status=run.status,
                frames=frames,
                events=events,
                summary=summary,
            )
        self._repository.save(current)

    def get_by_run_id(self, run_id: str, *, include_content: bool = True) -> ReplayRecord:
        return require_replay(
            self._repository.get_by_run_id(run_id, include_content=include_content),
            run_id=run_id,
        )

    def list_replays(self, query: ListReplaysQuery) -> list[ReplayRecord]:
        bounded_limit = max(1, min(query.limit, 200))
        return self._repository.list(
            game_id=query.game_id,
            run_kind=query.run_kind,
            limit=bounded_limit,
            include_content=False,
        )

    def delete_runs(self, run_ids: list[str]) -> None:
        self._repository.delete_by_run_ids(run_ids)


def _build_replay_payload(run: Run) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    payload = run.result_payload if isinstance(run.result_payload, dict) else {}

    raw_frames = payload.get("frames")
    frames = _normalize_dict_items(raw_frames)
    if not frames:
        frames = [
            {
                "tick": 0,
                "phase": run.status.value,
                "frame": payload,
            }
        ]

    raw_events = payload.get("events")
    events = _normalize_dict_items(raw_events)
    if run.error_message:
        events = events + [{"type": "run_error", "message": run.error_message}]

    summary: dict[str, object] = {
        "status": run.status.value,
        "run_kind": run.run_kind.value,
        "team_id": run.team_id,
        "worker_id": run.worker_id,
        "metrics": payload.get("metrics", {}),
        "scores": payload.get("scores", {}),
        "placements": payload.get("placements", {}),
        "error_message": run.error_message,
    }
    return frames, events, summary


def _normalize_dict_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(dict(item))
    return result
