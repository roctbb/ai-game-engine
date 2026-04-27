from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal

from execution.application.service import ExecutionService
from execution.domain.model import RunKind, RunStatus
from game_catalog.application.service import GameCatalogService
from game_catalog.domain.model import CatalogMetadataStatus, Game, GameMode


_SCORE_CANDIDATE_KEYS = ("score", "points")
_SOLVED_STATUS_VALUES = {"success", "solved", "passed", "win", "won"}
_SOLVED_FLAG_KEYS = (
    "solved",
    "success",
    "passed",
    "completed",
    "reached_goal",
    "reached_exit",
    "escaped",
    "won",
    "victory",
    "is_win",
)


@dataclass(frozen=True, slots=True)
class SingleTaskAttemptRecord:
    run_id: str
    game_id: str
    user_id: str
    finished_at: datetime | None
    solved: bool
    score: float | None


@dataclass(frozen=True, slots=True)
class SingleTaskLeaderboardEntry:
    place: int
    user_id: str
    solved: bool
    solved_attempts: int
    finished_attempts: int
    best_score: float | None
    best_run_id: str | None
    last_finished_at: str | None


@dataclass(frozen=True, slots=True)
class SingleTaskLeaderboard:
    game_id: str
    leaderboard_kind: Literal["score", "solved"]
    entries: tuple[SingleTaskLeaderboardEntry, ...]


@dataclass(frozen=True, slots=True)
class SingleTaskCatalogItem:
    game_id: str
    slug: str
    title: str
    description: str | None
    difficulty: str | None
    learning_section: str | None
    topics: tuple[str, ...]
    catalog_metadata_status: CatalogMetadataStatus
    attempts_finished: int
    solved_users: int
    has_score_model: bool


@dataclass(frozen=True, slots=True)
class SolvedSummaryEntry:
    place: int
    user_id: str
    solved_tasks_count: int
    solved_game_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SolvedSummary:
    total_single_tasks: int
    entries: tuple[SolvedSummaryEntry, ...]


@dataclass(slots=True)
class _UserAggregate:
    user_id: str
    solved_attempts: int = 0
    finished_attempts: int = 0
    best_score: float | None = None
    best_run_id: str | None = None
    solved: bool = False
    first_solved_at: datetime | None = None
    last_finished_at: datetime | None = None


class SingleTaskProgressService:
    _attempts_cache: ClassVar[
        dict[str, tuple[object, tuple[SingleTaskAttemptRecord, ...]]]
    ] = {}

    def __init__(self, game_catalog: GameCatalogService, execution: ExecutionService) -> None:
        self._game_catalog = game_catalog
        self._execution = execution

    def list_single_tasks(self, *, include_non_ready: bool = False) -> list[Game]:
        games = [game for game in self._game_catalog.list_games() if game.mode is GameMode.SINGLE_TASK]
        if include_non_ready:
            return games
        return [game for game in games if game.catalog_metadata_status is CatalogMetadataStatus.READY]

    def build_single_task_catalog_items(self) -> tuple[SingleTaskCatalogItem, ...]:
        games = sorted(self.list_single_tasks(include_non_ready=False), key=lambda game: (game.title.lower(), game.slug))
        attempts = self._collect_attempts(game_id=None)

        attempts_count_by_game: dict[str, int] = {}
        solved_users_by_game: dict[str, set[str]] = {}
        has_score_model_by_game: dict[str, bool] = {}
        for attempt in attempts:
            attempts_count_by_game[attempt.game_id] = attempts_count_by_game.get(attempt.game_id, 0) + 1
            if attempt.solved:
                solved_users_by_game.setdefault(attempt.game_id, set()).add(attempt.user_id)
            if attempt.score is not None:
                has_score_model_by_game[attempt.game_id] = True

        return tuple(
            SingleTaskCatalogItem(
                game_id=game.game_id,
                slug=game.slug,
                title=game.title,
                description=game.description,
                difficulty=game.difficulty,
                learning_section=game.learning_section,
                topics=game.topics,
                catalog_metadata_status=game.catalog_metadata_status,
                attempts_finished=attempts_count_by_game.get(game.game_id, 0),
                solved_users=len(solved_users_by_game.get(game.game_id, set())),
                has_score_model=has_score_model_by_game.get(game.game_id, False),
            )
            for game in games
        )

    def build_leaderboard(self, game_id: str, limit: int = 20) -> SingleTaskLeaderboard:
        game = self._game_catalog.get_game(game_id)
        if game.mode is not GameMode.SINGLE_TASK:
            return SingleTaskLeaderboard(game_id=game_id, leaderboard_kind="solved", entries=())

        attempts = self._collect_attempts(game_id=game_id)
        aggregates: dict[str, _UserAggregate] = {}

        for attempt in attempts:
            profile = aggregates.setdefault(attempt.user_id, _UserAggregate(user_id=attempt.user_id))
            profile.finished_attempts += 1
            profile.last_finished_at = _max_dt(profile.last_finished_at, attempt.finished_at)
            if attempt.solved:
                profile.solved = True
                profile.solved_attempts += 1
                profile.first_solved_at = _min_dt(profile.first_solved_at, attempt.finished_at)
            if attempt.score is not None and (profile.best_score is None or attempt.score > profile.best_score):
                profile.best_score = attempt.score
                profile.best_run_id = attempt.run_id

        by_user = list(aggregates.values())
        if not by_user:
            return SingleTaskLeaderboard(game_id=game_id, leaderboard_kind="solved", entries=())

        has_score_model = any(item.best_score is not None for item in by_user)
        if has_score_model:
            by_user.sort(
                key=lambda item: (
                    -item.best_score if item.best_score is not None else float("inf"),
                    0 if item.solved else 1,
                    _dt_sort_key(item.last_finished_at, none_fallback=float("-inf")),
                    item.user_id,
                )
            )
            entries = self._to_score_leaderboard_entries(by_user)
            leaderboard_kind: Literal["score", "solved"] = "score"
        else:
            solved_only = [item for item in by_user if item.solved]
            solved_only.sort(
                key=lambda item: (
                    _dt_sort_key(item.first_solved_at, none_fallback=float("inf")),
                    item.user_id,
                )
            )
            entries = self._to_solved_leaderboard_entries(solved_only)
            leaderboard_kind = "solved"

        bounded = entries[: max(1, limit)] if entries else []
        return SingleTaskLeaderboard(game_id=game_id, leaderboard_kind=leaderboard_kind, entries=tuple(bounded))

    def build_solved_summary(self, limit: int = 20) -> SolvedSummary:
        published_task_ids = {game.game_id for game in self.list_single_tasks(include_non_ready=False)}
        attempts = [attempt for attempt in self._collect_attempts(game_id=None) if attempt.game_id in published_task_ids]
        solved_by_user: dict[str, set[str]] = {}
        for attempt in attempts:
            if not attempt.solved:
                continue
            solved_by_user.setdefault(attempt.user_id, set()).add(attempt.game_id)

        ordered = sorted(
            solved_by_user.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )

        entries: list[SolvedSummaryEntry] = []
        for index, (user_id, solved_games) in enumerate(ordered[: max(1, limit)], start=1):
            entries.append(
                SolvedSummaryEntry(
                    place=index,
                    user_id=user_id,
                    solved_tasks_count=len(solved_games),
                    solved_game_ids=tuple(sorted(solved_games)),
                )
            )

        total_single_tasks = len(published_task_ids)
        return SolvedSummary(total_single_tasks=total_single_tasks, entries=tuple(entries))

    def _collect_attempts(self, game_id: str | None) -> list[SingleTaskAttemptRecord]:
        runs = self._execution.list_runs(
            game_id=game_id,
            run_kind=RunKind.SINGLE_TASK,
            include_result_payload=False,
        )
        finished_runs = [run for run in runs if run.status == RunStatus.FINISHED]
        cache_key = game_id or "__all__"
        signature = tuple(
            sorted(
                (
                    run.run_id,
                    run.game_id,
                    run.requested_by,
                    run.finished_at,
                )
                for run in finished_runs
            )
        )
        cached = self._attempts_cache.get(cache_key)
        if cached is not None and cached[0] == signature:
            return list(cached[1])

        attempts: list[SingleTaskAttemptRecord] = []
        for run in finished_runs:
            if run.result_payload is None:
                run = self._execution.get_run(run.run_id)
            payload = run.result_payload
            if not isinstance(payload, dict):
                continue
            metrics_raw = payload.get("metrics")
            metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
            solved = _infer_solved(payload=payload, metrics=metrics)
            score = _extract_score(payload=payload, metrics=metrics)
            attempts.append(
                SingleTaskAttemptRecord(
                    run_id=run.run_id,
                    game_id=run.game_id,
                    user_id=run.requested_by,
                    finished_at=run.finished_at if isinstance(run.finished_at, datetime) else None,
                    solved=solved,
                    score=score,
                )
            )
        self._attempts_cache[cache_key] = (signature, tuple(attempts))
        return attempts

    @staticmethod
    def _to_score_leaderboard_entries(items: list[_UserAggregate]) -> list[SingleTaskLeaderboardEntry]:
        entries: list[SingleTaskLeaderboardEntry] = []
        place = 0
        prev_score: float | None = None
        for index, item in enumerate(items, start=1):
            if item.best_score is None:
                if prev_score is not None:
                    place = index
                    prev_score = None
                elif place == 0:
                    place = index
            else:
                if prev_score is None or item.best_score != prev_score:
                    place = index
                    prev_score = item.best_score
            entries.append(
                SingleTaskLeaderboardEntry(
                    place=place,
                    user_id=item.user_id,
                    solved=item.solved,
                    solved_attempts=item.solved_attempts,
                    finished_attempts=item.finished_attempts,
                    best_score=item.best_score,
                    best_run_id=item.best_run_id,
                    last_finished_at=_to_iso(item.last_finished_at),
                )
            )
        return entries

    @staticmethod
    def _to_solved_leaderboard_entries(items: list[_UserAggregate]) -> list[SingleTaskLeaderboardEntry]:
        entries: list[SingleTaskLeaderboardEntry] = []
        for index, item in enumerate(items, start=1):
            entries.append(
                SingleTaskLeaderboardEntry(
                    place=index,
                    user_id=item.user_id,
                    solved=item.solved,
                    solved_attempts=item.solved_attempts,
                    finished_attempts=item.finished_attempts,
                    best_score=item.best_score,
                    best_run_id=item.best_run_id,
                    last_finished_at=_to_iso(item.last_finished_at),
                )
            )
        return entries


def _extract_score(payload: dict[str, object], metrics: dict[str, object]) -> float | None:
    for key in _SCORE_CANDIDATE_KEYS:
        value = metrics.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    for key in _SCORE_CANDIDATE_KEYS:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _infer_solved(payload: dict[str, object], metrics: dict[str, object]) -> bool:
    compile_error = metrics.get("compile_error")
    if isinstance(compile_error, str) and compile_error.strip():
        return False

    solved_flag = metrics.get("solved")
    if isinstance(solved_flag, bool):
        return solved_flag

    solved_from_payload = payload.get("solved")
    if isinstance(solved_from_payload, bool):
        return solved_from_payload

    status = payload.get("status")
    if isinstance(status, str) and status.strip().lower() in _SOLVED_STATUS_VALUES:
        return True

    for key in _SOLVED_FLAG_KEYS:
        value = metrics.get(key)
        if isinstance(value, bool) and value:
            return True
    return False


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _min_dt(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if left <= right else right


def _max_dt(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if left >= right else right


def _dt_sort_key(value: datetime | None, *, none_fallback: float) -> float:
    if value is None:
        return none_fallback
    return value.timestamp()
