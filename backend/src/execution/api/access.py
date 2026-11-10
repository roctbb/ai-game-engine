from __future__ import annotations

from app.dependencies import ServiceContainer
from execution.domain.model import Run, RunKind
from identity.domain.model import AppSession, UserRole
from shared.kernel import ForbiddenError, NotFoundError
from training_lobby.domain.model import LobbyAccess

_PRIVATE_EVENTS = {"bot_print", "print", "stdout", "bot_stdout", "console", "bot_error",
                   "compile_error", "runtime_error", "debug_snapshot", "debug_limit", "bot_crash", "bot_timeout"}


def visible_result_payload(
    container: ServiceContainer, session: AppSession, run: Run, payload: dict[str, object],
) -> dict[str, object]:
    """Keep the public game replay while returning diagnostics only to their author."""
    if session.role is not UserRole.STUDENT or run.run_kind is RunKind.SINGLE_TASK:
        return payload
    own_teams = {team.team_id for team in container.team_workspace.list_teams_by_game_and_captain(
        game_id=run.game_id, captain_user_id=session.nickname,
    )}
    aliases = set(own_teams)
    match = container.execution.get_match_execution_for_run(run)
    ordered_teams = [container.execution.get_run(run_id).team_id for run_id in match.run_ids] if match else []
    metrics = payload.get("metrics")
    slots = metrics.get("active_slots") if isinstance(metrics, dict) else None
    if not isinstance(slots, list) and isinstance(metrics, dict) and isinstance(metrics.get("slot_scores"), dict):
        slots = list(metrics["slot_scores"])
    if isinstance(slots, list) and len(slots) == len(ordered_teams):
        aliases.update(str(slot) for slot, team_id in zip(slots, ordered_teams) if team_id in own_teams)
    # Connect-five predates team-scoped diagnostics and uses two fixed source slots.
    if ordered_teams and container.game_catalog.get_game(run.game_id).slug == "ttt_connect5_v1":
        if ordered_teams[0] in own_teams:
            aliases.update({"bot", "player", "1"})
        if len(ordered_teams) > 1 and ordered_teams[1] in own_teams:
            aliases.update({"_enemy_bot", "enemy", "-1"})
    for team_id in own_teams:
        aliases.update({f"{team_id}:driver", f"{team_id}:support"})
    players = metrics.get("players") if isinstance(metrics, dict) else None
    if isinstance(players, list):
        for player in players:
            if isinstance(player, dict) and player.get("team_id") in own_teams:
                aliases.update(str(player[key]) for key in ("id", "key", "role") if player.get(key) is not None)

    def owned(item: dict[str, object]) -> bool:
        actor = item.get("team_id") or item.get("role") or item.get("slot") or item.get("slot_key")
        return str(actor) in aliases

    def clean(value: object) -> object:
        if isinstance(value, list):
            return [clean(item) for item in value if not (
                isinstance(item, dict) and item.get("type") in _PRIVATE_EVENTS and not owned(item)
            )]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key in {"codes_by_slot", "source_code", "compile_error", "traceback"}:
                continue
            if key == "compile_errors" and isinstance(item, dict):
                result[key] = {role: message for role, message in item.items() if str(role) in aliases}
            elif key in {"prints", "logs", "stdout", "console"}:
                result[key] = [clean(line) for line in item if isinstance(line, dict) and owned(line)] if isinstance(item, list) else []
            else:
                result[key] = clean(item)
        return result

    result = clean(payload)
    assert isinstance(result, dict)
    return result


def ensure_can_view_run(container: ServiceContainer, session: AppSession, run: Run) -> None:
    if session.role in {UserRole.TEACHER, UserRole.ADMIN}:
        return
    if run.requested_by == session.nickname:
        return
    try:
        team = container.team_workspace.get_team(run.team_id)
        if team.captain_user_id == session.nickname:
            return
    except NotFoundError:
        pass

    if run.run_kind is RunKind.TRAINING_MATCH and run.lobby_id:
        try:
            if container.training_lobby.find_user_team_in_lobby(
                lobby_id=run.lobby_id,
                user_id=session.nickname,
            ):
                return
        except NotFoundError:
            pass

    if run.run_kind is RunKind.COMPETITION_MATCH and run.lobby_id:
        try:
            competition = container.competition.get_competition(run.lobby_id)
            if competition.lobby_id:
                lobby = container.training_lobby.get_lobby(competition.lobby_id)
                if lobby.access is LobbyAccess.PUBLIC:
                    return
            user_teams = container.team_workspace.list_teams_by_game_and_captain(
                game_id=run.game_id,
                captain_user_id=session.nickname,
            )
            if any(team.team_id in competition.entrants for team in user_teams):
                return
            if competition.lobby_id and container.training_lobby.find_user_team_in_lobby(
                lobby_id=competition.lobby_id,
                user_id=session.nickname,
            ):
                return
        except NotFoundError:
            pass

    raise ForbiddenError("Просматривать этот запуск может только участник, преподаватель или админ")
