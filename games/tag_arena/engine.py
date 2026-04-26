from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 13
_HEIGHT = 13
_MAX_TURNS = 110
_TEAM_SLOTS = ("amber", "teal")
_ROLES = ("runner", "hunter")
_STARTS = {
    "amber": {"runner": (1, 1), "hunter": (1, 11)},
    "teal": {"runner": (11, 11), "hunter": (11, 1)},
}
_RANDOM_WALLS = 18
_STARS_TOTAL = 10
_RESPAWN_FREEZE = 2
_DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    "stay": (0, 0),
}
_BORDER_WALLS = {
    *{(x, 0) for x in range(_WIDTH)},
    *{(x, _HEIGHT - 1) for x in range(_WIDTH)},
    *{(0, y) for y in range(_HEIGHT)},
    *{(_WIDTH - 1, y) for y in range(_HEIGHT)},
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    teams, role_code, role_team, role_name = _resolve_participants(ctx)
    bots = {
        (team, role): _build_fn(role_code.get((team, role), ""), f"{team}_{role}", events, print_context)
        for team in teams
        for role in _ROLES
    }
    game_map = _build_map(ctx, teams)
    walls = game_map["walls"]
    stars = game_map["stars"]
    assert isinstance(walls, set) and isinstance(stars, set)

    positions = {(team, role): _STARTS[team][role] for team in teams for role in _ROLES}
    collected = {team: 0 for team in teams}
    catches = {team: 0 for team in teams}
    invalid = {f"{team}_{role}": 0 for team in teams for role in _ROLES}
    frozen = {team: 0 for team in teams}
    turns = 0
    frames = [_frame(0, "running", teams, positions, walls, stars, collected, catches, invalid, frozen, role_team, role_name, [])]

    for turn in range(_MAX_TURNS):
        if not stars:
            break
        print_context["tick"] = turn
        intents: dict[tuple[str, str], tuple[int, int]] = {}
        for team in teams:
            for role in _ROLES:
                key = f"{team}_{role}"
                if role == "runner" and frozen[team] > 0:
                    frozen[team] -= 1
                    intents[(team, role)] = positions[(team, role)]
                    events.append({"type": "runner_frozen", "tick": turn, "team": team, "left": frozen[team]})
                    continue

                fn, _compile_error = bots[(team, role)]
                x, y = positions[(team, role)]
                board = _board(walls, stars, positions, teams, team, role)
                action = _safe_call(fn, x, y, board, role, team)
                if action not in _DELTAS:
                    invalid[key] += 1
                    action = "stay"
                    events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "slot": key})
                target = _move((x, y), str(action))
                if target in walls:
                    invalid[key] += 1
                    target = (x, y)
                    events.append({"type": "blocked_move", "message": "Ход заблокирован стеной.", "tick": turn, "slot": key})
                intents[(team, role)] = target

        positions = _resolve_collisions(teams, positions, intents, events, turn)
        caught_events = _apply_catches(teams, positions, frozen, catches, events, turn)
        for caught in caught_events:
            caught_team = str(caught["runner_team"])
            positions[(caught_team, "runner")] = _STARTS[caught_team]["runner"]

        for team in teams:
            runner_pos = positions[(team, "runner")]
            if frozen[team] == 0 and runner_pos in stars:
                stars.remove(runner_pos)
                collected[team] += 1
                events.append({"type": "star", "tick": turn + 1, "team": team, "count": collected[team]})

        turns = turn + 1
        frames.append(_frame(turns, "running", teams, positions, walls, stars, collected, catches, invalid, frozen, role_team, role_name, caught_events))

    compile_errors = {f"{team}_{role}": err for (team, role), (_fn, err) in bots.items() if err}
    slot_scores = {
        team: collected[team] * 120 + catches[team] * 180 + (_MAX_TURNS - turns) // 2 - sum(invalid[f"{team}_{role}"] for role in _ROLES) * 10
        for team in teams
    }
    scores = {role_team[team]: max(0, slot_scores[team]) for team in teams}
    placements = _placements(teams, role_team, slot_scores)
    winner_slot = max(teams, key=lambda team: (slot_scores[team], collected[team], catches[team]))
    metrics: dict[str, object] = {
        "turns": turns,
        "active_teams": teams,
        "winner_slot": winner_slot,
        "winner_slots": _winner_slots(teams, slot_scores),
        "is_tie": _is_tie(teams, slot_scores),
        "stars_collected": collected,
        "stars_total": _STARS_TOTAL,
        "stars_left": len(stars),
        "catches": catches,
        "runner_frozen": frozen,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid,
        "slot_scores": slot_scores,
    }
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})

    frames.append(_frame(len(frames), "finished", teams, positions, walls, stars, collected, catches, invalid, frozen, role_team, role_name, [], slot_scores))
    payload: dict[str, object] = {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "scores": scores}
    payload["placements"] = placements
    return payload


def _load_context() -> dict[str, Any]:
    raw = os.getenv("AGP_RUN_CONTEXT")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_participants(ctx: dict[str, Any]) -> tuple[list[str], dict[tuple[str, str], str], dict[str, str], dict[str, str]]:
    participants = ctx.get("participants")
    if isinstance(participants, list) and len(participants) >= 2:
        teams = list(_TEAM_SLOTS[:2])
        role_code: dict[tuple[str, str], str] = {}
        role_team: dict[str, str] = {}
        role_name: dict[str, str] = {}
        for index, team in enumerate(teams):
            participant = participants[index]
            codes = participant.get("codes_by_slot") if isinstance(participant, dict) else {}
            for role in _ROLES:
                code = codes.get(role, "") if isinstance(codes, dict) else ""
                role_code[(team, role)] = str(code) if code else ""
            team_id = str(participant.get("team_id", team)) if isinstance(participant, dict) else team
            role_team[team] = team_id
            name = participant.get("display_name") or participant.get("captain_user_id") if isinstance(participant, dict) else None
            role_name[team] = str(name) if name else team_id
        return teams, role_code, role_team, role_name

    codes = ctx.get("codes_by_slot")
    teams = list(_TEAM_SLOTS[:2])
    role_code = {}
    if isinstance(codes, dict):
        for team in teams:
            for role in _ROLES:
                role_code[(team, role)] = str(codes.get(role) or "")
    else:
        role_code = {(team, role): "" for team in teams for role in _ROLES}
    role_team = {"amber": str(ctx.get("team_id") or "team-amber"), "teal": "team-teal"}
    return teams, role_code, role_team, dict(role_team)


def _map_seed(context: dict[str, Any], fallback: str) -> str:
    participants = context.get("participants")
    if isinstance(participants, list) and len(participants) >= 2:
        run_ids = [str(p.get("run_id", "")) for p in participants if isinstance(p, dict) and p.get("run_id")]
        seed = min(run_ids) if run_ids else context.get("run_id", fallback)
    else:
        seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = fallback
    return seed


def _build_map(context: dict[str, Any], teams: list[str]) -> dict[str, object]:
    rng = random.Random(_map_seed(context, "tag_arena_offline"))
    starts = {_STARTS[team][role] for team in teams for role in _ROLES}
    candidates = [
        (x, y)
        for y in range(1, _HEIGHT - 1)
        for x in range(1, _WIDTH - 1)
        if (x, y) not in starts
    ]
    required = list(starts)
    for _attempt in range(600):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        reachable = _reachable_cells(required[0], walls)
        if not all(cell in reachable for cell in required):
            continue
        shared = sorted(reachable - starts)
        if len(shared) < _STARS_TOTAL + 8:
            continue
        rng.shuffle(shared)
        return {"walls": walls, "stars": set(shared[:_STARS_TOTAL])}
    walls = set(_BORDER_WALLS)
    shared = sorted(_reachable_cells(required[0], walls) - starts)
    rng.shuffle(shared)
    return {"walls": walls, "stars": set(shared[:_STARS_TOTAL])}


def _build_fn(code: str, role: str, events: list[dict[str, object]], print_context: dict[str, int]):
    namespace = {"__builtins__": _builtins(role, events, print_context)}
    compile_error = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("make_move") or namespace.get("choose_move")
    return (fn if callable(fn) else _fallback_move), compile_error


def _builtins(slot: str, events: list[dict[str, object]], print_context: dict[str, int]) -> dict[str, object]:
    def bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message += end
        for line in message.splitlines() or [""]:
            events.append({"type": "bot_print", "tick": int(print_context.get("tick", 0)), "role": slot, "message": line})

    return {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
        "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
        "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]], role: str, team: str) -> object:
    for args in ((x, y, board, role, team), (x, y, board, role), (x, y, board)):
        try:
            return fn(*args)
        except TypeError:
            continue
        except Exception:
            return None
    return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]], _role: str = "", _team: str = "") -> str:
    return "stay"


def _board(
    walls: set[tuple[int, int]],
    stars: set[tuple[int, int]],
    positions: dict[tuple[str, str], tuple[int, int]],
    teams: list[str],
    viewer_team: str,
    viewer_role: str,
) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in stars:
        board[x][y] = 1

    for team in teams:
        if team == viewer_team:
            continue
        target_role = "runner" if viewer_role == "hunter" else "hunter"
        x, y = positions[(team, target_role)]
        board[x][y] = -2
    return board


def _resolve_collisions(
    teams: list[str],
    positions: dict[tuple[str, str], tuple[int, int]],
    intents: dict[tuple[str, str], tuple[int, int]],
    events: list[dict[str, object]],
    turn: int,
) -> dict[tuple[str, str], tuple[int, int]]:
    result = dict(intents)
    entities = [(team, role) for team in teams for role in _ROLES]
    for index, first in enumerate(entities):
        for second in entities[index + 1 :]:
            if first[0] != second[0] and intents[first] == intents[second]:
                if _is_hunter_runner_pair(first, second):
                    continue
                result[first] = positions[first]
                result[second] = positions[second]
                events.append({"type": "collision_bounce", "tick": turn + 1, "slots": [f"{first[0]}_{first[1]}", f"{second[0]}_{second[1]}"]})
            elif first[0] != second[0] and intents[first] == positions[second] and intents[second] == positions[first]:
                if _is_hunter_runner_pair(first, second):
                    result[first] = intents[first]
                    result[second] = intents[second]
                    continue
                result[first] = positions[first]
                result[second] = positions[second]
                events.append({"type": "swap_blocked", "tick": turn + 1, "slots": [f"{first[0]}_{first[1]}", f"{second[0]}_{second[1]}"]})
    return result


def _is_hunter_runner_pair(first: tuple[str, str], second: tuple[str, str]) -> bool:
    return {first[1], second[1]} == {"hunter", "runner"}


def _apply_catches(
    teams: list[str],
    positions: dict[tuple[str, str], tuple[int, int]],
    frozen: dict[str, int],
    catches: dict[str, int],
    events: list[dict[str, object]],
    turn: int,
) -> list[dict[str, object]]:
    caught_events: list[dict[str, object]] = []
    for hunter_team in teams:
        hunter_pos = positions[(hunter_team, "hunter")]
        for runner_team in teams:
            if runner_team == hunter_team:
                continue
            if positions[(runner_team, "runner")] == hunter_pos:
                catches[hunter_team] += 1
                frozen[runner_team] = _RESPAWN_FREEZE
                event = {
                    "type": "caught",
                    "message": "Охотник поймал чужого беглеца.",
                    "tick": turn + 1,
                    "hunter_team": hunter_team,
                    "runner_team": runner_team,
                    "count": catches[hunter_team],
                }
                events.append(event)
                caught_events.append(event)
    return caught_events


def _move(position: tuple[int, int], action: str) -> tuple[int, int]:
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def _reachable_cells(start: tuple[int, int], walls: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue = [start]
    seen = {start}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        for action in ("up", "down", "left", "right"):
            nxt = _move(current, action)
            if nxt in walls or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def _winner_slots(teams: list[str], slot_scores: dict[str, int]) -> list[str]:
    best = max(slot_scores.values()) if slot_scores else 0
    return [team for team in teams if slot_scores.get(team, 0) == best]


def _is_tie(teams: list[str], slot_scores: dict[str, int]) -> bool:
    return len(_winner_slots(teams, slot_scores)) > 1


def _placements(teams: list[str], role_team: dict[str, str], slot_scores: dict[str, int]) -> dict[str, int]:
    ordered = sorted(teams, key=lambda team: slot_scores[team], reverse=True)
    result: dict[str, int] = {}
    last_score: int | None = None
    last_place = 0
    for index, team in enumerate(ordered, start=1):
        score = slot_scores[team]
        if score != last_score:
            last_place = index
            last_score = score
        result[role_team[team]] = last_place
    return result


def _frame(
    tick: int,
    phase: str,
    teams: list[str],
    positions: dict[tuple[str, str], tuple[int, int]],
    walls: set[tuple[int, int]],
    stars: set[tuple[int, int]],
    collected: dict[str, int],
    catches: dict[str, int],
    invalid: dict[str, int],
    frozen: dict[str, int],
    role_team: dict[str, str],
    role_name: dict[str, str],
    caught_events: list[dict[str, object]],
    slot_scores: dict[str, int] | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, stars, positions, teams, teams[0], "runner"),
        "boards": {
            f"{team}_{role}": _board(walls, stars, positions, teams, team, role)
            for team in teams
            for role in _ROLES
        },
        "width": _WIDTH,
        "height": _HEIGHT,
        "teams": teams,
        "roles": list(_ROLES),
        "positions": {f"{team}_{role}": {"x": pos[0], "y": pos[1], "team": team, "role": role} for (team, role), pos in positions.items()},
        "labels": {team: role_name[team] for team in teams},
        "team_ids": {team: role_team[team] for team in teams},
        "stars_collected": dict(collected),
        "stars_left": len(stars),
        "catches": dict(catches),
        "runner_frozen": dict(frozen),
        "caught_events": caught_events,
        "invalid_moves": dict(invalid),
    }
    if slot_scores is not None:
        frame["slot_scores"] = slot_scores
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
