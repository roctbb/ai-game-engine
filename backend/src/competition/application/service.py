from __future__ import annotations

from dataclasses import dataclass

from competition.application.repositories import CompetitionRepository
from competition.domain.model import (
    Competition,
    CompetitionFormat,
    CompetitionMatch,
    CompetitionMatchStatus,
    CompetitionStatus,
    TieBreakPolicy,
)
from execution.application.service import CreateRunInput, ExecutionService
from execution.domain.model import Run, RunKind, RunStatus
from game_catalog.application.service import GameCatalogService
from shared.kernel import InvariantViolationError, NotFoundError
from team_workspace.application.service import TeamWorkspaceService


@dataclass(slots=True)
class CreateCompetitionInput:
    game_id: str
    title: str
    format: CompetitionFormat
    tie_break_policy: TieBreakPolicy
    advancement_top_k: int
    match_size: int


@dataclass(slots=True)
class ResolveTieInput:
    round_index: int
    match_id: str
    advanced_team_ids: list[str]


@dataclass(slots=True)
class _MatchOutcome:
    scores_by_team: dict[str, float]
    placements_by_team: dict[str, int]
    advanced_team_ids: list[str]
    requires_manual_tiebreak: bool = False
    tiebreak_reason: str | None = None


_TERMINAL_STATUSES = {
    RunStatus.FINISHED,
    RunStatus.FAILED,
    RunStatus.TIMEOUT,
    RunStatus.CANCELED,
}
_ACTIVE_STATUSES = {
    RunStatus.CREATED,
    RunStatus.QUEUED,
    RunStatus.RUNNING,
}


class CompetitionService:
    def __init__(
        self,
        repository: CompetitionRepository,
        game_catalog: GameCatalogService,
        team_workspace: TeamWorkspaceService,
        execution: ExecutionService,
    ) -> None:
        self._repository = repository
        self._game_catalog = game_catalog
        self._team_workspace = team_workspace
        self._execution = execution

    def create_competition(self, data: CreateCompetitionInput) -> Competition:
        game = self._game_catalog.get_game(data.game_id)
        competition = Competition.create(
            game_id=game.game_id,
            game_version_id=game.active_version.version_id,
            title=data.title,
            format=data.format,
            tie_break_policy=data.tie_break_policy,
            advancement_top_k=data.advancement_top_k,
            match_size=data.match_size,
        )
        self._repository.save(competition)
        return competition

    def list_competitions(self) -> list[Competition]:
        return self._repository.list()

    def get_competition(self, competition_id: str) -> Competition:
        competition = self._repository.get(competition_id)
        if competition is None:
            raise NotFoundError(f"Соревнование {competition_id} не найдено")
        return competition

    def update_competition(
        self,
        competition_id: str,
        *,
        title: str | None = None,
        tie_break_policy: TieBreakPolicy | None = None,
        advancement_top_k: int | None = None,
        match_size: int | None = None,
    ) -> Competition:
        competition = self.get_competition(competition_id)
        if competition.status is not CompetitionStatus.DRAFT:
            raise InvariantViolationError("Редактирование соревнования доступно только в статусе draft")

        if title is not None:
            normalized_title = title.strip()
            if not normalized_title:
                raise InvariantViolationError("title не может быть пустым")
            competition.title = normalized_title
        if tie_break_policy is not None:
            competition.tie_break_policy = tie_break_policy
        if advancement_top_k is not None:
            if advancement_top_k < 1:
                raise InvariantViolationError("advancement_top_k должен быть >= 1")
            competition.advancement_top_k = advancement_top_k
        if match_size is not None:
            if match_size < 2:
                raise InvariantViolationError("match_size должен быть >= 2")
            competition.match_size = match_size
        if competition.advancement_top_k > competition.match_size:
            raise InvariantViolationError("advancement_top_k не может быть больше match_size")

        self._repository.save(competition)
        return competition

    def register_team(self, competition_id: str, team_id: str) -> Competition:
        competition = self.get_competition(competition_id)
        team = self._team_workspace.get_team(team_id)
        if team.game_id != competition.game_id:
            raise InvariantViolationError("Команда может участвовать только в соревновании своей игры")

        competition.register_team(team_id)
        self._revalidate_one_entrant(competition=competition, team_id=team_id)
        self._repository.save(competition)
        return competition

    def unregister_team(self, competition_id: str, team_id: str) -> Competition:
        competition = self.get_competition(competition_id)
        competition.unregister_team(team_id)
        self._repository.save(competition)
        return competition

    def set_not_ready(self, competition_id: str, team_id: str, reason: str | None) -> Competition:
        competition = self.get_competition(competition_id)
        competition.set_ready(team_id=team_id, ready=False, blocker_reason=reason)
        self._repository.save(competition)
        return competition

    def set_ban(self, competition_id: str, team_id: str, banned: bool, reason: str | None) -> Competition:
        competition = self.get_competition(competition_id)
        competition.set_ban(team_id=team_id, banned=banned, blocker_reason=reason)
        if banned:
            active_runs = self._execution.list_runs(
                team_id=team_id,
                lobby_id=competition.competition_id,
                run_kind=RunKind.COMPETITION_MATCH,
            )
            for run in active_runs:
                if run.status in _ACTIVE_STATUSES:
                    self._execution.cancel_run(run.run_id, message="manual_moderation_ban")
        self._repository.save(competition)
        return competition

    def start_competition(self, competition_id: str, requested_by: str) -> Competition:
        competition = self.get_competition(competition_id)
        self._revalidate_all_entrants(competition)
        competition.start()

        if competition.current_round_index is None:
            seed_team_ids = self._seed_team_ids(competition)
            competition.seed_first_round(seed_team_ids)

        run_ids = self._schedule_current_round(competition=competition, requested_by=requested_by)
        competition.set_last_scheduled_runs(run_ids)
        self._repository.save(competition)
        return competition

    def pause_competition(self, competition_id: str) -> Competition:
        competition = self.get_competition(competition_id)
        competition.pause()
        self._repository.save(competition)
        return competition

    def finish_competition(self, competition_id: str) -> Competition:
        competition = self.get_competition(competition_id)
        competition.finish()
        self._repository.save(competition)
        return competition

    def advance_competition(self, competition_id: str, requested_by: str) -> Competition:
        competition = self.get_competition(competition_id)
        if competition.status is not CompetitionStatus.RUNNING:
            raise InvariantViolationError("Продвижение раунда доступно только в running")

        current_round = competition.get_current_round()
        if current_round is None:
            raise InvariantViolationError("Для соревнования не создан активный раунд")

        runs = self._execution.list_runs(
            lobby_id=competition.competition_id,
            run_kind=RunKind.COMPETITION_MATCH,
        )
        runs_by_id = {run.run_id: run for run in runs}

        next_seed: list[str] = []
        found_tiebreak = False

        for match in current_round.matches:
            if match.status in {CompetitionMatchStatus.FINISHED, CompetitionMatchStatus.AUTO_ADVANCED}:
                next_seed.extend(match.advanced_team_ids)
                continue
            if match.status is CompetitionMatchStatus.AWAITING_TIEBREAK:
                found_tiebreak = True
                continue

            match_runs = self._require_terminal_match_runs(match=match, runs_by_id=runs_by_id)
            outcome = self._build_match_outcome(competition=competition, match=match, runs=match_runs)
            if outcome.requires_manual_tiebreak:
                competition.mark_match_awaiting_tiebreak(
                    round_index=current_round.round_index,
                    match_id=match.match_id,
                    reason=outcome.tiebreak_reason or "Требуется ручное tie-break решение",
                )
                found_tiebreak = True
                continue

            competition.mark_match_finished(
                round_index=current_round.round_index,
                match_id=match.match_id,
                scores_by_team=outcome.scores_by_team,
                placements_by_team=outcome.placements_by_team,
                advanced_team_ids=outcome.advanced_team_ids,
            )
            next_seed.extend(outcome.advanced_team_ids)

        if found_tiebreak:
            if competition.status is CompetitionStatus.RUNNING:
                competition.pause()
            competition.set_pending_reason(
                "Найдено неоднозначное определение прохода в следующий раунд. Требуется ручное решение."
            )
            self._repository.save(competition)
            return competition

        competition.mark_round_finished(round_index=current_round.round_index)
        competition.set_pending_reason(None)
        next_seed = [team_id for team_id in next_seed if team_id]

        if len(next_seed) <= 1:
            competition.finish_with_winners(next_seed)
            self._repository.save(competition)
            return competition

        competition.create_next_round(next_seed)
        run_ids = self._schedule_current_round(competition=competition, requested_by=requested_by)
        competition.set_last_scheduled_runs(run_ids)
        self._repository.save(competition)
        return competition

    def resolve_match_tiebreak(self, competition_id: str, data: ResolveTieInput) -> Competition:
        competition = self.get_competition(competition_id)
        competition.resolve_match_tiebreak(
            round_index=data.round_index,
            match_id=data.match_id,
            advanced_team_ids=data.advanced_team_ids,
        )
        competition.set_pending_reason(None)
        self._repository.save(competition)
        return competition

    def _revalidate_all_entrants(self, competition: Competition) -> None:
        for team_id in list(competition.entrants.keys()):
            self._revalidate_one_entrant(competition=competition, team_id=team_id)

    def _revalidate_one_entrant(self, competition: Competition, team_id: str) -> None:
        compatibility = self._team_workspace.evaluate_compatibility(
            team_id=team_id,
            game_id=competition.game_id,
            version_id=competition.game_version_id,
        )
        if compatibility.compatible:
            competition.set_ready(team_id=team_id, ready=True, blocker_reason=None)
            return
        reason = "Не заполнены обязательные слоты: " + ", ".join(compatibility.missing_required_slots)
        competition.set_ready(team_id=team_id, ready=False, blocker_reason=reason)

    def list_competition_runs(self, competition_id: str) -> list[dict[str, object]]:
        competition = self.get_competition(competition_id)
        runs = self._execution.list_runs(
            lobby_id=competition.competition_id,
            run_kind=RunKind.COMPETITION_MATCH,
        )
        return [
            {
                "run_id": run.run_id,
                "team_id": run.team_id,
                "status": run.status.value,
                "error_message": run.error_message,
            }
            for run in runs
        ]

    def _seed_team_ids(self, competition: Competition) -> list[str]:
        ready = [
            entrant
            for entrant in competition.entrants.values()
            if entrant.ready and not entrant.banned
        ]
        ready.sort(key=lambda entrant: (entrant.registered_at, entrant.team_id))
        return [entrant.team_id for entrant in ready]

    def _schedule_current_round(self, competition: Competition, requested_by: str) -> list[str]:
        current_round = competition.get_current_round()
        if current_round is None:
            return []
        run_ids: list[str] = []
        for match in current_round.matches:
            if match.status is not CompetitionMatchStatus.PENDING:
                continue
            for team_id in match.team_ids:
                run = self._execution.create_run(
                    CreateRunInput(
                        team_id=team_id,
                        game_id=competition.game_id,
                        requested_by=requested_by,
                        run_kind=RunKind.COMPETITION_MATCH,
                        lobby_id=competition.competition_id,
                        version_id=competition.game_version_id,
                    )
                )
                queued = self._execution.queue_run(run.run_id)
                run_ids.append(queued.run_id)
                competition.mark_match_scheduled(
                    round_index=current_round.round_index,
                    match_id=match.match_id,
                    team_id=team_id,
                    run_id=queued.run_id,
                )
        return run_ids

    def _require_terminal_match_runs(self, match: CompetitionMatch, runs_by_id: dict[str, Run]) -> dict[str, Run]:
        terminal_runs: dict[str, Run] = {}
        for team_id in match.team_ids:
            run_id = match.run_ids_by_team.get(team_id)
            if not run_id:
                raise InvariantViolationError(f"Для команды {team_id} не найден competition-run в матче")
            run = runs_by_id.get(run_id)
            if run is None:
                raise InvariantViolationError(f"competition-run {run_id} не найден")
            if run.status not in _TERMINAL_STATUSES:
                raise InvariantViolationError(
                    f"Нельзя продвинуть раунд: run {run_id} для команды {team_id} не завершен"
                )
            terminal_runs[team_id] = run
        return terminal_runs

    def _build_match_outcome(
        self,
        competition: Competition,
        match: CompetitionMatch,
        runs: dict[str, Run],
    ) -> _MatchOutcome:
        scored: list[tuple[str, int, float]] = []
        provided_placements: dict[str, int] = {}
        provided_scores: dict[str, float] = {}

        for team_id in match.team_ids:
            run = runs[team_id]
            placement, score = self._extract_team_metrics(run=run, team_id=team_id)
            provided_placements[team_id] = placement
            provided_scores[team_id] = score
            scored.append((team_id, placement, score))

        scored.sort(key=lambda item: (item[1], -item[2], item[0]))
        placements_by_team: dict[str, int] = {}
        for index, (team_id, placement, _) in enumerate(scored, start=1):
            if placement >= 1_000_000_000:
                placements_by_team[team_id] = index
            else:
                placements_by_team[team_id] = placement

        top_k = min(competition.advancement_top_k, len(scored))
        advanced = [team_id for team_id, _, _ in scored[:top_k]]

        if len(scored) > top_k:
            boundary = scored[top_k - 1]
            next_item = scored[top_k]
            boundary_signature = (boundary[1], boundary[2])
            next_signature = (next_item[1], next_item[2])
            if boundary_signature == next_signature:
                if competition.tie_break_policy is TieBreakPolicy.SHARED_ADVANCEMENT:
                    index = top_k
                    while index < len(scored):
                        candidate = scored[index]
                        if (candidate[1], candidate[2]) != boundary_signature:
                            break
                        advanced.append(candidate[0])
                        index += 1
                else:
                    return _MatchOutcome(
                        scores_by_team=provided_scores,
                        placements_by_team=placements_by_team,
                        advanced_team_ids=[],
                        requires_manual_tiebreak=True,
                        tiebreak_reason=(
                            "Граница top-k имеет одинаковые score/placement, "
                            f"tie_break_policy={competition.tie_break_policy.value}"
                        ),
                    )

        return _MatchOutcome(
            scores_by_team=provided_scores,
            placements_by_team=placements_by_team,
            advanced_team_ids=advanced,
        )

    @staticmethod
    def _extract_team_metrics(run: Run, team_id: str) -> tuple[int, float]:
        payload = run.result_payload if isinstance(run.result_payload, dict) else {}

        placement = 1_000_000_000
        placements = payload.get("placements")
        if isinstance(placements, dict):
            raw_place = placements.get(team_id)
            if isinstance(raw_place, int) and raw_place > 0:
                placement = raw_place
            elif len(placements) == 1:
                only_value = next(iter(placements.values()))
                if isinstance(only_value, int) and only_value > 0:
                    placement = only_value

        score = float("-inf")
        scores = payload.get("scores")
        if isinstance(scores, dict):
            raw_score = scores.get(team_id)
            if isinstance(raw_score, (int, float)):
                score = float(raw_score)
            elif len(scores) == 1:
                only_value = next(iter(scores.values()))
                if isinstance(only_value, (int, float)):
                    score = float(only_value)

        metrics = payload.get("metrics")
        if score == float("-inf") and isinstance(metrics, dict):
            metric_score = metrics.get("score")
            if isinstance(metric_score, (int, float)):
                score = float(metric_score)

        if score == float("-inf"):
            score = -1_000_000_000.0

        return placement, score

    def list_running_competitions(self) -> tuple[str, ...]:
        return tuple(
            competition.competition_id
            for competition in self._repository.list()
            if competition.status is CompetitionStatus.RUNNING
        )

    def has_running_competition_for_game(self, game_id: str) -> bool:
        return any(
            competition.game_id == game_id and competition.status is CompetitionStatus.RUNNING
            for competition in self._repository.list()
        )
