from __future__ import annotations

import json
import os
from typing import Any, Callable


_BOARD_SIZE = 5
_CONNECT = 5
_PLAYER_ROLE = 1
_ENEMY_ROLE = -1
_MAX_TURNS = _BOARD_SIZE * _BOARD_SIZE


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    player_fn, compile_error = _build_player_fn(
        ctx=ctx,
        slot_key="bot",
        events=events,
        print_context=print_context,
    )

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
            },
        }
    ]

    for _ in range(_MAX_TURNS):
        if current_role == _PLAYER_ROLE:
            print_context["tick"] = turns_played
            move = _call_player(player_fn=player_fn, board=board, role=current_role)
            if not _is_valid_move(board=board, move=move):
                invalid_moves_player += 1
                events.append({"type": "invalid_move", "role": "player"})
                move = _first_free_cell(board)
        else:
            move = _enemy_move(board)
            if not _is_valid_move(board=board, move=move):
                invalid_moves_enemy += 1
                events.append({"type": "invalid_move", "role": "enemy"})
                move = _first_free_cell(board)

        if move is None:
            break

        x, y = move
        board[x][y] = current_role
        turns_played += 1
        events.append({"type": "move", "turn": turns_played, "role": current_role, "x": x, "y": y})

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
                },
            }
        )
        if winner_role != 0:
            events.append({"type": "winner", "role": winner_role})
            break

        if _first_free_cell(board) is None:
            break

        current_role = next_role

    team_player_id = _resolve_team_player_id(ctx)
    team_enemy_id = "team-bot"
    scores = _build_scores(team_player_id=team_player_id, team_enemy_id=team_enemy_id, winner_role=winner_role)
    placements = _build_placements(team_player_id=team_player_id, team_enemy_id=team_enemy_id, winner_role=winner_role)

    metrics: dict[str, object] = {
        "turns_played": turns_played,
        "winner_role": winner_role,
        "draw": winner_role == 0,
        "invalid_moves_player": invalid_moves_player,
        "invalid_moves_enemy": invalid_moves_enemy,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

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


def _build_player_fn(
    ctx: dict[str, Any],
    slot_key: str,
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[Callable[..., object], str | None]:
    code = _code_for_slot(ctx=ctx, slot_key=slot_key)
    namespace: dict[str, Any] = {
        "__builtins__": _safe_builtins(
            print_fn=_make_bot_print(events=events, role=slot_key, print_context=print_context),
        )
    }
    compile_error: str | None = None

    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:  # pragma: no cover - runtime path
            compile_error = str(exc)

    fn = namespace.get("make_choice") or namespace.get("make_move")
    if callable(fn):
        return fn, compile_error

    bot_cls = namespace.get("Bot")
    if isinstance(bot_cls, type):
        try:
            instance = bot_cls()
            method = getattr(instance, "make_move", None) or getattr(instance, "make_choice", None)
            if callable(method):
                return method, compile_error
        except Exception as exc:  # pragma: no cover - runtime path
            compile_error = str(exc)

    return _fallback_player_move, compile_error


def _safe_builtins(print_fn: Callable[..., None] | None = None) -> dict[str, object]:
    return {
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
    try:
        candidate = player_fn(_copy_board(board), role)
    except TypeError:
        # Совместимость с сигнатурой `make_move(observation)`.
        try:
            candidate = player_fn({"field": _copy_board(board), "role": role})
        except Exception:  # pragma: no cover - runtime path
            return None
    except Exception:  # pragma: no cover - runtime path
        return None
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


def _build_scores(team_player_id: str, team_enemy_id: str, winner_role: int) -> dict[str, int]:
    if winner_role == _PLAYER_ROLE:
        return {team_player_id: 1, team_enemy_id: 0}
    if winner_role == _ENEMY_ROLE:
        return {team_player_id: 0, team_enemy_id: 1}
    return {team_player_id: 0, team_enemy_id: 0}


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
