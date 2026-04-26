from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from enum import StrEnum

from shared.kernel import InvariantViolationError, NotFoundError, new_id, utc_now


class CompetitionFormat(StrEnum):
    SINGLE_ELIMINATION = "single_elimination"
    ROUND_ROBIN = "round_robin"
    SWISS = "swiss"


class TieBreakPolicy(StrEnum):
    MANUAL = "manual"
    SHARED_ADVANCEMENT = "shared_advancement"
    TIEBREAK_MATCH = "tiebreak_match"
    GAME_DEFINED = "game_defined"


class CompetitionCodePolicy(StrEnum):
    LOCKED_ON_REGISTRATION = "locked_on_registration"
    LOCKED_ON_START = "locked_on_start"
    ALLOWED_BETWEEN_MATCHES = "allowed_between_matches"


class CompetitionStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FINISHED = "finished"


class CompetitionRoundStatus(StrEnum):
    RUNNING = "running"
    FINISHED = "finished"


class CompetitionMatchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    AWAITING_TIEBREAK = "awaiting_tiebreak"
    AUTO_ADVANCED = "auto_advanced"


@dataclass(slots=True)
class CompetitionEntrant:
    team_id: str
    ready: bool = False
    banned: bool = False
    blocker_reason: str | None = None
    registered_at: object = field(default_factory=utc_now)


@dataclass(slots=True)
class CompetitionMatch:
    match_id: str
    round_index: int
    team_ids: tuple[str, ...]
    status: CompetitionMatchStatus
    run_ids_by_team: dict[str, str] = field(default_factory=dict)
    scores_by_team: dict[str, float] = field(default_factory=dict)
    placements_by_team: dict[str, int] = field(default_factory=dict)
    advanced_team_ids: tuple[str, ...] = ()
    tie_break_reason: str | None = None


@dataclass(slots=True)
class CompetitionRound:
    round_index: int
    status: CompetitionRoundStatus
    matches: list[CompetitionMatch] = field(default_factory=list)


@dataclass(slots=True)
class Competition:
    competition_id: str
    game_id: str
    game_version_id: str
    title: str
    format: CompetitionFormat
    tie_break_policy: TieBreakPolicy
    code_policy: CompetitionCodePolicy
    advancement_top_k: int
    min_match_size: int
    match_size: int
    lobby_id: str | None = None
    status: CompetitionStatus = CompetitionStatus.DRAFT
    entrants: dict[str, CompetitionEntrant] = field(default_factory=dict)
    rounds: list[CompetitionRound] = field(default_factory=list)
    current_round_index: int | None = None
    winner_team_ids: tuple[str, ...] = ()
    pending_reason: str | None = None
    last_scheduled_run_ids: tuple[str, ...] = ()
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)

    @staticmethod
    def create(
        game_id: str,
        game_version_id: str,
        title: str,
        format: CompetitionFormat,
        tie_break_policy: TieBreakPolicy,
        code_policy: CompetitionCodePolicy,
        advancement_top_k: int,
        min_match_size: int,
        match_size: int,
        lobby_id: str | None = None,
    ) -> "Competition":
        if min_match_size < 2:
            raise InvariantViolationError("min_match_size должен быть >= 2")
        if match_size < min_match_size:
            raise InvariantViolationError("match_size должен быть >= min_match_size")
        if advancement_top_k < 1:
            raise InvariantViolationError("advancement_top_k должен быть >= 1")
        if advancement_top_k > match_size:
            raise InvariantViolationError("advancement_top_k не может быть больше match_size")

        return Competition(
            competition_id=new_id("comp"),
            game_id=game_id,
            game_version_id=game_version_id,
            title=title,
            format=format,
            tie_break_policy=tie_break_policy,
            code_policy=code_policy,
            advancement_top_k=advancement_top_k,
            min_match_size=min_match_size,
            match_size=match_size,
            lobby_id=lobby_id,
        )

    def register_team(self, team_id: str) -> None:
        if self.status is not CompetitionStatus.DRAFT:
            raise InvariantViolationError("Регистрация доступна только в статусе draft")
        if team_id in self.entrants:
            raise InvariantViolationError("Команда уже зарегистрирована в соревновании")
        self.entrants[team_id] = CompetitionEntrant(team_id=team_id)
        self.updated_at = utc_now()

    def unregister_team(self, team_id: str) -> None:
        if self.status is not CompetitionStatus.DRAFT:
            raise InvariantViolationError("Удаление entrant доступно только в статусе draft")
        if team_id not in self.entrants:
            raise NotFoundError("Команда не зарегистрирована в соревновании")
        self.entrants.pop(team_id)
        self.updated_at = utc_now()

    def set_ready(self, team_id: str, ready: bool, blocker_reason: str | None = None) -> None:
        entrant = self.entrants.get(team_id)
        if entrant is None:
            raise NotFoundError("Команда не зарегистрирована в соревновании")
        if entrant.banned and ready:
            raise InvariantViolationError("Забаненная команда не может стать ready")
        entrant.ready = ready
        entrant.blocker_reason = blocker_reason
        self.updated_at = utc_now()

    def set_ban(self, team_id: str, banned: bool, blocker_reason: str | None = None) -> None:
        entrant = self.entrants.get(team_id)
        if entrant is None:
            raise NotFoundError("Команда не зарегистрирована в соревновании")
        entrant.banned = banned
        if banned:
            entrant.ready = False
            entrant.blocker_reason = blocker_reason or "Команда заблокирована модератором"
        self.updated_at = utc_now()

    def start(self) -> None:
        if self.status not in {CompetitionStatus.DRAFT, CompetitionStatus.PAUSED}:
            raise InvariantViolationError("Соревнование можно стартовать только из draft/paused")
        if len(self.eligible_team_ids()) < self.min_match_size:
            raise InvariantViolationError(
                f"Для старта требуется минимум {self.min_match_size} ready-команды"
            )
        self.status = CompetitionStatus.RUNNING
        self.pending_reason = None
        self.updated_at = utc_now()

    def pause(self) -> None:
        if self.status is not CompetitionStatus.RUNNING:
            raise InvariantViolationError("Пауза доступна только в running")
        self.status = CompetitionStatus.PAUSED
        self.updated_at = utc_now()

    def finish(self) -> None:
        if self.status is not CompetitionStatus.COMPLETED:
            raise InvariantViolationError("Завершение доступно только после определения победителя")
        self.status = CompetitionStatus.FINISHED
        self.updated_at = utc_now()

    def complete_with_winners(self, winner_team_ids: list[str]) -> None:
        if self.status is not CompetitionStatus.RUNNING:
            raise InvariantViolationError("Определение победителя доступно только в running")
        self.status = CompetitionStatus.COMPLETED
        self.winner_team_ids = tuple(winner_team_ids)
        self.current_round_index = None
        self.updated_at = utc_now()

    def set_pending_reason(self, reason: str | None) -> None:
        self.pending_reason = reason
        self.updated_at = utc_now()

    def set_last_scheduled_runs(self, run_ids: list[str]) -> None:
        self.last_scheduled_run_ids = tuple(run_ids)
        self.updated_at = utc_now()

    def get_current_round(self) -> CompetitionRound | None:
        if self.current_round_index is None:
            return None
        for round_item in self.rounds:
            if round_item.round_index == self.current_round_index:
                return round_item
        return None

    def seed_first_round(self, team_ids: list[str]) -> CompetitionRound:
        if self.rounds:
            raise InvariantViolationError("Первый раунд уже создан")
        round_item = self._build_round(round_index=1, team_ids=team_ids)
        self.rounds.append(round_item)
        self.current_round_index = 1
        self.updated_at = utc_now()
        return round_item

    def create_next_round(self, team_ids: list[str]) -> CompetitionRound:
        if not self.rounds:
            raise InvariantViolationError("Нельзя создать следующий раунд без первого раунда")
        next_round_index = (self.current_round_index or 0) + 1
        round_item = self._build_round(round_index=next_round_index, team_ids=team_ids)
        self.rounds.append(round_item)
        self.current_round_index = next_round_index
        self.updated_at = utc_now()
        return round_item

    def mark_round_finished(self, round_index: int) -> None:
        round_item = self._require_round(round_index)
        round_item.status = CompetitionRoundStatus.FINISHED
        self.updated_at = utc_now()

    def mark_match_scheduled(self, round_index: int, match_id: str, team_id: str, run_id: str) -> None:
        match = self._require_match(round_index=round_index, match_id=match_id)
        if team_id not in match.team_ids:
            raise InvariantViolationError("Команда не входит в состав матча")
        match.run_ids_by_team[team_id] = run_id
        if match.status is CompetitionMatchStatus.PENDING:
            match.status = CompetitionMatchStatus.RUNNING
        self.updated_at = utc_now()

    def mark_match_finished(
        self,
        round_index: int,
        match_id: str,
        scores_by_team: dict[str, float],
        placements_by_team: dict[str, int],
        advanced_team_ids: list[str],
    ) -> None:
        match = self._require_match(round_index=round_index, match_id=match_id)
        match.scores_by_team = dict(scores_by_team)
        match.placements_by_team = dict(placements_by_team)
        match.advanced_team_ids = tuple(advanced_team_ids)
        match.status = CompetitionMatchStatus.FINISHED
        match.tie_break_reason = None
        self.updated_at = utc_now()

    def mark_match_awaiting_tiebreak(self, round_index: int, match_id: str, reason: str) -> None:
        match = self._require_match(round_index=round_index, match_id=match_id)
        match.status = CompetitionMatchStatus.AWAITING_TIEBREAK
        match.tie_break_reason = reason
        self.updated_at = utc_now()

    def resolve_match_tiebreak(
        self,
        round_index: int,
        match_id: str,
        advanced_team_ids: list[str],
    ) -> None:
        match = self._require_match(round_index=round_index, match_id=match_id)
        if match.status is not CompetitionMatchStatus.AWAITING_TIEBREAK:
            raise InvariantViolationError("Ручное решение доступно только для матча в awaiting_tiebreak")
        invalid = [team_id for team_id in advanced_team_ids if team_id not in match.team_ids]
        if invalid:
            raise InvariantViolationError("Решение содержит команды, отсутствующие в матче")
        if not advanced_team_ids:
            raise InvariantViolationError("В решении должна быть хотя бы одна команда")
        match.advanced_team_ids = tuple(advanced_team_ids)
        match.status = CompetitionMatchStatus.FINISHED
        match.tie_break_reason = None
        self.updated_at = utc_now()

    def eligible_team_ids(self) -> tuple[str, ...]:
        return tuple(
            entrant.team_id
            for entrant in self.entrants.values()
            if entrant.ready and not entrant.banned
        )

    def _build_round(self, round_index: int, team_ids: list[str]) -> CompetitionRound:
        if len(team_ids) < 1:
            raise InvariantViolationError("Раунд нельзя построить без участников")

        team_ids = _order_competition_round_seed(
            competition_id=self.competition_id,
            round_index=round_index,
            team_ids=team_ids,
            min_match_size=self.min_match_size,
            max_match_size=self.match_size,
            previous_auto_advances=self._auto_advance_counts(),
        )
        matches: list[CompetitionMatch] = []
        for chunk in _partition_competition_matches(
            team_ids=team_ids,
            min_match_size=self.min_match_size,
            max_match_size=self.match_size,
        ):
            match_id = new_id("cmp_match")
            if len(chunk) == 1:
                matches.append(
                    CompetitionMatch(
                        match_id=match_id,
                        round_index=round_index,
                        team_ids=chunk,
                        status=CompetitionMatchStatus.AUTO_ADVANCED,
                        advanced_team_ids=chunk,
                        placements_by_team={chunk[0]: 1},
                        scores_by_team={chunk[0]: 0.0},
                    )
                )
                continue
            matches.append(
                CompetitionMatch(
                    match_id=match_id,
                    round_index=round_index,
                    team_ids=chunk,
                    status=CompetitionMatchStatus.PENDING,
                )
            )

        return CompetitionRound(
            round_index=round_index,
            status=CompetitionRoundStatus.RUNNING,
            matches=matches,
        )

    def _require_round(self, round_index: int) -> CompetitionRound:
        for round_item in self.rounds:
            if round_item.round_index == round_index:
                return round_item
        raise NotFoundError(f"Раунд {round_index} не найден")

    def _require_match(self, round_index: int, match_id: str) -> CompetitionMatch:
        round_item = self._require_round(round_index=round_index)
        for match in round_item.matches:
            if match.match_id == match_id:
                return match
        raise NotFoundError(f"Матч {match_id} не найден в раунде {round_index}")

    def _auto_advance_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for round_item in self.rounds:
            for match in round_item.matches:
                if match.status is not CompetitionMatchStatus.AUTO_ADVANCED:
                    continue
                for team_id in match.advanced_team_ids:
                    counts[team_id] = counts.get(team_id, 0) + 1
        return counts


def _order_competition_round_seed(
    *,
    competition_id: str,
    round_index: int,
    team_ids: list[str],
    min_match_size: int,
    max_match_size: int,
    previous_auto_advances: dict[str, int],
) -> list[str]:
    if len(team_ids) <= 1:
        return list(team_ids)

    rng = random.Random(_stable_round_seed(competition_id=competition_id, round_index=round_index))
    shuffled = list(team_ids)
    rng.shuffle(shuffled)

    playable_count = _competition_playable_count(
        total=len(shuffled),
        min_match_size=min_match_size,
        max_match_size=max_match_size,
    )
    auto_advance_count = len(shuffled) - playable_count
    if auto_advance_count <= 0:
        return shuffled

    tie_breakers = {team_id: rng.random() for team_id in shuffled}
    auto_advanced = set(
        sorted(
            shuffled,
            key=lambda team_id: (previous_auto_advances.get(team_id, 0), tie_breakers[team_id], team_id),
        )[:auto_advance_count]
    )
    playable = [team_id for team_id in shuffled if team_id not in auto_advanced]
    byes = [team_id for team_id in shuffled if team_id in auto_advanced]
    return playable + byes


def _stable_round_seed(*, competition_id: str, round_index: int) -> int:
    digest = hashlib.sha256(f"{competition_id}:{round_index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _competition_playable_count(*, total: int, min_match_size: int, max_match_size: int) -> int:
    if total <= 1:
        return total
    for playable_count in range(total, min_match_size - 1, -1):
        min_group_count = (playable_count + max_match_size - 1) // max_match_size
        max_group_count = playable_count // min_match_size
        for group_count in range(min_group_count, max_group_count + 1):
            if group_count * min_match_size <= playable_count <= group_count * max_match_size:
                return playable_count
    return 0


def _partition_competition_matches(
    *,
    team_ids: list[str],
    min_match_size: int,
    max_match_size: int,
) -> list[tuple[str, ...]]:
    total = len(team_ids)
    if total <= 1:
        return [tuple(team_ids)] if team_ids else []

    playable_count = _competition_playable_count(
        total=total,
        min_match_size=min_match_size,
        max_match_size=max_match_size,
    )
    if playable_count >= min_match_size:
        min_group_count = (playable_count + max_match_size - 1) // max_match_size
        max_group_count = playable_count // min_match_size
        for group_count in range(min_group_count, max_group_count + 1):
            if group_count * min_match_size <= playable_count <= group_count * max_match_size:
                sizes = _distribute_competition_match_sizes(
                    total=playable_count,
                    group_count=group_count,
                    min_match_size=min_match_size,
                    max_match_size=max_match_size,
                )
                chunks: list[tuple[str, ...]] = []
                cursor = 0
                for size in sizes:
                    chunks.append(tuple(team_ids[cursor : cursor + size]))
                    cursor += size
                chunks.extend((team_id,) for team_id in team_ids[cursor:])
                return chunks

    return [(team_id,) for team_id in team_ids]


def _distribute_competition_match_sizes(
    *,
    total: int,
    group_count: int,
    min_match_size: int,
    max_match_size: int,
) -> list[int]:
    sizes = [min_match_size for _ in range(group_count)]
    remaining = total - group_count * min_match_size
    index = 0
    while remaining > 0:
        capacity = max_match_size - sizes[index]
        delta = min(capacity, remaining)
        sizes[index] += delta
        remaining -= delta
        index = (index + 1) % group_count
    return sizes
