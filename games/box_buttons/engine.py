from __future__ import annotations

import json
import os
import random
from typing import Any, Callable


_WIDTH = 10
_HEIGHT = 10
_MAX_TURNS = 180
_START = (1, 1)
_BOXES_TOTAL = 2
_RANDOM_WALLS = 10
_DELTAS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "stay": (0, 0)}
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
    move_fn, compile_error = _build_player_fn(ctx, events, print_context)
    game_map = _build_map(ctx)
    walls = game_map["walls"]
    boxes = game_map["boxes"]
    targets = game_map["targets"]
    assert isinstance(walls, set) and isinstance(boxes, set) and isinstance(targets, set)

    position = _START
    pushes = 0
    invalid_moves = 0
    turns = 0
    completed = _completed(boxes, targets)
    frames = [_frame(0, "running", position, walls, boxes, targets, pushes, completed, invalid_moves)]

    for turn in range(_MAX_TURNS):
        if completed:
            break
        print_context["tick"] = turn
        action = _safe_call(move_fn, position[0], position[1], _board(walls, boxes, targets))
        if action not in _DELTAS:
            invalid_moves += 1
            action = "stay"
            events.append({"type": "invalid_action", "message": "Недопустимое действие: верните одну из разрешенных команд.", "tick": turn, "action": repr(action)})

        target = _move(position, str(action))
        if target in walls:
            invalid_moves += 1
            target = position
            events.append({"type": "blocked_move", "message": "Ход заблокирован: там стена, закрытая клетка или другой непроходимый объект.", "tick": turn, "action": action})
        elif target in boxes:
            pushed_to = _move(target, str(action))
            if pushed_to in walls or pushed_to in boxes:
                invalid_moves += 1
                target = position
                events.append({"type": "blocked_push", "tick": turn, "action": action})
            else:
                boxes.remove(target)
                boxes.add(pushed_to)
                pushes += 1
                events.append({"type": "push", "tick": turn + 1, "from": {"x": target[0], "y": target[1]}, "to": {"x": pushed_to[0], "y": pushed_to[1]}})

        position = target
        turns = turn + 1
        completed = _completed(boxes, targets)
        if completed:
            events.append({"type": "completed", "tick": turns})
        frames.append(_frame(turns, "running", position, walls, boxes, targets, pushes, completed, invalid_moves))

    boxes_on_targets = sum(1 for box in boxes if box in targets)
    score = max(0, boxes_on_targets * 180 + (400 if completed else 0) - turns * 2 - pushes * 3 - invalid_moves * 15)
    metrics: dict[str, object] = {
        "turns": turns,
        "completed": completed,
        "solved": completed,
        "boxes_on_targets": boxes_on_targets,
        "boxes_total": _BOXES_TOTAL,
        "targets_total": _BOXES_TOTAL,
        "pushes": pushes,
        "walls_total": len(walls) - len(_BORDER_WALLS),
        "invalid_moves": invalid_moves,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(_frame(len(frames), "finished", position, walls, boxes, targets, pushes, completed, invalid_moves, score))
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


def _build_map(context: dict[str, Any]) -> dict[str, object]:
    seed = context.get("run_id")
    if not isinstance(seed, str) or not seed:
        seed = "box_buttons_offline"
    rng = random.Random(seed)
    candidates = [(x, y) for y in range(1, _HEIGHT - 1) for x in range(1, _WIDTH - 1) if (x, y) != _START]
    for _attempt in range(1200):
        rng.shuffle(candidates)
        walls = set(_BORDER_WALLS) | set(candidates[:_RANDOM_WALLS])
        reachable = sorted(_reachable_cells(_START, walls) - {_START})
        if len(reachable) < _BOXES_TOTAL * 2 + 8:
            continue
        rng.shuffle(reachable)
        boxes = set(reachable[:_BOXES_TOTAL])
        targets = set(reachable[_BOXES_TOTAL:_BOXES_TOTAL * 2])
        if boxes & targets:
            continue
        if _can_solve(walls, boxes, targets):
            return {"walls": walls, "boxes": boxes, "targets": targets}
    walls = set(_BORDER_WALLS)
    return {"walls": walls, "boxes": {(3, 2), (3, 4)}, "targets": {(7, 2), (7, 4)}}


def _build_player_fn(context: dict[str, Any], events: list[dict[str, object]], print_context: dict[str, int]) -> tuple[Callable[..., object], str | None]:
    code = ""
    codes = context.get("codes_by_slot")
    if isinstance(codes, dict) and isinstance(codes.get("agent"), str):
        code = str(codes["agent"])
    namespace = {"__builtins__": _builtins(events, print_context)}
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    fn = namespace.get("make_move") or namespace.get("choose_move")
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
        "print": bot_print, "range": range, "set": set, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "zip": zip,
    }


def _safe_call(fn: Callable[..., object], x: int, y: int, board: list[list[int]]) -> object:
    try:
        return fn(x, y, board)
    except Exception:
        return None


def _fallback_move(_x: int, _y: int, _board_value: list[list[int]]) -> str:
    return "right"


def _board(walls: set[tuple[int, int]], boxes: set[tuple[int, int]], targets: set[tuple[int, int]]) -> list[list[int]]:
    board = [[0 for _ in range(_HEIGHT)] for _ in range(_WIDTH)]
    for x, y in walls:
        board[x][y] = -1
    for x, y in targets:
        board[x][y] = 2
    for x, y in boxes:
        board[x][y] = 3 if (x, y) in targets else 1
    return board


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


def _completed(boxes: set[tuple[int, int]], targets: set[tuple[int, int]]) -> bool:
    return bool(boxes) and boxes <= targets


def _can_solve(walls: set[tuple[int, int]], boxes: set[tuple[int, int]], targets: set[tuple[int, int]]) -> bool:
    start_state = (_START, tuple(sorted(boxes)))
    queue = [start_state]
    seen = {start_state}
    head = 0
    while head < len(queue) and len(seen) < 20000:
        player, box_tuple = queue[head]
        head += 1
        current_boxes = set(box_tuple)
        if current_boxes <= targets:
            return True
        for action in ("up", "down", "left", "right"):
            nxt = _move(player, action)
            next_boxes = set(current_boxes)
            if nxt in walls:
                continue
            if nxt in current_boxes:
                pushed_to = _move(nxt, action)
                if pushed_to in walls or pushed_to in current_boxes:
                    continue
                next_boxes.remove(nxt)
                next_boxes.add(pushed_to)
            state = (nxt, tuple(sorted(next_boxes)))
            if state in seen:
                continue
            seen.add(state)
            queue.append(state)
    return False


def _frame(
    tick: int,
    phase: str,
    position: tuple[int, int],
    walls: set[tuple[int, int]],
    boxes: set[tuple[int, int]],
    targets: set[tuple[int, int]],
    pushes: int,
    completed: bool,
    invalid_moves: int,
    score: int | None = None,
) -> dict[str, object]:
    frame: dict[str, object] = {
        "board": _board(walls, boxes, targets),
        "width": _WIDTH,
        "height": _HEIGHT,
        "position": {"x": position[0], "y": position[1]},
        "boxes": [{"x": x, "y": y} for x, y in sorted(boxes)],
        "targets": [{"x": x, "y": y} for x, y in sorted(targets)],
        "pushes": pushes,
        "completed": completed,
        "invalid_moves": invalid_moves,
    }
    if score is not None:
        frame["score"] = score
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
