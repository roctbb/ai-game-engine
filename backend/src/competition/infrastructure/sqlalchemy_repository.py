from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from competition.domain.model import (
    Competition,
    CompetitionCodePolicy,
    CompetitionEntrant,
    CompetitionFormat,
    CompetitionMatch,
    CompetitionMatchStatus,
    CompetitionRound,
    CompetitionRoundStatus,
    CompetitionStatus,
    TieBreakPolicy,
)
from competition.infrastructure.sqlalchemy_models import CompetitionOrm


class SqlAlchemyCompetitionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, competition: Competition) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_competition_to_orm(competition))

    def get(self, competition_id: str) -> Competition | None:
        with self._session_factory() as session:
            row = session.get(CompetitionOrm, competition_id)
            return None if row is None else _map_competition_from_orm(row)

    def list(self) -> list[Competition]:
        with self._session_factory() as session:
            rows = session.scalars(select(CompetitionOrm).order_by(desc(CompetitionOrm.created_at))).all()
            return [_map_competition_from_orm(row) for row in rows]

    def list_by_lobby(self, lobby_id: str) -> list[Competition]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(CompetitionOrm)
                .where(CompetitionOrm.lobby_id == lobby_id)
                .order_by(desc(CompetitionOrm.created_at))
            ).all()
            return [_map_competition_from_orm(row) for row in rows]


def _map_competition_to_orm(competition: Competition) -> CompetitionOrm:
    entrants_json: dict[str, dict[str, object]] = {}
    for team_id, entrant in competition.entrants.items():
        entrants_json[team_id] = {
            "ready": entrant.ready,
            "banned": entrant.banned,
            "blocker_reason": entrant.blocker_reason,
            "registered_at": entrant.registered_at.isoformat(),
        }

    rounds_json: list[dict[str, object]] = []
    for round_item in competition.rounds:
        rounds_json.append(
            {
                "round_index": round_item.round_index,
                "status": round_item.status.value,
                "matches": [
                    {
                        "match_id": match.match_id,
                        "round_index": match.round_index,
                        "team_ids": list(match.team_ids),
                        "status": match.status.value,
                        "run_ids_by_team": dict(match.run_ids_by_team),
                        "scores_by_team": dict(match.scores_by_team),
                        "placements_by_team": dict(match.placements_by_team),
                        "advanced_team_ids": list(match.advanced_team_ids),
                        "tie_break_reason": match.tie_break_reason,
                    }
                    for match in round_item.matches
                ],
            }
        )

    return CompetitionOrm(
        competition_id=competition.competition_id,
        game_id=competition.game_id,
        game_version_id=competition.game_version_id,
        lobby_id=competition.lobby_id,
        title=competition.title,
        format=competition.format.value,
        tie_break_policy=competition.tie_break_policy.value,
        code_policy=competition.code_policy.value,
        advancement_top_k=competition.advancement_top_k,
        min_match_size=competition.min_match_size,
        match_size=competition.match_size,
        status=competition.status.value,
        entrants_json=entrants_json,
        rounds_json=rounds_json,
        current_round_index=competition.current_round_index,
        winner_team_ids_json=list(competition.winner_team_ids),
        pending_reason=competition.pending_reason,
        last_scheduled_run_ids_json=list(competition.last_scheduled_run_ids),
        created_at=competition.created_at,
        updated_at=competition.updated_at,
    )


def _map_competition_from_orm(row: CompetitionOrm) -> Competition:
    entrants: dict[str, CompetitionEntrant] = {}
    for team_id, raw in (row.entrants_json or {}).items():
        registered_at_raw = raw.get("registered_at")
        registered_at = (
            datetime.fromisoformat(str(registered_at_raw))
            if isinstance(registered_at_raw, str)
            else datetime.now()
        )
        entrants[team_id] = CompetitionEntrant(
            team_id=team_id,
            ready=bool(raw.get("ready", False)),
            banned=bool(raw.get("banned", False)),
            blocker_reason=(str(raw["blocker_reason"]) if raw.get("blocker_reason") else None),
            registered_at=registered_at,
        )

    rounds: list[CompetitionRound] = []
    for raw_round in row.rounds_json or []:
        matches: list[CompetitionMatch] = []
        for raw_match in raw_round.get("matches", []):
            team_ids_raw = raw_match.get("team_ids", [])
            if not isinstance(team_ids_raw, list):
                team_ids_raw = []
            advanced_raw = raw_match.get("advanced_team_ids", [])
            if not isinstance(advanced_raw, list):
                advanced_raw = []
            run_ids_raw = raw_match.get("run_ids_by_team", {})
            scores_raw = raw_match.get("scores_by_team", {})
            placements_raw = raw_match.get("placements_by_team", {})

            run_ids_by_team: dict[str, str] = {}
            if isinstance(run_ids_raw, dict):
                for team_id, run_id in run_ids_raw.items():
                    if isinstance(team_id, str) and isinstance(run_id, str):
                        run_ids_by_team[team_id] = run_id

            scores_by_team: dict[str, float] = {}
            if isinstance(scores_raw, dict):
                for team_id, score in scores_raw.items():
                    if isinstance(team_id, str) and isinstance(score, (int, float)):
                        scores_by_team[team_id] = float(score)

            placements_by_team: dict[str, int] = {}
            if isinstance(placements_raw, dict):
                for team_id, place in placements_raw.items():
                    if isinstance(team_id, str) and isinstance(place, int):
                        placements_by_team[team_id] = place

            status_raw = str(raw_match.get("status", CompetitionMatchStatus.PENDING.value))
            try:
                match_status = CompetitionMatchStatus(status_raw)
            except ValueError:
                match_status = CompetitionMatchStatus.PENDING

            matches.append(
                CompetitionMatch(
                    match_id=str(raw_match.get("match_id", "")),
                    round_index=int(raw_match.get("round_index", raw_round.get("round_index", 1))),
                    team_ids=tuple(str(team_id) for team_id in team_ids_raw),
                    status=match_status,
                    run_ids_by_team=run_ids_by_team,
                    scores_by_team=scores_by_team,
                    placements_by_team=placements_by_team,
                    advanced_team_ids=tuple(str(team_id) for team_id in advanced_raw),
                    tie_break_reason=(
                        str(raw_match.get("tie_break_reason"))
                        if raw_match.get("tie_break_reason")
                        else None
                    ),
                )
            )

        round_status_raw = str(raw_round.get("status", CompetitionRoundStatus.RUNNING.value))
        try:
            round_status = CompetitionRoundStatus(round_status_raw)
        except ValueError:
            round_status = CompetitionRoundStatus.RUNNING
        rounds.append(
            CompetitionRound(
                round_index=int(raw_round.get("round_index", 1)),
                status=round_status,
                matches=matches,
            )
        )

    code_policy_raw = str(getattr(row, "code_policy", CompetitionCodePolicy.LOCKED_ON_START.value))
    try:
        code_policy = CompetitionCodePolicy(code_policy_raw)
    except ValueError:
        code_policy = CompetitionCodePolicy.LOCKED_ON_START

    return Competition(
        competition_id=row.competition_id,
        game_id=row.game_id,
        game_version_id=row.game_version_id,
        lobby_id=getattr(row, "lobby_id", None),
        title=row.title,
        format=CompetitionFormat(row.format),
        tie_break_policy=TieBreakPolicy(row.tie_break_policy),
        code_policy=code_policy,
        advancement_top_k=row.advancement_top_k,
        min_match_size=getattr(row, "min_match_size", 2) or 2,
        match_size=row.match_size,
        status=CompetitionStatus(row.status),
        entrants=entrants,
        rounds=rounds,
        current_round_index=row.current_round_index,
        winner_team_ids=tuple(str(item) for item in (row.winner_team_ids_json or [])),
        pending_reason=row.pending_reason,
        last_scheduled_run_ids=tuple(str(item) for item in (row.last_scheduled_run_ids_json or [])),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
