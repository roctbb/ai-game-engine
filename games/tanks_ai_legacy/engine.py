from contextlib import contextmanager
import ast
import json
import math
import os
import random
import signal
import traceback
from dataclasses import dataclass, field
from types import FrameType
from typing import Any, Callable, Iterator


_MAP_TEMPLATE = """
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. # # # # # . # # # # . # # # # # .
. # . . . . . . . . . . . . . . # .
. # . . . . . . . . . . . . . . # .
. # . . . . # # # # # # . . . . # .
. # . . . . # . . . . # . . . . # .
. . . . . . . . . . . . . . . . . .
. . . . . . . # . . # . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . # . . # . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . # # . . # # . . . . . .
. # . . . . # . . . . # . . . . # .
. # . . . . . . # # . . . . . . # .
. # . . . . . . # # . . . . . . # .
. # . . . . # . . . . # . . . . # .
. . . . . . # # . . # # . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . # . . # . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . # . . # . . . . . . .
. . . . . . . . . . . . . . . . . .
. # . . . . # . . . . # . . . . # .
. # . . . . # # # # # # . . . . # .
. # . . . . . . . . . . . . . . # .
. # . . . . . . . . . . . . . . # .
. # # # # # . # # # # . # # # # # .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
""".strip()

_MAX_TICKS = 300
_MAX_HEALTH = 50
_STARTING_SHIELD = _MAX_HEALTH // 2
_INITIAL_COINS = 30
_COIN_SPAWN_CHANCE = 0.48
_BOT_TIMEOUT_SECONDS = 0.4
_ACTIONS = {
    "go_up",
    "go_down",
    "go_left",
    "go_right",
    "fire_up",
    "fire_down",
    "fire_left",
    "fire_right",
    "shield",
    "self_destruct",
    "crash",
}
_MOVE_DELTAS = {
    "go_up": (0, -1),
    "go_down": (0, 1),
    "go_left": (-1, 0),
    "go_right": (1, 0),
}
_FIRE_DELTAS = {
    "fire_up": (0, -1),
    "fire_down": (0, 1),
    "fire_left": (-1, 0),
    "fire_right": (1, 0),
}
_ARROWS = {
    "fire_up": "&uarr;",
    "fire_down": "&darr;",
    "fire_left": "&larr;",
    "fire_right": "&rarr;",
}
_FORBIDDEN_NAMES = {
    "eval": "Using eval is forbidden",
    "exec": "Using exec is forbidden",
    "open": "Using open is forbidden",
    "__import__": "Using __import__ is forbidden",
}
_FORBIDDEN_MODULE_PREFIXES = (
    "os",
    "subprocess",
    "socket",
    "requests",
    "http",
    "urllib",
    "pathlib",
)
_ALLOWED_IMPORT_ROOTS = {
    "bisect",
    "collections",
    "copy",
    "functools",
    "heapq",
    "itertools",
    "math",
    "operator",
    "random",
    "statistics",
}


class _TurnTimeout(Exception):
    pass


@dataclass(slots=True)
class BotProgram:
    key: str
    name: str
    code: str
    team_id: str
    code_object: object | None = None
    compile_error: str | None = None


@dataclass(slots=True)
class Tank:
    key: str
    name: str
    team_id: str
    x: int
    y: int
    health: int = _MAX_HEALTH
    shield: int = _STARTING_SHIELD
    coins: int = 0
    hits: int = 0
    crashes: int = 0
    errors: int = 0
    steps: int = 0
    shots: int = 0
    history: list[str] = field(default_factory=list)
    last_error: str = ""

    @property
    def score(self) -> int:
        return self.coins * 50 + self.hits * 20 + len(self.history) - self.crashes * 5


@dataclass(slots=True)
class Arena:
    base: list[list[str]]
    tanks: dict[str, Tank]
    active_order: list[str]
    coins: set[tuple[int, int]]
    rng: random.Random

    @property
    def width(self) -> int:
        return len(self.base)

    @property
    def height(self) -> int:
        return len(self.base[0]) if self.base else 0


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    seed = str(ctx.get("run_id") or "tanks_ai_legacy_offline")
    rng = random.Random(seed)
    random.seed(seed)
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}

    programs = _build_programs(ctx)
    arena = _build_arena(programs=programs, rng=rng)
    frames = [_frame_envelope(0, "running", arena, actions={}, explosions=set())]
    ticks_played = 0

    for tick in range(_MAX_TICKS):
        if not arena.active_order:
            break
        print_context["tick"] = tick
        ticks_played = tick + 1
        _maybe_spawn_coin(arena)

        field = _bot_field(arena)
        actions: dict[str, str] = {}
        for key in list(arena.active_order):
            tank = arena.tanks[key]
            program = programs[key]
            choice = _choose_action(program, tank, field, events, print_context)
            actions[key] = choice

        _apply_moves(arena, actions)
        explosions = _apply_attacks_and_explosions(arena, actions, events, tick + 1)
        _record_actions(arena, actions, events, tick + 1)
        _remove_dead(arena, events, tick + 1, explosions)
        frames.append(_frame_envelope(tick + 1, "running", arena, actions=actions, explosions=explosions))

    scores = {tank.team_id: max(0, tank.score) for tank in arena.tanks.values()}
    placements = _placements(arena.tanks.values())
    winner_tanks = _winner_tanks(arena.tanks.values())
    winner_team_ids = [tank.team_id for tank in winner_tanks]
    is_tie = len(winner_team_ids) > 1
    metrics: dict[str, object] = {
        "ticks_played": ticks_played,
        "winner_names": [tank.name for tank in winner_tanks],
        "winner_team_ids": winner_team_ids,
        "is_tie": is_tie,
        "players_total": len(arena.tanks),
        "players_alive": len(arena.active_order),
        "coins_spawned_initially": _INITIAL_COINS,
        "coins_left": len(arena.coins),
        "score_formula": "coins * 50 + hits * 20 + turns_alive - crashes * 5",
        "players": [_tank_metrics(tank) for tank in sorted(arena.tanks.values(), key=lambda item: item.score, reverse=True)],
    }
    compile_errors = {program.key: program.compile_error for program in programs.values() if program.compile_error}
    if compile_errors:
        metrics["compile_errors"] = compile_errors
    frames.append(_frame_envelope(ticks_played, "finished", arena, actions={}, explosions=set()))

    payload: dict[str, object] = {
        "status": "finished",
        "metrics": metrics,
        "frames": frames,
        "events": events,
        "scores": scores,
        "winner_slots": winner_team_ids,
        "is_tie": is_tie,
    }
    if str(ctx.get("run_kind") or "training_match") == "competition_match":
        payload["placements"] = placements
        if len(set(placements.values())) < len(placements):
            payload["tie_resolution"] = "explicit_tie"
    elif str(ctx.get("run_kind") or "training_match") == "training_match":
        payload["placements"] = placements
    else:
        payload["replay_ref"] = None
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


def _build_programs(ctx: dict[str, Any]) -> dict[str, BotProgram]:
    participant_programs = _participant_programs(ctx)
    if participant_programs:
        return participant_programs

    team_id = str(ctx.get("team_id") or "team-player")
    display_name = _display_name(ctx.get("team_name") or ctx.get("display_name") or ctx.get("requested_by"), "Игрок")
    code = ""
    codes_by_slot = ctx.get("codes_by_slot")
    if isinstance(codes_by_slot, dict) and isinstance(codes_by_slot.get("bot"), str):
        code = str(codes_by_slot["bot"])
    if not code.strip():
        code = _RANDOM_BOT_CODE

    raw_programs = [
        BotProgram("player", display_name, code, team_id),
    ]
    return _compile_programs(raw_programs)


def _participant_programs(ctx: dict[str, Any]) -> dict[str, BotProgram]:
    participants = ctx.get("participants")
    if not isinstance(participants, list) or not participants:
        return {}
    raw_programs: list[BotProgram] = []
    for index, item in enumerate(participants, start=1):
        if not isinstance(item, dict):
            continue
        team_id = str(item.get("team_id") or f"team-{index}")
        name = _display_name(
            item.get("display_name") or item.get("captain_user_id") or item.get("name"),
            f"Игрок {index}",
        )
        code = ""
        codes_by_slot = item.get("codes_by_slot")
        if isinstance(codes_by_slot, dict) and isinstance(codes_by_slot.get("bot"), str):
            code = str(codes_by_slot["bot"])
        if not code.strip():
            code = _RANDOM_BOT_CODE
        raw_programs.append(BotProgram(f"player_{index}", name, code, team_id))
    return _compile_programs(raw_programs)


def _display_name(raw: object, fallback: str) -> str:
    if isinstance(raw, str) and raw.strip():
        value = raw.strip()
        return value[:-5] if value.endswith(" team") and len(value) > 5 else value
    return fallback


def _compile_programs(raw_programs: list[BotProgram]) -> dict[str, BotProgram]:
    programs: dict[str, BotProgram] = {}
    for program in raw_programs:
        try:
            _assert_code_safe(program.code)
            program.code_object = compile(program.code, f"<{program.key}>", "exec")
        except Exception as exc:
            program.compile_error = str(exc)
            program.code_object = None
        programs[program.key] = program
    return programs


def _assert_code_safe(code: str) -> None:
    tree = ast.parse(code)

    class SafeCodeChecker(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> Any:
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_NAMES:
                raise ValueError(_FORBIDDEN_NAMES[node.func.id])
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> Any:
            for alias in node.names:
                _assert_module_allowed(alias.name)
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
            if node.module:
                _assert_module_allowed(node.module)
            self.generic_visit(node)

    SafeCodeChecker().visit(tree)


def _assert_module_allowed(module_name: str) -> None:
    root = module_name.split(".", 1)[0]
    if module_name.startswith(_FORBIDDEN_MODULE_PREFIXES) or root not in _ALLOWED_IMPORT_ROOTS:
        raise ValueError(f"Importing module {module_name!r} is forbidden")


def _build_arena(programs: dict[str, BotProgram], rng: random.Random) -> Arena:
    base = _parse_map()
    arena = Arena(base=base, tanks={}, active_order=[], coins=set(), rng=rng)
    occupied: set[tuple[int, int]] = set()
    for key, program in programs.items():
        x, y = _random_empty_cell(arena, occupied)
        occupied.add((x, y))
        arena.tanks[key] = Tank(key=key, name=program.name, team_id=program.team_id, x=x, y=y)
        arena.active_order.append(key)
    for _ in range(_INITIAL_COINS):
        x, y = _random_empty_cell(arena, occupied | arena.coins)
        arena.coins.add((x, y))
    return arena


def _parse_map() -> list[list[str]]:
    return [line.split(" ") for line in _MAP_TEMPLATE.splitlines()]


def _random_empty_cell(arena: Arena, occupied: set[tuple[int, int]]) -> tuple[int, int]:
    while True:
        x = arena.rng.randint(0, arena.width - 1)
        y = arena.rng.randint(0, arena.height - 1)
        if arena.base[x][y] == "." and (x, y) not in occupied:
            return x, y


def _maybe_spawn_coin(arena: Arena) -> None:
    if arena.rng.random() >= _COIN_SPAWN_CHANCE:
        return
    occupied = {(tank.x, tank.y) for key, tank in arena.tanks.items() if key in arena.active_order}
    for _ in range(10):
        x = arena.rng.randint(0, arena.width - 1)
        y = arena.rng.randint(0, arena.height - 1)
        if arena.base[x][y] == "." and (x, y) not in occupied and (x, y) not in arena.coins:
            arena.coins.add((x, y))
            return


def _choose_action(
    program: BotProgram,
    tank: Tank,
    field_value: list[list[object]],
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> str:
    if program.compile_error or program.code_object is None:
        tank.crashes += 1
        tank.last_error = program.compile_error or "compile_error"
        return "crash"
    namespace: dict[str, Any] = {
        "__name__": f"tanks_ai_legacy_{program.key}",
        "__builtins__": _safe_builtins(events, program.key, print_context),
    }
    try:
        with _time_limit(_BOT_TIMEOUT_SECONDS):
            exec(program.code_object, namespace, namespace)
            fn = namespace.get("make_choice")
            if not callable(fn):
                raise RuntimeError("make_choice is not defined")
            choice = fn(tank.x, tank.y, _clone_field(field_value))
    except _TurnTimeout:
        tank.crashes += 1
        tank.last_error = "timeout"
        events.append({"type": "bot_timeout", "tick": print_context["tick"] + 1, "role": program.key})
        return "crash"
    except Exception as exc:
        tank.crashes += 1
        tank.last_error = f"{exc} {traceback.format_exc(limit=3)}"
        events.append({"type": "bot_crash", "tick": print_context["tick"] + 1, "role": program.key, "message": str(exc)})
        return "crash"
    return choice if isinstance(choice, str) else str(choice)


@contextmanager
def _time_limit(seconds: float) -> Iterator[None]:
    previous_handler = signal.getsignal(signal.SIGALRM)

    def handle_timeout(_signum: int, _frame: FrameType | None) -> None:
        raise _TurnTimeout()

    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _safe_builtins(
    events: list[dict[str, object]],
    role: str,
    print_context: dict[str, int],
) -> dict[str, object]:
    def bot_print(*values: object, sep: str = " ", end: str = "\n", file: object | None = None, flush: bool = False) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message += end
        for line in message.splitlines() or [""]:
            events.append({"type": "bot_print", "tick": int(print_context.get("tick", 0)), "role": role, "message": line})

    def safe_import(name: str, globals_value: object = None, locals_value: object = None, fromlist: tuple[str, ...] = (), level: int = 0) -> object:
        if level != 0:
            raise ImportError("Relative imports are forbidden")
        _assert_module_allowed(name)
        return __import__(name, globals_value, locals_value, fromlist, level)

    return {
        "__import__": safe_import,
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "int": int,
        "isinstance": isinstance,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "print": bot_print,
        "range": range,
        "reversed": reversed,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }


def _clone_field(field_value: list[list[object]]) -> list[list[object]]:
    cloned: list[list[object]] = []
    for column in field_value:
        new_column: list[object] = []
        for cell in column:
            if isinstance(cell, dict):
                new_cell = dict(cell)
                if isinstance(new_cell.get("history"), list):
                    new_cell["history"] = list(new_cell["history"])
                new_column.append(new_cell)
            else:
                new_column.append(cell)
        cloned.append(new_column)
    return cloned


def _bot_field(arena: Arena) -> list[list[object]]:
    occupied = {(tank.x, tank.y): tank for key, tank in arena.tanks.items() if key in arena.active_order}
    field_value: list[list[object]] = [[0 for _ in range(arena.height)] for _ in range(arena.width)]
    for x in range(arena.width):
        for y in range(arena.height):
            if arena.base[x][y] == "#":
                field_value[x][y] = -1
            elif (x, y) in arena.coins:
                field_value[x][y] = 1
            elif (x, y) in occupied:
                tank = occupied[(x, y)]
                field_value[x][y] = {
                    "name": tank.name,
                    "life": tank.health,
                    "shield": tank.shield,
                    "score": tank.score,
                    "history": list(tank.history),
                }
    return field_value


def _apply_moves(arena: Arena, actions: dict[str, str]) -> None:
    occupied = {(tank.x, tank.y): key for key, tank in arena.tanks.items() if key in arena.active_order}
    for key in list(arena.active_order):
        tank = arena.tanks[key]
        action = actions.get(key, "")
        if action not in _MOVE_DELTAS:
            continue
        tank.steps += 1
        dx, dy = _MOVE_DELTAS[action]
        nx, ny = tank.x + dx, tank.y + dy
        if not _inside(arena, nx, ny) or arena.base[nx][ny] == "#" or (nx, ny) in occupied:
            continue
        del occupied[(tank.x, tank.y)]
        tank.x = nx
        tank.y = ny
        occupied[(tank.x, tank.y)] = key
        if (nx, ny) in arena.coins:
            tank.coins += 1
            arena.coins.remove((nx, ny))


def _apply_attacks_and_explosions(
    arena: Arena,
    actions: dict[str, str],
    events: list[dict[str, object]],
    tick: int,
) -> set[tuple[int, int]]:
    explosions: set[tuple[int, int]] = set()
    for key in list(arena.active_order):
        tank = arena.tanks[key]
        action = actions.get(key, "")
        if action in _FIRE_DELTAS:
            tank.shots += 1
            target = _fire_target(arena, tank.x, tank.y, action)
            if target:
                hit_key = _tank_at(arena, *target)
                if hit_key:
                    actual = _apply_damage(arena.tanks[hit_key], 1, actions.get(hit_key) == "shield")
                    if actual > 0:
                        tank.hits += 1
                    events.append({"type": "hit", "tick": tick, "attacker": key, "target": hit_key, "damage": actual})
        elif action == "self_destruct":
            explosions.add((tank.x, tank.y))
            for tx, ty in _self_destruct_cells(arena, tank.x, tank.y):
                explosions.add((tx, ty))
                hit_key = _tank_at(arena, tx, ty)
                if hit_key and hit_key != key:
                    actual = _apply_damage(arena.tanks[hit_key], 3, actions.get(hit_key) == "shield")
                    if actual > 0:
                        tank.hits += 1
                    events.append({"type": "blast_hit", "tick": tick, "attacker": key, "target": hit_key, "damage": actual})
            tank.health = 0
            events.append({"type": "self_destruct", "tick": tick, "role": key})
    return explosions


def _record_actions(
    arena: Arena,
    actions: dict[str, str],
    events: list[dict[str, object]],
    tick: int,
) -> None:
    for key in list(arena.active_order):
        tank = arena.tanks[key]
        action = actions.get(key, "")
        if action in _ACTIONS:
            tank.history.append(action)
            events.append({"type": "action", "tick": tick, "role": key, "action": action})
        else:
            tank.errors += 1
            tank.history.append("error")
            events.append({"type": "invalid_action", "tick": tick, "role": key, "action": repr(action)})


def _remove_dead(
    arena: Arena,
    events: list[dict[str, object]],
    tick: int,
    explosions: set[tuple[int, int]],
) -> None:
    next_order: list[str] = []
    for key in arena.active_order:
        tank = arena.tanks[key]
        if tank.health <= 0:
            explosions.add((tank.x, tank.y))
            events.append({"type": "death", "tick": tick, "role": key, "x": tank.x, "y": tank.y})
        else:
            next_order.append(key)
    arena.active_order = next_order


def _apply_damage(target: Tank, damage: int, shield_active: bool) -> int:
    if shield_active and target.shield > 0:
        absorbed = min(damage, target.shield)
        target.shield -= absorbed
        damage -= absorbed
    target.health -= damage
    return damage


def _fire_target(arena: Arena, x: int, y: int, action: str) -> tuple[int, int] | None:
    dx, dy = _FIRE_DELTAS[action]
    cx, cy = x + dx, y + dy
    while _inside(arena, cx, cy):
        if arena.base[cx][cy] == "#" or (cx, cy) in arena.coins:
            return None
        if _tank_at(arena, cx, cy):
            return cx, cy
        cx += dx
        cy += dy
    return None


def _self_destruct_cells(arena: Arena, x: int, y: int) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx == 0 and dy == 0:
                continue
            tx, ty = x + dx, y + dy
            if not _inside(arena, tx, ty):
                continue
            blocked = False
            steps = max(abs(dx), abs(dy))
            for step in range(1, steps):
                cx = x + round(dx * step / steps)
                cy = y + round(dy * step / steps)
                if arena.base[cx][cy] == "#":
                    blocked = True
                    break
            if not blocked:
                cells.append((tx, ty))
    return cells


def _tank_at(arena: Arena, x: int, y: int) -> str | None:
    for key in arena.active_order:
        tank = arena.tanks[key]
        if tank.x == x and tank.y == y:
            return key
    return None


def _inside(arena: Arena, x: int, y: int) -> bool:
    return 0 <= x < arena.width and 0 <= y < arena.height


def _frame_envelope(
    tick: int,
    phase: str,
    arena: Arena,
    actions: dict[str, str],
    explosions: set[tuple[int, int]],
) -> dict[str, object]:
    return {"tick": tick, "phase": phase, "frame": _render_frame(arena, tick, phase, actions, explosions)}


def _render_frame(
    arena: Arena,
    tick: int,
    phase: str,
    actions: dict[str, str],
    explosions: set[tuple[int, int]],
) -> dict[str, object]:
    grid: list[list[object]] = [[arena.base[x][y] for y in range(arena.height)] for x in range(arena.width)]
    for x, y in arena.coins:
        grid[x][y] = "@"
    for key in arena.active_order:
        tank = arena.tanks[key]
        grid[tank.x][tank.y] = {
            "name": tank.name,
            "life": tank.health,
            "hit": 0,
            "shield": tank.shield,
            "shielding": 1 if actions.get(key) == "shield" and tank.shield > 0 else 0,
            "score": tank.score,
        }
    for key, action in actions.items():
        if action in _FIRE_DELTAS and key in arena.active_order:
            tank = arena.tanks[key]
            _paint_ray(arena, grid, tank.x, tank.y, action)
    for x, y in explosions:
        if _inside(arena, x, y) and grid[x][y] in (".", "@"):
            grid[x][y] = "*"
    return {
        "map": grid,
        "board": _bot_field(arena),
        "width": arena.width,
        "height": arena.height,
        "tick": tick,
        "phase": phase,
        "players": [_tank_metrics(tank) for tank in arena.tanks.values()],
        "alive": list(arena.active_order),
    }


def _paint_ray(arena: Arena, grid: list[list[object]], x: int, y: int, action: str) -> None:
    dx, dy = _FIRE_DELTAS[action]
    cx, cy = x + dx, y + dy
    while _inside(arena, cx, cy):
        cell = grid[cx][cy]
        if cell == "#" or cell == "@":
            break
        if isinstance(cell, dict):
            cell["hit"] = 1
            break
        if cell in (".", "*"):
            grid[cx][cy] = _ARROWS[action]
        cx += dx
        cy += dy


def _tank_metrics(tank: Tank) -> dict[str, object]:
    return {
        "key": tank.key,
        "name": tank.name,
        "team_id": tank.team_id,
        "x": tank.x,
        "y": tank.y,
        "life": tank.health,
        "shield": tank.shield,
        "coins": tank.coins,
        "hits": tank.hits,
        "shots": tank.shots,
        "steps": tank.steps,
        "crashes": tank.crashes,
        "errors": tank.errors,
        "score": max(0, tank.score),
        "alive": tank.health > 0,
    }


def _placements(tanks: Iterator[Tank] | list[Tank]) -> dict[str, int]:
    ordered = sorted(tanks, key=lambda tank: tank.score, reverse=True)
    result: dict[str, int] = {}
    last_score: int | None = None
    last_place = 0
    for index, tank in enumerate(ordered, start=1):
        if tank.score != last_score:
            last_place = index
            last_score = tank.score
        result[tank.team_id] = last_place
    return result


def _winner_tanks(tanks: Iterator[Tank] | list[Tank]) -> list[Tank]:
    tank_list = list(tanks)
    best = max((tank.score for tank in tank_list), default=0)
    return [tank for tank in tank_list if tank.score == best]


_RANDOM_BOT_CODE = """
import random

def make_choice(x, y, field):
    return random.choice([
        "go_left", "go_right", "go_up", "go_down",
        "fire_left", "fire_right", "fire_up", "fire_down",
    ])
""".strip()


_MINER_BOT_CODE = """
from collections import deque

def make_choice(start_x, start_y, field):
    width = len(field)
    height = len(field[0]) if width else 0
    queue = deque([(start_x, start_y, [])])
    visited = {(start_x, start_y)}
    moves = [
        ("go_right", 1, 0),
        ("go_down", 0, 1),
        ("go_left", -1, 0),
        ("go_up", 0, -1),
    ]
    while queue:
        x, y, path = queue.popleft()
        if field[x][y] == 1 and path:
            return path[0]
        for action, dx, dy in moves:
            nx, ny = x + dx, y + dy
            if nx < 0 or ny < 0 or nx >= width or ny >= height or (nx, ny) in visited:
                continue
            cell = field[nx][ny]
            if cell == -1 or isinstance(cell, dict):
                continue
            visited.add((nx, ny))
            queue.append((nx, ny, path + [action]))
    return "fire_up"
""".strip()


_SHOOTER_BOT_CODE = """
def make_choice(x, y, field):
    width = len(field)
    height = len(field[0]) if width else 0
    rays = [
        ("fire_left", -1, 0),
        ("fire_right", 1, 0),
        ("fire_up", 0, -1),
        ("fire_down", 0, 1),
    ]
    for action, dx, dy in rays:
        cx, cy = x + dx, y + dy
        while 0 <= cx < width and 0 <= cy < height:
            if field[cx][cy] == -1 or field[cx][cy] == 1:
                break
            if isinstance(field[cx][cy], dict):
                return action
            cx += dx
            cy += dy
    return "go_right"
""".strip()


_SHIELD_BOT_CODE = """
def make_choice(x, y, field):
    me = field[x][y]
    if isinstance(me, dict) and me.get("life", 0) < 20 and me.get("shield", 0) > 0:
        return "shield"
    return "fire_right"
""".strip()


_KAMIKAZE_BOT_CODE = """
def make_choice(x, y, field):
    width = len(field)
    height = len(field[0]) if width else 0
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx == 0 and dy == 0:
                continue
            tx, ty = x + dx, y + dy
            if 0 <= tx < width and 0 <= ty < height and isinstance(field[tx][ty], dict):
                return "self_destruct"
    return "go_left"
""".strip()


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
