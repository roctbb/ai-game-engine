from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 12
_HEIGHT = 12
_MAX_TURNS = 320
_UNKNOWN = -2
_FLAG = -1
_MINES_TOTAL = 18


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    choose_fn, compile_error = _build_player_fn(ctx, events, print_context)

    visible = [[_UNKNOWN for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    opened: set[tuple[int, int]] = set()
    flags: set[tuple[int, int]] = set()
    mines: set[tuple[int, int]] | None = None
    invalid_moves = 0
    hit_mine = False
    won = False
    turns = 0
    frames: list[dict[str, object]] = [_frame(0, "running", visible, flags, opened, hit_mine, won, invalid_moves, mines)]

    for turn in range(_MAX_TURNS):
        if hit_mine or (mines is not None and _all_safe_opened(opened, mines)):
            won = mines is not None and _all_safe_opened(opened, mines) and not hit_mine
            break
        print_context["tick"] = turn
        action = _safe_call(choose_fn, _copy_grid(visible), _MINES_TOTAL - len(flags))
        kind, cell = _normalize_action(action)
        if kind is None or cell is None:
            invalid_moves += 1
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})
            frames.append(_frame(turn + 1, "running", visible, flags, opened, hit_mine, won, invalid_moves, mines))
            continue

        x, y = cell
        if kind == "flag":
            if cell in opened:
                invalid_moves += 1
                events.append({"type": "invalid_flag", "tick": turn, "x": x, "y": y})
            elif cell in flags:
                flags.remove(cell)
                visible[x][y] = _UNKNOWN
                events.append({"type": "unflag", "tick": turn, "x": x, "y": y})
            elif len(flags) < _MINES_TOTAL:
                flags.add(cell)
                visible[x][y] = _FLAG
                events.append({"type": "flag", "tick": turn, "x": x, "y": y})
            else:
                invalid_moves += 1
                events.append({"type": "too_many_flags", "tick": turn, "x": x, "y": y})
        else:
            if cell in flags or cell in opened:
                invalid_moves += 1
                events.append({"type": "invalid_open", "tick": turn, "x": x, "y": y})
            else:
                if mines is None:
                    mines = _build_mines(ctx, first_open=cell)
                if cell in mines:
                    hit_mine = True
                    visible[x][y] = 9
                    events.append({"type": "mine_hit", "tick": turn, "x": x, "y": y})
                else:
                    opened_now = _open_cell(visible, opened, cell, mines)
                    events.append({"type": "open", "tick": turn, "x": x, "y": y, "opened": opened_now})

        turns = turn + 1
        won = mines is not None and _all_safe_opened(opened, mines) and not hit_mine
        frames.append(_frame(turns, "running", visible, flags, opened, hit_mine, won, invalid_moves, mines))
        if won or hit_mine:
            break

    final_mines = mines or _build_mines(ctx, first_open=(0, 0))
    correctly_flagged = len(flags & final_mines)
    score = max(0, len(opened) * 5 + correctly_flagged * 12 + (150 if won else 0) - invalid_moves * 6 - (80 if hit_mine else 0))
    metrics: dict[str, object] = {
        "turns": turns,
        "opened_safe_cells": len(opened),
        "safe_cells_total": _WIDTH * _HEIGHT - len(final_mines),
        "mines_total": len(final_mines),
        "flags": len(flags),
        "correct_flags": correctly_flagged,
        "invalid_moves": invalid_moves,
        "hit_mine": hit_mine,
        "won": won,
        "solved": won,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", visible, flags, opened, hit_mine, won, invalid_moves, final_mines, score))
    return {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "replay_ref": None}


def _load_context() -> dict[str, Any]:
    raw = os.getenv("AGP_RUN_CONTEXT")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_player_fn(
    context: dict[str, Any],
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[Callable[..., object], str | None]:
    code = ""
    codes = context.get("codes_by_slot")
    if isinstance(codes, dict) and isinstance(codes.get("agent"), str):
        code = str(codes["agent"])
    namespace: dict[str, Any] = {"__builtins__": _builtins(events, print_context)}
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("choose_cell") or namespace.get("make_move")
    return (fn if callable(fn) else _fallback_move), compile_error


def _builtins(events: list[dict[str, object]], print_context: dict[str, int]) -> dict[str, object]:
    def bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message += end
        for line in message.splitlines() or [""]:
            events.append({"type": "bot_print", "tick": int(print_context.get("tick", 0)), "role": "agent", "message": line})

    return {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "enumerate": enumerate,
        "float": float, "int": int, "len": len, "list": list, "max": max, "min": min,
        "print": bot_print, "range": range, "set": set, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], board: list[list[int]], flags_left: int) -> object:
    try:
        return fn(board, flags_left)
    except TypeError:
        return fn(board)
    except Exception:
        return None


def _normalize_action(action: object) -> tuple[str | None, tuple[int, int] | None]:
    if isinstance(action, (list, tuple)) and len(action) == 3 and action[0] == "flag":
        x, y = action[1], action[2]
        if isinstance(x, int) and isinstance(y, int) and _inside(x, y):
            return "flag", (x, y)
    if isinstance(action, (list, tuple)) and len(action) == 2:
        x, y = action
        if isinstance(x, int) and isinstance(y, int) and _inside(x, y):
            return "open", (x, y)
    return None, None


def _fallback_move(board: list[list[int]], _flags_left: int = 0) -> tuple[int, int]:
    for y, row in enumerate(board):
        for x, cell in enumerate(row):
            if cell == _UNKNOWN:
                return x, y
    return 0, 0


def _build_mines(context: dict[str, Any], first_open: tuple[int, int]) -> set[tuple[int, int]]:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "minesweeper_offline"
    rng = random.Random(seed)
    protected = {first_open, *_neighbors(first_open[0], first_open[1])}
    candidates = [(x, y) for y in range(_HEIGHT) for x in range(_WIDTH) if (x, y) not in protected]
    best: set[tuple[int, int]] | None = None
    best_progress = -1

    for _attempt in range(5000):
        rng.shuffle(candidates)
        mines = set(candidates[:_MINES_TOTAL])
        solved, progress = _is_solvable_without_guessing(first_open=first_open, mines=mines)
        if solved:
            return mines
        if progress > best_progress:
            best = mines
            best_progress = progress

    return best or set(candidates[:_MINES_TOTAL])


def _is_solvable_without_guessing(first_open: tuple[int, int], mines: set[tuple[int, int]]) -> tuple[bool, int]:
    visible = [[_UNKNOWN for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    opened: set[tuple[int, int]] = set()
    flags: set[tuple[int, int]] = set()
    _open_cell(visible, opened, first_open, mines)

    changed = True
    while changed:
        changed = False
        for y in range(_HEIGHT):
            for x in range(_WIDTH):
                number = visible[x][y]
                if number < 0:
                    continue

                unknown: list[tuple[int, int]] = []
                flag_count = 0
                for nx, ny in _neighbors(x, y):
                    if (nx, ny) in flags:
                        flag_count += 1
                    elif visible[nx][ny] == _UNKNOWN:
                        unknown.append((nx, ny))

                if unknown and number == flag_count:
                    for cell in unknown:
                        if cell not in opened and cell not in mines:
                            _open_cell(visible, opened, cell, mines)
                            changed = True
                elif unknown and number == flag_count + len(unknown):
                    for cell in unknown:
                        if cell not in flags:
                            flags.add(cell)
                            visible[cell[0]][cell[1]] = _FLAG
                            changed = True

    return _all_safe_opened(opened, mines), len(opened)


def _open_cell(visible: list[list[int]], opened: set[tuple[int, int]], start: tuple[int, int], mines: set[tuple[int, int]]) -> int:
    queue = [start]
    count = 0
    while queue:
        cell = queue.pop()
        if cell in opened or cell in mines:
            continue
        x, y = cell
        opened.add(cell)
        count += 1
        number = _neighbor_mines(x, y, mines)
        visible[x][y] = number
        if number == 0:
            for nx, ny in _neighbors(x, y):
                if (nx, ny) not in opened:
                    queue.append((nx, ny))
    return count


def _neighbor_mines(x: int, y: int, mines: set[tuple[int, int]]) -> int:
    return sum(1 for cell in _neighbors(x, y) if cell in mines)


def _neighbors(x: int, y: int) -> list[tuple[int, int]]:
    result = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if _inside(nx, ny):
                result.append((nx, ny))
    return result


def _inside(x: int, y: int) -> bool:
    return 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def _all_safe_opened(opened: set[tuple[int, int]], mines: set[tuple[int, int]]) -> bool:
    return len(opened) == _WIDTH * _HEIGHT - len(mines)


def _frame(
    tick: int,
    phase: str,
    visible: list[list[int]],
    flags: set[tuple[int, int]],
    opened: set[tuple[int, int]],
    hit_mine: bool,
    won: bool,
    invalid_moves: int,
    mines: set[tuple[int, int]] | None,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _copy_grid(visible),
        "width": _WIDTH,
        "height": _HEIGHT,
        "flags_left": _MINES_TOTAL - len(flags),
        "opened": len(opened),
        "hit_mine": hit_mine,
        "won": won,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
        frame["mines"] = [{"x": x, "y": y} for x, y in sorted(mines or set())]
    return {"tick": tick, "phase": phase, "frame": frame}


def _copy_grid(grid: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in grid]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
