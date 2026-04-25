from __future__ import annotations

import json
import os
import random
from typing import Any, Callable

CONFIG = {
  "dir": "farm_grid",
  "id": "farm_grid_v1",
  "title": "Ферма 2D",
  "difficulty": "medium",
  "section": "Матрицы и координаты",
  "topics": [
    "матрицы",
    "вложенные циклы",
    "подсчет"
  ],
  "kind": "farm_grid",
  "instruction": "Определите функцию count_plants(field), которая считает все растения на ферме.",
  "learning_section": "Матрицы и координаты",
  "mode": "single_task",
  "slots": [
    {
      "key": "agent"
    }
  ]
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    rng = random.Random(str(ctx.get("run_id") or CONFIG["id"]))
    if CONFIG.get("mode") == "small_match":
        return _run_match(ctx, rng)
    return _run_single(ctx, rng)


def _load_context() -> dict[str, Any]:
    raw = os.getenv("AGP_RUN_CONTEXT")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _run_single(ctx: dict[str, Any], rng: random.Random) -> dict[str, object]:
    events: list[dict[str, object]] = []
    task = _build_task(CONFIG["kind"], rng)
    fn, compile_error = _build_fn(ctx, "agent", events, {"tick": 0})
    details = _evaluate_task(CONFIG["kind"], task, fn, events)
    if compile_error:
        details["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})
    solved = bool(details.get("solved"))
    score = int(details.get("score", 0))
    metrics = {
        "solved": solved,
        "score": score,
        "kind": CONFIG["kind"],
        "learning_section": CONFIG["learning_section"],
        "expected": details.get("expected"),
        "actual": details.get("actual"),
    }
    for metric_key in ("correct", "total", "missing", "extra"):
        if metric_key in details:
            metrics[metric_key] = details[metric_key]
    frames = _build_single_frames(task, details, score, solved)
    return {"status": "finished", "metrics": metrics, "frames": frames, "events": events, "replay_ref": None}


def _build_single_frames(task: dict[str, object], details: dict[str, object], score: int, solved: bool) -> list[dict[str, object]]:
    expected = _normalize(details.get("expected"))
    actual = _normalize(details.get("actual"))
    frames = [_frame(0, "running", task, {"score": 0, "solved": False, "actual": actual, "expected": expected, "stage": "briefing", "step_title": "Разведка задания"})]
    steps = _visual_steps(task, expected, actual)
    total = max(1, len(steps))
    for index, step in enumerate(steps, start=1):
        frame_score = int(score * index / total) if solved else int(100 * index / total)
        frames.append(_frame(index, "running", task, {
            "score": min(frame_score, score if solved else 95),
            "solved": False,
            "actual": actual,
            "expected": expected,
            "stage": "action",
            "step": index,
            "steps_total": total,
            **step,
        }))
    frames.append(_frame(len(frames), "finished", task, {"score": score, "solved": solved, "actual": actual, "expected": expected, "stage": "result", "step_title": "Итог проверки"}))
    return frames


def _visual_steps(task: dict[str, object], expected: object, actual: object) -> list[dict[str, object]]:
    expected_list = expected if isinstance(expected, list) else []
    actual_list = actual if isinstance(actual, list) else []
    cases = task.get("cases")
    if isinstance(cases, list) and expected_list:
        steps = []
        for index, item in enumerate(cases):
            expected_step = expected_list[index] if index < len(expected_list) else None
            actual_step = actual_list[index] if index < len(actual_list) else None
            case_input = item.get("input", item) if isinstance(item, dict) else item
            steps.append(_step(index, expected_step, actual_step, {"case": _normalize(case_input)}))
        return steps
    if CONFIG["kind"] == "potion_maker":
        return _recipe_visual_steps(task, expected, actual)
    if CONFIG["kind"] in {"weakest_enemy", "priority_tower"}:
        return _enemy_choice_visual_steps(task, expected, actual)
    if CONFIG["kind"] == "space_queue":
        return _ship_queue_visual_steps(task, expected, actual)
    if CONFIG["kind"] == "miner_backpack":
        return _miner_visual_steps(task, expected, actual)
    if CONFIG["kind"] == "laser_mirrors":
        return _laser_visual_steps(task)
    if CONFIG["kind"] in {"pixel_painter", "treasure_scanner", "minesweeper_numbers", "farm_grid", "gravity_apples"}:
        board = task.get("board") or task.get("pixels") or task.get("field") or task.get("mines")
        board_steps = _board_visual_steps(board, expected, actual)
        if board_steps:
            return board_steps
    if expected_list:
        total = max(len(expected_list), len(actual_list))
        steps = []
        for index in range(total):
            expected_step = expected_list[index] if index < len(expected_list) else None
            actual_step = actual_list[index] if index < len(actual_list) else None
            steps.append(_step(index, expected_step, actual_step))
        return steps
    board = task.get("board") or task.get("pixels") or task.get("field") or task.get("mines")
    board_steps = _board_visual_steps(board, expected, actual)
    if board_steps:
        return board_steps
    return [_step(0, expected, actual)]


def _step(index: int, expected_step: object, actual_step: object, extra: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "active_index": index,
        "expected_step": _normalize(expected_step),
        "actual_step": _normalize(actual_step),
        "step_correct": _normalize(expected_step) == _normalize(actual_step),
        "step_title": f"Шаг {index + 1}",
    }
    if extra:
        payload.update(extra)
    return payload


def _recipe_visual_steps(task: dict[str, object], expected: object, actual: object) -> list[dict[str, object]]:
    recipes = task.get("recipes")
    resources = task.get("resources")
    if not isinstance(recipes, dict) or not isinstance(resources, dict):
        return [_step(0, expected, actual)]
    steps: list[dict[str, object]] = []
    for index, (name, recipe) in enumerate(recipes.items()):
        if not isinstance(recipe, dict):
            continue
        can_make = all(int(resources.get(k, 0)) >= int(v) for k, v in recipe.items() if k != "value")
        steps.append(_step(index, expected, actual, {
            "recipe_name": name,
            "recipe": _normalize(recipe),
            "can_make": can_make,
            "recipe_value": recipe.get("value"),
            "step_title": f"Рецепт {name}",
        }))
    return steps or [_step(0, expected, actual)]


def _enemy_choice_visual_steps(task: dict[str, object], expected: object, actual: object) -> list[dict[str, object]]:
    enemies = task.get("enemies")
    if not isinstance(enemies, list):
        return [_step(0, expected, actual)]
    steps: list[dict[str, object]] = []
    for index, enemy in enumerate(enemies):
        marker = enemy.get("id") if isinstance(enemy, dict) else None
        score = None
        if isinstance(enemy, dict) and CONFIG["kind"] == "priority_tower":
            score = int(enemy.get("danger", 0)) * 3 + int(enemy.get("speed", 0)) * 2 - int(enemy.get("distance", 0))
        steps.append(_step(index, expected, actual, {
            "enemy": _normalize(enemy),
            "enemy_score": score,
            "is_expected_target": marker == expected,
            "is_actual_target": marker == actual,
            "step_title": f"Цель {index + 1}",
        }))
    return steps or [_step(0, expected, actual)]


def _ship_queue_visual_steps(task: dict[str, object], expected: object, actual: object) -> list[dict[str, object]]:
    ships = task.get("ships")
    expected_order = expected if isinstance(expected, list) else []
    actual_order = actual if isinstance(actual, list) else []
    if not isinstance(ships, list):
        return [_step(0, expected, actual)]
    by_id = {ship.get("id"): ship for ship in ships if isinstance(ship, dict)}
    total = max(len(expected_order), len(actual_order), 1)
    steps: list[dict[str, object]] = []
    for index in range(total):
        expected_ship = expected_order[index] if index < len(expected_order) else None
        actual_ship = actual_order[index] if index < len(actual_order) else None
        steps.append(_step(index, expected_ship, actual_ship, {
            "ship": _normalize(by_id.get(expected_ship) or by_id.get(actual_ship) or {}),
            "active_ship_id": expected_ship or actual_ship,
            "step_title": f"Место в очереди {index + 1}",
        }))
    return steps


def _miner_visual_steps(task: dict[str, object], expected: object, actual: object) -> list[dict[str, object]]:
    ores = task.get("ores")
    capacity = int(task.get("capacity", 0))
    if not isinstance(ores, list):
        return [_step(0, expected, actual)]
    steps: list[dict[str, object]] = []
    total_weight = 0
    expected_count = int(expected) if isinstance(expected, int) else 0
    actual_count = int(actual) if isinstance(actual, int) else -1
    for index, ore in enumerate(ores):
        ore_weight = int(ore) if isinstance(ore, int) else 0
        can_take = total_weight + ore_weight <= capacity
        if can_take:
            total_weight += ore_weight
        steps.append(_step(index, expected_count, actual_count, {
            "active_index": index,
            "ore_weight": ore_weight,
            "backpack_weight": total_weight,
            "capacity": capacity,
            "can_take": can_take,
            "step_title": f"Жила {index + 1}",
        }))
        if not can_take:
            break
    return steps or [_step(0, expected, actual)]


def _board_visual_steps(board: object, expected: object, actual: object) -> list[dict[str, object]]:
    if not isinstance(board, list):
        return []
    cells = _board_cells(board)
    if not cells:
        return [_step(0, expected, actual)]
    stride = max(1, len(cells) // 14)
    selected = cells[::stride][:16]
    if cells[-1] not in selected:
        selected.append(cells[-1])
    return [_step(index, expected, actual, {"active_x": x, "active_y": y}) for index, (x, y) in enumerate(selected)]


def _board_cells(board: object) -> list[tuple[int, int]]:
    if not isinstance(board, list):
        return []
    width = len(board)
    height = len(board[0]) if width and isinstance(board[0], list) else 0
    return [(x, y) for y in range(height) for x in range(width)]


def _laser_visual_steps(task: dict[str, object]) -> list[dict[str, object]]:
    board = task.get("board")
    if not isinstance(board, list):
        return [_step(0, task.get("expected"), None)]
    x = int(task.get("start_x", 0)); y = int(task.get("start_y", 0)); dx = int(task.get("dx", 1)); dy = int(task.get("dy", 0))
    width = len(board); height = len(board[0]) if width and isinstance(board[0], list) else 0
    seen: set[tuple[int, int, int, int]] = set()
    steps: list[dict[str, object]] = []
    while 0 <= x < width and 0 <= y < height and (x, y, dx, dy) not in seen and len(steps) < 24:
        seen.add((x, y, dx, dy))
        cell = board[x][y]
        steps.append(_step(len(steps), task.get("expected"), task.get("expected"), {"active_x": x, "active_y": y, "beam": {"dx": dx, "dy": dy}}))
        if cell == "T" or cell == "#":
            break
        if cell == "/":
            dx, dy = -dy, -dx
        elif cell == "\\":
            dx, dy = dy, dx
        x += dx; y += dy
    return steps or [_step(0, task.get("expected"), None)]


def _run_match(ctx: dict[str, Any], rng: random.Random) -> dict[str, object]:
    events: list[dict[str, object]] = []
    slots = [slot["key"] for slot in CONFIG["slots"]]
    print_context = {"tick": 0}
    bots = {slot: _build_fn(ctx, slot, events, print_context) for slot in slots}
    if CONFIG["kind"] == "archer_duel_lite":
        result = _archer_duel(slots, bots, events, print_context, rng)
    else:
        result = _crystal_auction(slots, bots, events, print_context, rng)
    team_ids = _team_ids(ctx, slots)
    slot_scores = result["slot_scores"]
    scores = {team_ids[slot]: int(slot_scores[slot]) for slot in slots}
    placements = _placements(team_ids, slot_scores, slots)
    metrics = {**result["metrics"], "slot_scores": slot_scores, "winner_slots": _winner_slots(slot_scores, slots)}
    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})
    payload: dict[str, object] = {"status": "finished", "metrics": metrics, "frames": result["frames"], "events": events, "scores": scores}
    payload["placements"] = placements
    if len(set(placements.values())) != len(placements):
        payload["tie_resolution"] = "explicit_tie"
    return payload


def _build_fn(ctx: dict[str, Any], slot: str, events: list[dict[str, object]], print_context: dict[str, int]) -> tuple[Callable[..., object] | None, str | None]:
    code = ""
    codes = ctx.get("codes_by_slot")
    if isinstance(codes, dict) and isinstance(codes.get(slot), str):
        code = str(codes[slot])
    namespace: dict[str, Any] = {"__builtins__": _builtins(slot, events, print_context)}
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    for name in ("play", "solve", "choose_action", "choose_actions", "choose_target", "choose_item", "choose_potion", "schedule", "decode", "run_tape", "paint", "scan", "build_numbers", "count_plants", "trace", "simulate", "make_plan", "make_move", "bid"):
        candidate = namespace.get(name)
        if callable(candidate):
            return candidate, compile_error
    return None, compile_error


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
        "float": float, "int": int, "isinstance": isinstance, "len": len, "list": list, "max": max,
        "min": min, "print": bot_print, "range": range, "round": round, "set": set, "sorted": sorted,
        "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    }


class _Hero:
    def __init__(self) -> None:
        self.commands: list[str] = []
    def forward(self) -> None: self.commands.append("forward")
    def collect(self) -> None: self.commands.append("collect")
    def attack(self) -> None: self.commands.append("attack")
    def turn_left(self) -> None: self.commands.append("turn_left")
    def turn_right(self) -> None: self.commands.append("turn_right")
    def wait(self) -> None: self.commands.append("wait")


def _call(fn: Callable[..., object] | None, *args: object) -> object:
    if fn is None:
        return None
    for count in range(len(args), -1, -1):
        try:
            return fn(*args[:count])
        except TypeError:
            continue
        except Exception as exc:
            return {"error": str(exc)}
    return None


def _normalize(value: object) -> object:
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    return value


def _score(expected: object, actual: object) -> dict[str, object]:
    actual_norm = _normalize(actual)
    expected_norm = _normalize(expected)
    solved = actual_norm == expected_norm
    correct, total, missing, extra = _compare_value(expected_norm, actual_norm)
    score = 100 if solved else int(100 * correct / max(1, total))
    return {
        "solved": solved,
        "score": score,
        "correct": correct,
        "total": total,
        "missing": missing,
        "extra": extra,
        "expected": expected_norm,
        "actual": actual_norm,
    }


def _measure_value(value: object) -> int:
    if isinstance(value, list):
        return sum(_measure_value(item) for item in value) or 1
    if isinstance(value, dict):
        return sum(_measure_value(item) for item in value.values()) or 1
    return 1


def _compare_value(expected: object, actual: object) -> tuple[int, int, int, int]:
    if isinstance(expected, list) and isinstance(actual, list):
        correct = total = missing = extra = 0
        for index in range(max(len(expected), len(actual))):
            if index >= len(expected):
                size = _measure_value(actual[index])
                total += size
                extra += size
            elif index >= len(actual):
                size = _measure_value(expected[index])
                total += size
                missing += size
            else:
                c, t, m, e = _compare_value(expected[index], actual[index])
                correct += c; total += t; missing += m; extra += e
        return correct, max(1, total), missing, extra
    if isinstance(expected, dict) and isinstance(actual, dict):
        correct = total = missing = extra = 0
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                size = _measure_value(actual[key])
                total += size
                extra += size
            elif key not in actual:
                size = _measure_value(expected[key])
                total += size
                missing += size
            else:
                c, t, m, e = _compare_value(expected[key], actual[key])
                correct += c; total += t; missing += m; extra += e
        return correct, max(1, total), missing, extra
    return (1 if expected == actual else 0), 1, 0, 0


def _build_task(kind: str, rng: random.Random) -> dict[str, object]:
    if kind == "beginner_cave":
        expected = ["forward", "collect", "forward", "attack", "forward", "collect", "forward"]
        return {"goal": "repeat_commands", "expected": expected, "timeline": ["монета", "путь", "монстр", "монета", "пещера"]}
    if kind == "gate_guard":
        colors = ["red", "blue", "black", "green", "blue", "black", "red", "gold"]
        cases = []
        for index, color in enumerate(colors):
            gate = {"id": index, "color": color, "has_key": index % 2 == 0, "trap": color == "black" and index % 3 != 0, "hp": 40 + index * 7}
            if color == "red": expected = "attack"
            elif color == "blue": expected = "use_key" if gate["has_key"] else "wait"
            elif gate["trap"]: expected = "disarm"
            else: expected = "open"
            cases.append({"input": gate, "expected": expected})
        return {"cases": cases}
    if kind == "wall_archer":
        cases = []
        for i in range(8):
            enemy = {"distance": rng.randint(1, 8), "hp": rng.randint(10, 80), "is_aiming": bool(i % 3 == 0)}
            arrows = rng.randint(0, 3)
            hp = rng.randint(20, 90)
            if arrows <= 0: expected = "reload"
            elif enemy["distance"] <= 3: expected = "shoot"
            elif enemy["is_aiming"] and hp < 50: expected = "shield"
            else: expected = "wait"
            cases.append({"enemy": enemy, "arrows": arrows, "hp": hp, "expected": expected})
        return {"cases": cases}
    if kind == "farm_row":
        row = [rng.choice([0, 1, 1]) for _ in range(10)]
        return {"row": row, "expected": ["water" if cell else "skip" for cell in row]}
    if kind == "crystal_corridor":
        corridor = [rng.choice([".", "C", "C"]) for _ in range(8)] + ["#"] + ["C", "."]
        expected: list[str] = []
        for cell in corridor:
            if cell == "#": break
            if cell == "C": expected.append("collect")
            expected.append("move")
        return {"corridor": corridor, "expected": expected}
    if kind == "rune_decoder":
        mapping = {"ᚠ": "forward", "ᚱ": "turn_right", "ᛚ": "turn_left", "ᚲ": "collect", "ᚨ": "attack"}
        runes = "".join(rng.choice(list(mapping)) for _ in range(9))
        return {"runes": runes, "mapping": mapping, "expected": [mapping[ch] for ch in runes]}
    if kind == "miner_backpack":
        ores = [rng.randint(1, 4) for _ in range(9)]
        capacity = 9
        total = count = 0
        for ore in ores:
            if total + ore > capacity: break
            total += ore; count += 1
        return {"ores": ores, "capacity": capacity, "expected": count}
    if kind == "battery_robot_lite":
        cases = []
        for i in range(8):
            state = {"battery": rng.randint(1, 8), "on_charger": bool(i % 4 == 0), "dirty": bool(i % 2 == 0), "front_clear": bool(i % 5 != 0)}
            if state["battery"] <= 2 and state["on_charger"]: expected = "charge"
            elif state["dirty"] and state["battery"] >= 2: expected = "clean"
            elif state["front_clear"] and state["battery"] >= 1: expected = "move"
            else: expected = "wait"
            cases.append({"input": state, "expected": expected})
        return {"cases": cases}
    if kind == "potion_maker":
        resources = {"water": 3, "herb": 4, "crystal": 2, "mushroom": 1}
        recipes = {
            "heal": {"water": 1, "herb": 2, "value": 30},
            "mana": {"water": 1, "crystal": 1, "value": 35},
            "strength": {"herb": 1, "crystal": 2, "value": 45},
            "sleep": {"mushroom": 2, "water": 1, "value": 50},
        }
        expected = max((name for name, recipe in recipes.items() if all(resources.get(k, 0) >= v for k, v in recipe.items() if k != "value")), key=lambda name: recipes[name]["value"])
        return {"resources": resources, "recipes": recipes, "expected": expected}
    if kind == "weakest_enemy":
        enemies = [{"id": f"enemy_{i}", "hp": rng.randint(10, 90), "distance": rng.randint(1, 8)} for i in range(6)]
        return {"enemies": enemies, "expected": min(enemies, key=lambda e: e["hp"])["id"]}
    if kind == "priority_tower":
        enemies = [{"id": f"mob_{i}", "danger": rng.randint(1, 9), "speed": rng.randint(1, 5), "distance": rng.randint(1, 10)} for i in range(6)]
        def value(e: dict[str, int | str]) -> int: return int(e["danger"]) * 3 + int(e["speed"]) * 2 - int(e["distance"])
        return {"enemies": enemies, "expected": max(enemies, key=value)["id"], "formula": "danger*3 + speed*2 - distance"}
    if kind == "hero_inventory":
        inventory = ["rope", "torch", "small_key", "apple", "healing_potion"]
        situations = [
            {"hp": 25, "door": False, "dark": False, "expected": "healing_potion"},
            {"hp": 80, "door": True, "dark": False, "expected": "small_key"},
            {"hp": 80, "door": False, "dark": True, "expected": "torch"},
            {"hp": 80, "door": False, "dark": False, "expected": "apple"},
        ]
        return {"inventory": inventory, "cases": situations}
    if kind == "space_queue":
        ships = [{"id": f"ship_{i}", "priority": rng.randint(1, 5), "fuel": rng.randint(0, 9), "broken": bool(i % 4 == 0)} for i in range(7)]
        expected = [ship["id"] for ship in sorted(ships, key=lambda s: (-int(s["priority"]), int(s["fuel"])))]
        return {"ships": ships, "expected": expected}
    if kind == "command_tape":
        mapping = {"F": "forward", "L": "turn_left", "R": "turn_right", "A": "attack", "C": "collect"}
        tape = "".join(rng.choice(list(mapping)) for _ in range(12))
        return {"tape": tape, "mapping": mapping, "expected": [mapping[ch] for ch in tape]}
    if kind == "pixel_painter":
        palette = {0: "sky", 1: "grass", 2: "stone", 3: "coin"}
        pixels = [[rng.randint(0, 3) for _ in range(5)] for _ in range(6)]
        return {"pixels": pixels, "palette": palette, "expected": [[palette[cell] for cell in col] for col in pixels], "board": pixels}
    if kind == "treasure_scanner":
        board = [[rng.randint(0, 4) for _ in range(5)] for _ in range(6)]
        col_sums = [sum(col) for col in board]
        row_sums = [sum(board[x][y] for x in range(len(board))) for y in range(len(board[0]))]
        best_col = max(range(len(col_sums)), key=lambda x: col_sums[x])
        best_row = max(range(len(row_sums)), key=lambda y: row_sums[y])
        expected = {"axis": "column", "index": best_col, "score": col_sums[best_col]} if col_sums[best_col] >= row_sums[best_row] else {"axis": "row", "index": best_row, "score": row_sums[best_row]}
        return {"board": board, "expected": expected}
    if kind == "minesweeper_numbers":
        mines = [[False for _ in range(5)] for _ in range(6)]
        for x, y in [(1, 1), (3, 2), (4, 4), (0, 3)]: mines[x][y] = True
        expected = _minesweeper(mines)
        return {"mines": mines, "board": [[-1 if mines[x][y] else 0 for y in range(5)] for x in range(6)], "expected": expected}
    if kind == "farm_grid":
        field = [[rng.choice([0, 0, 1]) for _ in range(5)] for _ in range(6)]
        return {"field": field, "board": field, "expected": sum(sum(col) for col in field)}
    if kind == "laser_mirrors":
        board = [list(col) for col in ["....#", "./...", "..\\T.", ".....", ".....", "....."]]
        return {"board": board, "start_x": 0, "start_y": 1, "dx": 1, "dy": 0, "expected": _trace_laser(board, 0, 1, 1, 0)}
    if kind == "gravity_apples":
        board = [list(col) for col in ["A..#.", ".A.#A", "..A..", "#A..A", ".....", "A#..."]]
        return {"board": board, "expected": _settle_apples(board)}
    if kind == "patrol_guard":
        events = [rng.choice(["clear", "clear", "enemy", "lost_route"]) for _ in range(10)]
        expected = ["attack" if e == "enemy" else "return_to_route" if e == "lost_route" else "patrol" for e in events]
        return {"events": events, "expected": expected}
    if kind == "boss_pattern":
        states = ["prepares", "heavy_attack", "rest", "summon"] * 3
        expected = ["attack" if s == "prepares" else "shield" if s == "heavy_attack" else "attack" if s == "rest" else "area_spell" for s in states]
        return {"states": states, "expected": expected}
    raise ValueError(kind)


def _evaluate_task(kind: str, task: dict[str, object], fn: Callable[..., object] | None, events: list[dict[str, object]]) -> dict[str, object]:
    if kind == "beginner_cave":
        hero = _Hero()
        actual = None
        if fn is not None and getattr(fn, "__name__", "") == "play":
            _call(fn, hero)
            actual = hero.commands
        else:
            actual = _call(fn, task)
        return _score(task["expected"], actual)
    if kind in {"gate_guard", "battery_robot_lite"}:
        actual = []
        for case in task["cases"]: actual.append(_call(fn, case["input"]))
        return _score([case["expected"] for case in task["cases"]], actual)
    if kind == "wall_archer":
        actual = []
        for case in task["cases"]: actual.append(_call(fn, case["enemy"], case["arrows"], case["hp"]))
        return _score([case["expected"] for case in task["cases"]], actual)
    if kind == "farm_row": return _score(task["expected"], _call(fn, task["row"]))
    if kind == "crystal_corridor": return _score(task["expected"], _call(fn, task["corridor"]))
    if kind == "rune_decoder": return _score(task["expected"], _call(fn, task["runes"]))
    if kind == "miner_backpack": return _score(task["expected"], _call(fn, task["ores"], task["capacity"]))
    if kind == "potion_maker": return _score(task["expected"], _call(fn, task["resources"], task["recipes"]))
    if kind in {"weakest_enemy", "priority_tower"}: return _score(task["expected"], _call(fn, task["enemies"]))
    if kind == "hero_inventory":
        actual = [_call(fn, task["inventory"], {k: v for k, v in case.items() if k != "expected"}) for case in task["cases"]]
        return _score([case["expected"] for case in task["cases"]], actual)
    if kind == "space_queue": return _score(task["expected"], _call(fn, task["ships"]))
    if kind == "command_tape": return _score(task["expected"], _call(fn, task["tape"]))
    if kind == "pixel_painter": return _score(task["expected"], _call(fn, task["pixels"], task["palette"]))
    if kind == "treasure_scanner": return _score(task["expected"], _call(fn, task["board"]))
    if kind == "minesweeper_numbers": return _score(task["expected"], _call(fn, task["mines"]))
    if kind == "farm_grid": return _score(task["expected"], _call(fn, task["field"]))
    if kind == "laser_mirrors": return _score(task["expected"], _call(fn, task["board"], task["start_x"], task["start_y"], task["dx"], task["dy"]))
    if kind == "gravity_apples": return _score(task["expected"], _call(fn, task["board"]))
    if kind == "patrol_guard": return _score(task["expected"], _call(fn, task["events"]))
    if kind == "boss_pattern":
        actual = [_call(fn, turn + 1, state) for turn, state in enumerate(task["states"])]
        return _score(task["expected"], actual)
    return {"solved": False, "score": 0, "actual": None, "expected": None}


def _minesweeper(mines: list[list[bool]]) -> list[list[int]]:
    width = len(mines); height = len(mines[0]) if width else 0
    out = [[0 for _ in range(height)] for _ in range(width)]
    for x in range(width):
        for y in range(height):
            if mines[x][y]:
                out[x][y] = -1
                continue
            count = 0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0: continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and mines[nx][ny]: count += 1
            out[x][y] = count
    return out


def _trace_laser(board: list[list[str]], x: int, y: int, dx: int, dy: int) -> bool:
    width = len(board); height = len(board[0]) if width else 0
    seen = set()
    while 0 <= x < width and 0 <= y < height and (x, y, dx, dy) not in seen:
        seen.add((x, y, dx, dy))
        cell = board[x][y]
        if cell == "T": return True
        if cell == "#": return False
        if cell == "/": dx, dy = -dy, -dx
        elif cell == "\\": dx, dy = dy, dx
        x += dx; y += dy
    return False


def _settle_apples(board: list[list[str]]) -> list[list[str]]:
    out = [col[:] for col in board]
    width = len(out); height = len(out[0]) if width else 0
    changed = True
    while changed:
        changed = False
        for x in range(width):
            for y in range(height - 2, -1, -1):
                if out[x][y] == "A" and out[x][y + 1] == ".":
                    out[x][y], out[x][y + 1] = ".", "A"
                    changed = True
    return out


def _archer_duel(slots: list[str], bots: dict[str, tuple[Callable[..., object] | None, str | None]], events: list[dict[str, object]], print_context: dict[str, int], rng: random.Random) -> dict[str, object]:
    hp = {slot: 100 for slot in slots}; arrows = {slot: 1 for slot in slots}; aimed = {slot: False for slot in slots}; frames = []
    for turn in range(12):
        print_context["tick"] = turn
        actions = {}
        for slot in slots:
            enemy = slots[1] if slot == slots[0] else slots[0]
            state = {"turn": turn + 1, "hp": hp[slot], "enemy_hp": hp[enemy], "arrows": arrows[slot], "enemy_aimed": aimed[enemy]}
            action = _call(bots[slot][0], state)
            actions[slot] = action if action in {"aim", "shoot", "shield", "reload"} else "aim"
        shields = {slot for slot, action in actions.items() if action == "shield"}
        for slot, action in actions.items():
            enemy = slots[1] if slot == slots[0] else slots[0]
            if action == "reload": arrows[slot] += 1; aimed[slot] = False
            elif action == "aim": aimed[slot] = True
            elif action == "shoot" and arrows[slot] > 0:
                arrows[slot] -= 1
                damage = 35 if aimed[slot] else 20
                if enemy in shields: damage //= 2
                hp[enemy] = max(0, hp[enemy] - damage)
                aimed[slot] = False
            elif action == "shoot":
                aimed[slot] = False
        frames.append({"tick": turn + 1, "phase": "running", "frame": _match_frame({"actions": actions, "hp": hp.copy(), "arrows": arrows.copy(), "aimed": aimed.copy()})})
        if any(value <= 0 for value in hp.values()): break
    slot_scores = {slot: hp[slot] * 2 + arrows[slot] * 5 for slot in slots}
    frames.append({"tick": len(frames) + 1, "phase": "finished", "frame": _match_frame({"hp": hp, "arrows": arrows, "score": slot_scores})})
    return {"slot_scores": slot_scores, "metrics": {"hp": hp, "arrows": arrows}, "frames": frames}


def _crystal_auction(slots: list[str], bots: dict[str, tuple[Callable[..., object] | None, str | None]], events: list[dict[str, object]], print_context: dict[str, int], rng: random.Random) -> dict[str, object]:
    budget = {slot: 60 for slot in slots}; value = {slot: 0 for slot in slots}; frames = []
    crystals = [rng.randint(8, 28) for _ in range(8)]
    for turn, crystal in enumerate(crystals, start=1):
        print_context["tick"] = turn
        bids = {}
        for slot in slots:
            state = {"turn": turn, "crystal_value": crystal, "budget": budget[slot], "my_value": value[slot], "rounds_left": len(crystals) - turn}
            raw = _call(bots[slot][0], state)
            try: bid = int(raw)
            except Exception: bid = 0
            bids[slot] = max(0, min(budget[slot], bid))
        winner = max(slots, key=lambda s: (bids[s], -slots.index(s)))
        if bids[slots[0]] == bids[slots[1]]:
            winner = slots[(turn + crystal) % 2]
        budget[winner] -= bids[winner]
        value[winner] += crystal
        frames.append({"tick": turn, "phase": "running", "frame": _match_frame({"crystal": crystal, "bids": bids, "winner": winner, "budget": budget.copy(), "value": value.copy()})})
    slot_scores = {slot: value[slot] + budget[slot] for slot in slots}
    frames.append({"tick": len(frames) + 1, "phase": "finished", "frame": _match_frame({"budget": budget, "value": value, "score": slot_scores})})
    return {"slot_scores": slot_scores, "metrics": {"budget": budget, "value": value, "crystals": crystals}, "frames": frames}


def _match_frame(payload: dict[str, object]) -> dict[str, object]:
    return {"title": CONFIG["title"], "kind": CONFIG["kind"], "learning_section": CONFIG["learning_section"], "difficulty": CONFIG["difficulty"], **_normalize(payload)}


def _team_ids(ctx: dict[str, Any], slots: list[str]) -> dict[str, str]:
    result = {slot: f"team-{slot}" for slot in slots}
    participants = ctx.get("participants")
    if isinstance(participants, list):
        for item in participants:
            if isinstance(item, dict) and item.get("slot_key") in result and isinstance(item.get("team_id"), str):
                result[str(item["slot_key"])] = str(item["team_id"])
    return result


def _placements(team_ids: dict[str, str], slot_scores: dict[str, int], slots: list[str]) -> dict[str, int]:
    ordered = sorted(slots, key=lambda slot: (-slot_scores[slot], slot))
    placements: dict[str, int] = {}
    last_score = None; last_place = 0
    for index, slot in enumerate(ordered, start=1):
        score = slot_scores[slot]
        place = last_place if score == last_score else index
        placements[team_ids[slot]] = place
        last_score = score; last_place = place
    return placements


def _winner_slots(slot_scores: dict[str, int], slots: list[str]) -> list[str]:
    best = max(slot_scores[slot] for slot in slots)
    return [slot for slot in slots if slot_scores[slot] == best]


def _frame(tick: int, phase: str, task: dict[str, object], status: dict[str, object]) -> dict[str, object]:
    frame = {"title": CONFIG["title"], "kind": CONFIG["kind"], "learning_section": CONFIG["learning_section"], "difficulty": CONFIG["difficulty"], "task": _normalize(task), **_normalize(status)}
    board = task.get("board") or task.get("pixels") or task.get("field")
    if board is not None:
        frame["board"] = _normalize(board)
    return {"tick": tick, "phase": phase, "frame": frame}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
