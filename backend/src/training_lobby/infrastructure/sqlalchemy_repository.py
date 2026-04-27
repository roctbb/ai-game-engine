from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from training_lobby.domain.model import Lobby, LobbyAccess, LobbyKind, LobbyStatus, LobbyTeamState
from training_lobby.infrastructure.sqlalchemy_models import LobbyOrm


class SqlAlchemyLobbyRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, lobby: Lobby) -> None:
        with self._session_factory.begin() as session:
            session.merge(_map_lobby_to_orm(lobby))

    def get(self, lobby_id: str) -> Lobby | None:
        with self._session_factory() as session:
            row = session.get(LobbyOrm, lobby_id)
            return None if row is None else _map_lobby_from_orm(row)

    def list(self) -> list[Lobby]:
        with self._session_factory() as session:
            rows = session.scalars(select(LobbyOrm).order_by(desc(LobbyOrm.created_at))).all()
            return [_map_lobby_from_orm(row) for row in rows]

    def delete(self, lobby_id: str) -> None:
        with self._session_factory.begin() as session:
            row = session.get(LobbyOrm, lobby_id)
            if row is not None:
                session.delete(row)


def _map_lobby_to_orm(lobby: Lobby) -> LobbyOrm:
    teams_json: dict[str, dict[str, object]] = {}
    for team_id, state in lobby.teams.items():
        teams_json[team_id] = {
            "ready": state.ready,
            "blocker_reason": state.blocker_reason,
        }

    return LobbyOrm(
        lobby_id=lobby.lobby_id,
        game_id=lobby.game_id,
        game_version_id=lobby.game_version_id,
        title=lobby.title,
        kind=lobby.kind.value,
        access=lobby.access.value,
        access_code=lobby.access_code,
        max_teams=lobby.max_teams,
        status=lobby.status.value,
        teams_json=teams_json,
        last_scheduled_run_ids_json=list(lobby.last_scheduled_run_ids),
        last_scheduled_match_groups_json=[list(group) for group in lobby.last_scheduled_match_groups],
        cumulative_stats_by_team_json={
            str(team_id): dict(stats)
            for team_id, stats in lobby.cumulative_stats_by_team.items()
        },
        created_at=lobby.created_at,
    )


def _map_lobby_from_orm(row: LobbyOrm) -> Lobby:
    teams: dict[str, LobbyTeamState] = {}
    for team_id, raw in (row.teams_json or {}).items():
        teams[team_id] = LobbyTeamState(
            team_id=team_id,
            ready=bool(raw.get("ready", False)),
            blocker_reason=(str(raw["blocker_reason"]) if raw.get("blocker_reason") else None),
        )

    raw_groups = row.last_scheduled_match_groups_json or []
    match_groups: list[tuple[str, ...]] = []
    for raw_group in raw_groups:
        if not isinstance(raw_group, list):
            continue
        group = tuple(str(item) for item in raw_group if item)
        if group:
            match_groups.append(group)

    return Lobby(
        lobby_id=row.lobby_id,
        game_id=row.game_id,
        game_version_id=row.game_version_id,
        title=row.title,
        kind=LobbyKind(row.kind),
        access=LobbyAccess(row.access),
        access_code=row.access_code,
        max_teams=row.max_teams,
        status=LobbyStatus(row.status),
        teams=teams,
        last_scheduled_run_ids=tuple(str(item) for item in (row.last_scheduled_run_ids_json or [])),
        last_scheduled_match_groups=tuple(match_groups),
        cumulative_stats_by_team=_normalize_cumulative_stats(row.cumulative_stats_by_team_json or {}),
        created_at=row.created_at,
    )


def _normalize_cumulative_stats(raw: dict[str, dict[str, object]]) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for team_id, stats in raw.items():
        if not isinstance(stats, dict):
            continue
        result[str(team_id)] = {
            "matches_total": int(stats.get("matches_total", 0) or 0),
            "wins": int(stats.get("wins", 0) or 0),
            "score_sum": float(stats.get("score_sum", 0.0) or 0.0),
            "score_count": int(stats.get("score_count", 0) or 0),
        }
    return result
