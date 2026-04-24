from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import re

from competition.application.service import CompetitionService
from execution.application.service import ExecutionService
from execution.domain.model import Run, RunKind
from shared.kernel import InvariantViolationError
from team_workspace.application.service import TeamWorkspaceService

from antiplagiarism.domain.model import SimilarityWarning

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|==|!=|<=|>=|:=|[+\-*/%<>{}\[\]().,:=]")
_COMMENT_RE = re.compile(r"#.*")
_STRING_RE = re.compile(r"('''.*?'''|\"\"\".*?\"\"\"|'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\")", re.S)
_ALGORITHM = "jaccard_shingle_5_v1"


@dataclass(frozen=True, slots=True)
class AnalyzeCompetitionInput:
    competition_id: str
    similarity_threshold: float
    min_token_count: int


class AntiplagiarismService:
    def __init__(
        self,
        competition: CompetitionService,
        execution: ExecutionService,
        team_workspace: TeamWorkspaceService,
    ) -> None:
        self._competition = competition
        self._execution = execution
        self._team_workspace = team_workspace

    def analyze_competition(self, data: AnalyzeCompetitionInput) -> list[SimilarityWarning]:
        self._validate_input(data)
        competition = self._competition.get_competition(data.competition_id)
        runs = self._execution.list_runs(
            lobby_id=competition.competition_id,
            run_kind=RunKind.COMPETITION_MATCH,
        )

        latest_run_by_team = self._latest_run_by_team(runs=runs, allowed_team_ids=set(competition.entrants.keys()))
        warnings: list[SimilarityWarning] = []

        for team_a_id, team_b_id in combinations(sorted(latest_run_by_team.keys()), 2):
            run_a = latest_run_by_team[team_a_id]
            run_b = latest_run_by_team[team_b_id]
            if run_a.snapshot_id is None or run_b.snapshot_id is None:
                continue

            snapshot_a = self._team_workspace.get_snapshot(run_a.snapshot_id)
            snapshot_b = self._team_workspace.get_snapshot(run_b.snapshot_id)
            common_slots = sorted(set(snapshot_a.codes_by_slot.keys()) & set(snapshot_b.codes_by_slot.keys()))

            for slot_key in common_slots:
                similarity = _code_similarity(
                    code_left=snapshot_a.codes_by_slot[slot_key],
                    code_right=snapshot_b.codes_by_slot[slot_key],
                    min_token_count=data.min_token_count,
                )
                if similarity < data.similarity_threshold:
                    continue
                warnings.append(
                    SimilarityWarning.create(
                        competition_id=competition.competition_id,
                        team_a_id=team_a_id,
                        team_b_id=team_b_id,
                        slot_key=slot_key,
                        similarity=round(similarity, 4),
                        algorithm=_ALGORITHM,
                        run_a_id=run_a.run_id,
                        run_b_id=run_b.run_id,
                    )
                )

        warnings.sort(key=lambda item: (-item.similarity, item.team_a_id, item.team_b_id, item.slot_key))
        return warnings

    @staticmethod
    def _latest_run_by_team(runs: list[Run], allowed_team_ids: set[str]) -> dict[str, Run]:
        latest: dict[str, Run] = {}
        for run in runs:
            if run.team_id not in allowed_team_ids:
                continue
            if run.snapshot_id is None:
                continue
            if run.team_id in latest:
                continue
            latest[run.team_id] = run
        return latest

    @staticmethod
    def _validate_input(data: AnalyzeCompetitionInput) -> None:
        if not (0.0 <= data.similarity_threshold <= 1.0):
            raise InvariantViolationError("similarity_threshold должен быть в диапазоне [0, 1]")
        if data.min_token_count < 1:
            raise InvariantViolationError("min_token_count должен быть >= 1")


def _code_similarity(code_left: str, code_right: str, min_token_count: int) -> float:
    tokens_left = _tokenize(code_left)
    tokens_right = _tokenize(code_right)

    if len(tokens_left) < min_token_count or len(tokens_right) < min_token_count:
        return 0.0

    shingles_left = _build_shingles(tokens_left, size=5)
    shingles_right = _build_shingles(tokens_right, size=5)
    if not shingles_left and not shingles_right:
        return 1.0

    intersection = len(shingles_left & shingles_right)
    union = len(shingles_left | shingles_right)
    if union == 0:
        return 0.0
    return intersection / union


def _tokenize(code: str) -> tuple[str, ...]:
    without_strings = _STRING_RE.sub(" STR ", code)
    without_comments = _COMMENT_RE.sub("", without_strings)
    compact = without_comments.lower()
    return tuple(_TOKEN_RE.findall(compact))


def _build_shingles(tokens: tuple[str, ...], size: int) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return {tokens} if tokens else set()
    return {tuple(tokens[index : index + size]) for index in range(0, len(tokens) - size + 1)}
