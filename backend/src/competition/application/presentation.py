from __future__ import annotations

from datetime import UTC, datetime, timedelta

from competition.domain.model import CompetitionMatch, CompetitionRound
from execution.domain.model import Run, RunStatus

FRAME_MS = 500
RESULT_SECONDS = 2
_TERMINAL = {RunStatus.FINISHED, RunStatus.FAILED, RunStatus.TIMEOUT, RunStatus.CANCELED}


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def schedule_round_show(round_item: CompetitionRound, runs: dict[str, Run]) -> bool:
    """Freeze a common timeline once all calculations are ready; retain shown slots on retry."""
    playable = [match for match in round_item.matches if len(match.team_ids) > 1]
    if not playable or any(
        len(match.run_ids_by_team) != len(match.team_ids) or any(
            run_id not in runs or runs[run_id].status not in _TERMINAL or runs[run_id].finished_at is None
            for run_id in match.run_ids_by_team.values()
        ) for match in playable
    ):
        return False
    cursor = max(as_utc(runs[run_id].finished_at) for match in playable
                 for run_id in match.run_ids_by_team.values())
    changed = False
    for match in playable:
        if match.show_started_at is not None and match.show_ends_at is not None:
            cursor = max(cursor, as_utc(match.show_ends_at))
            continue
        match_runs = [runs[run_id] for run_id in match.run_ids_by_team.values()]
        frame_count = max(_frame_count(run) for run in match_runs)
        match.show_started_at = cursor
        match.show_reveal_at = cursor + timedelta(seconds=max(1, (frame_count - 1) * FRAME_MS / 1000))
        match.show_ends_at = match.show_reveal_at + timedelta(seconds=RESULT_SECONDS)
        cursor = match.show_ends_at
        changed = True
    return changed


def results_revealed(match: CompetitionMatch, now: datetime) -> bool:
    return match.show_reveal_at is not None and as_utc(now) >= as_utc(match.show_reveal_at)


def _frame_count(run: Run) -> int:
    summary = run.result_summary or {}
    count = summary.get("replay_frame_count")
    if isinstance(count, int) and count > 0:
        return count
    frames = (run.result_payload or {}).get("frames")
    return max(1, len(frames)) if isinstance(frames, list) else 1
