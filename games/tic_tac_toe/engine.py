from __future__ import annotations

import builtins
import inspect
import json
import os
import random
from types import ModuleType
from typing import Any, Callable


_BOARD_SIZE = 5
_CONNECT = 4
_PLAYER_ROLE = 1
_ENEMY_ROLE = -1
_MAX_TURNS = _BOARD_SIZE * _BOARD_SIZE * 2


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    participants = ctx.get("participants")
    if isinstance(participants, list) and participants and isinstance(participants[0], dict):
        ctx = {**ctx, "team_id": participants[0].get("team_id", ctx.get("team_id")),
               "codes_by_slot": participants[0].get("codes_by_slot", ctx.get("codes_by_slot", {}))}
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    labels = _resolve_labels(ctx)
    participants = ctx.get("participants")
    opponent = participants[1] if isinstance(participants, list) and len(participants) >= 2 else None
    team_player_id = _resolve_team_player_id(ctx)
    team_enemy_id = str(opponent["team_id"]) if isinstance(opponent, dict) and opponent.get("team_id") else "team-bot"
    team_by_role = {1: team_player_id, -1: team_enemy_id}
    player_fn, compile_error = _build_player_fn(
        {**ctx, "actor_role": 1, "actor_team_id": team_player_id}, "bot", events, print_context,
    )
    enemy_compile_error = None
    if isinstance(opponent, dict):
        enemy_fn, enemy_compile_error = _build_player_fn(
            {**ctx, "codes_by_slot": opponent.get("codes_by_slot", {}), "actor_role": -1,
             "actor_team_id": team_enemy_id}, "bot", events, print_context,
        )
    else:
        def enemy_fn(field, role):
            return _enemy_move(field)
    bots = {1: player_fn, -1: enemy_fn}
    bot_errors_by_team = {team_player_id: int(bool(compile_error)), team_enemy_id: int(bool(enemy_compile_error))}

    board = _create_board()
    invalid_moves_player = 0
    invalid_moves_enemy = 0
    turns_played = 0
    winner_role = 0
    current_role = _PLAYER_ROLE
    frames: list[dict[str, object]] = [
        {
            "tick": 0,
            "phase": "running",
            "frame": {
                "board": _copy_board(board),
                "turns_played": turns_played,
                "winner_role": winner_role,
                "next_role": current_role,
                "labels": labels,
            },
        }
    ]

    for _ in range(_MAX_TURNS):
        print_context["tick"] = turns_played
        fn = bots[current_role]
        move = None
        if fn is not None:
            try:
                move = _call_player(fn, board, current_role)
                if not _is_valid_move(board, move):
                    raise ValueError("Верните координаты свободной клетки: два целых числа от 0 до 4")
            except Exception as exc:
                bot_errors_by_team[team_by_role[current_role]] += 1
                events.append(_error_event(exc, "bot_error", turns_played, current_role,
                                           team_by_role[current_role]))
                move = None
        turns_played += 1
        if move is None:
            if current_role == 1:
                invalid_moves_player += 1
            else:
                invalid_moves_enemy += 1
            events.append({"type": "turn_skipped", "tick": turns_played, "role": current_role,
                           "team_id": team_by_role[current_role], "message": "Ход пропущен из-за ошибки кода"})
            current_role = -current_role
            frames.append({"tick": turns_played, "phase": "running", "frame": {
                "board": _copy_board(board), "turns_played": turns_played,
                "winner_role": winner_role, "next_role": current_role, "labels": labels,
            }})
            continue

        x, y = move
        board[x][y] = current_role
        events.append({"type": "move", "tick": turns_played, "turn": turns_played, "role": current_role, "x": x, "y": y})

        winner_role = _check_winner(board)
        next_role = _ENEMY_ROLE if current_role == _PLAYER_ROLE else _PLAYER_ROLE
        frames.append(
            {
                "tick": turns_played,
                "phase": "running",
                "frame": {
                    "board": _copy_board(board),
                    "turns_played": turns_played,
                    "winner_role": winner_role,
                    "next_role": next_role,
                    "labels": labels,
                },
            }
        )
        if winner_role != 0:
            events.append({"type": "winner", "tick": turns_played, "role": winner_role})
            break

        if _first_free_cell(board) is None:
            break

        current_role = next_role

    scores = _build_scores(team_player_id=team_player_id, team_enemy_id=team_enemy_id, winner_role=winner_role)
    placements = _build_placements(team_player_id=team_player_id, team_enemy_id=team_enemy_id, winner_role=winner_role)

    metrics: dict[str, object] = {
        "turns_played": turns_played,
        "winner_role": winner_role,
        "draw": winner_role == 0,
        "invalid_moves_player": invalid_moves_player,
        "invalid_moves_enemy": invalid_moves_enemy,
    }
    metrics["bot_errors_by_team"] = bot_errors_by_team
    metrics["bot_errors"] = sum(bot_errors_by_team.values())
    compile_errors = {team: error for team, error in (
        (team_player_id, compile_error), (team_enemy_id, enemy_compile_error),
    ) if error}
    if compile_errors:
        metrics["compile_errors"] = compile_errors

    payload: dict[str, object] = {
        "status": "finished",
        "metrics": metrics,
    }
    run_kind = str(ctx.get("run_kind") or "training_match")
    if run_kind == "competition_match":
        payload["scores"] = scores
        payload["placements"] = placements
        if winner_role == 0:
            payload["tie_resolution"] = "explicit_tie"
    elif run_kind == "training_match":
        payload["scores"] = scores
        payload["placements"] = placements
    else:
        payload["replay_ref"] = None

    frames.append(
        {
            "tick": len(frames),
            "phase": "finished",
            "frame": {
                "board": _copy_board(board),
                "turns_played": turns_played,
                "winner_role": winner_role,
                "draw": winner_role == 0,
                "labels": labels,
            },
        }
    )
    payload["frames"] = frames
    payload["events"] = events

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


def _create_board() -> list[list[int]]:
    return [[0 for _ in range(_BOARD_SIZE)] for _ in range(_BOARD_SIZE)]


def _resolve_labels(ctx: dict[str, Any]) -> dict[str, str]:
    participants = ctx.get("participants")
    if isinstance(participants, list) and participants:
        first = participants[0]
        second = participants[1] if len(participants) > 1 else {}
        player = first.get("display_name") or first.get("captain_user_id") or first.get("team_id") if isinstance(first, dict) else None
        enemy = second.get("display_name") or second.get("captain_user_id") or second.get("team_id") if isinstance(second, dict) else None
        return {"1": str(player) if player else "Игрок", "-1": str(enemy) if enemy else "Соперник"}
    raw = ctx.get("display_name") or ctx.get("team_name") or ctx.get("requested_by")
    return {"1": str(raw) if raw else "Игрок", "-1": "Соперник"}


def _build_player_fn(
    ctx: dict[str, Any],
    slot_key: str,
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[Callable[..., object] | None, str | None]:
    code = _code_for_slot(ctx=ctx, slot_key=slot_key)
    namespace: dict[str, Any] = {
        "__builtins__": _safe_builtins(
            print_fn=_make_bot_print(events=events, role=str(ctx.get("actor_role", 1)), print_context=print_context),
            seed=f"{ctx.get('seed') or ctx.get('run_id') or 'connect5'}:{ctx.get('actor_team_id') or ctx.get('team_id')}",
        )
    }
    namespace["__name__"] = "bot"
    role = int(ctx.get("actor_role", 1))
    team_id = str(ctx.get("actor_team_id") or ctx.get("team_id") or "team-player")
    try:
        if not code.strip():
            raise ValueError("Напишите функцию make_choice(field, role)")
        exec(compile(code, f"<bot:{team_id}>", "exec"), namespace, namespace)
        fn = namespace.get("make_choice") or namespace.get("make_move")
        if not callable(fn):
            bot_cls = namespace.get("Bot")
            instance = bot_cls() if isinstance(bot_cls, type) else None
            fn = getattr(instance, "make_move", None) or getattr(instance, "make_choice", None)
        if not callable(fn):
            raise ValueError("Не найдена функция make_choice(field, role) или make_move(observation)")
        return fn, None
    except Exception as exc:
        event = _error_event(exc, "compile_error", 0, role, team_id)
        events.append(event)
        return None, str(event["message"])


def _error_event(exc: Exception, kind: str, tick: int, role: int, team_id: str) -> dict[str, object]:
    line = getattr(exc, "lineno", None)
    trace = exc.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code.co_filename.startswith("<bot:"):
            line = trace.tb_lineno
        trace = trace.tb_next
    return {"type": kind, "tick": tick, "role": role, "team_id": team_id,
            "line": line, "message": f"{type(exc).__name__}: {str(exc)[:800]}"}


def _safe_builtins(print_fn: Callable[..., None] | None = None, seed: str = "connect5") -> dict[str, object]:
    rng = random.Random(seed)
    module = ModuleType("random")
    for name in random.__all__:
        if hasattr(rng, name):
            setattr(module, name, getattr(rng, name))
    module.Random = random.Random

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name != "random" or level:
            raise ImportError(f"Модуль «{name}» недоступен в этой игре")
        return module

    return {
        "__import__": safe_import, "__build_class__": builtins.__build_class__, "object": object,
        "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,

        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": print_fn or print,
        "range": range,
        "set": set,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
        "hasattr": hasattr,
        "getattr": getattr,
        "setattr": setattr,
    }


def _make_bot_print(
    events: list[dict[str, object]],
    role: str,
    print_context: dict[str, int],
) -> Callable[..., None]:
    def _bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message = f"{message}{end}"
        lines = message.splitlines() or [""]
        for line in lines:
            events.append(
                {
                    "type": "bot_print",
                    "tick": int(print_context.get("tick", 0)),
                    "role": role,
                    "message": line,
                }
            )

    return _bot_print


def _code_for_slot(ctx: dict[str, Any], slot_key: str) -> str:
    codes = ctx.get("codes_by_slot")
    if not isinstance(codes, dict):
        return ""
    code = codes.get(slot_key)
    return code if isinstance(code, str) else ""


def _call_player(player_fn: Callable[..., object], board: list[list[int]], role: int) -> tuple[int, int] | None:
    field = _copy_board(board)
    signature = inspect.signature(player_fn)
    try:
        signature.bind(field, role)
    except TypeError:
        signature.bind({"field": field, "role": role})
        candidate = player_fn({"field": field, "role": role})
    else:
        candidate = player_fn(field, role)
    return _normalize_move(candidate)


def _normalize_move(value: object) -> tuple[int, int] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    x = _to_cell_index(value[0])
    y = _to_cell_index(value[1])
    if x is None or y is None:
        return None
    return x, y


def _to_cell_index(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value >= _BOARD_SIZE:
        return None
    return value


def _is_valid_move(board: list[list[int]], move: tuple[int, int] | None) -> bool:
    if move is None:
        return False
    x, y = move
    return board[x][y] == 0


def _fallback_player_move(board: list[list[int]], _role: int) -> tuple[int, int] | None:
    return _first_free_cell(board)


def _enemy_move(board: list[list[int]]) -> tuple[int, int] | None:
    center = (_BOARD_SIZE // 2, _BOARD_SIZE // 2)
    if _is_valid_move(board, center):
        return center
    return _first_free_cell(board)


def _first_free_cell(board: list[list[int]]) -> tuple[int, int] | None:
    for x in range(_BOARD_SIZE):
        for y in range(_BOARD_SIZE):
            if board[x][y] == 0:
                return x, y
    return None


def _check_winner(board: list[list[int]]) -> int:
    directions = ((1, 0), (0, 1), (1, 1), (1, -1))
    for x in range(_BOARD_SIZE):
        for y in range(_BOARD_SIZE):
            role = board[x][y]
            if role == 0:
                continue
            for dx, dy in directions:
                if _has_line(board=board, x=x, y=y, dx=dx, dy=dy, role=role):
                    return role
    return 0


def _has_line(board: list[list[int]], x: int, y: int, dx: int, dy: int, role: int) -> bool:
    for step in range(1, _CONNECT):
        nx = x + dx * step
        ny = y + dy * step
        if nx < 0 or ny < 0 or nx >= _BOARD_SIZE or ny >= _BOARD_SIZE:
            return False
        if board[nx][ny] != role:
            return False
    return True


def _build_scores(team_player_id: str, team_enemy_id: str, winner_role: int) -> dict[str, float]:
    if winner_role == _PLAYER_ROLE:
        return {team_player_id: 1, team_enemy_id: 0}
    if winner_role == _ENEMY_ROLE:
        return {team_player_id: 0, team_enemy_id: 1}
    return {team_player_id: 0.5, team_enemy_id: 0.5}


def _build_placements(team_player_id: str, team_enemy_id: str, winner_role: int) -> dict[str, int]:
    if winner_role == _PLAYER_ROLE:
        return {team_player_id: 1, team_enemy_id: 2}
    if winner_role == _ENEMY_ROLE:
        return {team_player_id: 2, team_enemy_id: 1}
    return {team_player_id: 1, team_enemy_id: 1}


def _resolve_team_player_id(ctx: dict[str, Any]) -> str:
    team_id = ctx.get("team_id")
    if isinstance(team_id, str) and team_id.strip():
        return team_id
    return "team-player"


def _copy_board(board: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in board]


# Legacy-compatible exports for regression tests.
def createEmptyField() -> list[list[int]]:
    return _create_board()


def checkForWin(field: list[list[int]]) -> int:
    return _check_winner(field)


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
