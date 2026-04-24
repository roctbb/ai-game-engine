import json
import os
from typing import Any


_LANES = 3
_TRACK_LENGTH = 10
_MAX_TICKS = 20
_BASE_HP_START = 30
_TOWER_COST = 5
_ENEMY_HP = 5
_ENEMY_DAMAGE = 3
_ENEMY_SPAWN_PLAN = (0, 1, 2, 1, 0, 2, 2, 1, 0, 1)


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    action_fn, compile_error = _build_player_fn(
        ctx,
        slot_key="defender",
        events=events,
        print_context=print_context,
    )

    towers = [0] * _LANES
    enemies: list[dict[str, int]] = []
    base_hp = _BASE_HP_START
    budget = 15
    towers_built = 0
    enemies_destroyed = 0
    leaks = 0
    frames: list[dict[str, object]] = [
        {
            "tick": 0,
            "phase": "running",
            "frame": {
                "base_hp": base_hp,
                "budget": budget,
                "towers": list(towers),
                "enemies": [],
                "enemies_destroyed": enemies_destroyed,
                "leaks": leaks,
            },
        }
    ]

    for tick in range(_MAX_TICKS):
        if tick < len(_ENEMY_SPAWN_PLAN):
            enemies.append({"lane": _ENEMY_SPAWN_PLAN[tick], "position": 0, "hp": _ENEMY_HP})
            events.append({"type": "enemy_spawned", "tick": tick, "lane": _ENEMY_SPAWN_PLAN[tick]})

        print_context["tick"] = tick
        action = action_fn(_build_state(tick=tick, towers=towers, enemies=enemies, base_hp=base_hp, budget=budget))
        lane = _normalize_lane(action)
        if lane is not None and budget >= _TOWER_COST:
            towers[lane] += 1
            towers_built += 1
            budget -= _TOWER_COST
            events.append({"type": "tower_built", "tick": tick, "lane": lane})

        enemies_destroyed += _apply_tower_damage(towers=towers, enemies=enemies)

        next_enemies: list[dict[str, int]] = []
        for enemy in enemies:
            if enemy["hp"] <= 0:
                continue
            enemy["position"] += 1
            if enemy["position"] >= _TRACK_LENGTH:
                base_hp -= _ENEMY_DAMAGE
                leaks += 1
                events.append({"type": "enemy_leaked", "tick": tick, "lane": enemy["lane"]})
                continue
            next_enemies.append(enemy)
        enemies = next_enemies
        budget += 1
        frames.append(
            {
                "tick": tick + 1,
                "phase": "running",
                "frame": {
                    "base_hp": max(base_hp, 0),
                    "budget": budget,
                    "towers": list(towers),
                    "enemies": [dict(enemy) for enemy in enemies],
                    "enemies_destroyed": enemies_destroyed,
                    "leaks": leaks,
                },
            }
        )

        if base_hp <= 0:
            events.append({"type": "base_destroyed", "tick": tick + 1})
            break

    score = max(0, base_hp + enemies_destroyed * 2 + towers_built - leaks * 2)
    metrics: dict[str, object] = {
        "base_hp": max(base_hp, 0),
        "enemies_destroyed": enemies_destroyed,
        "towers_built": towers_built,
        "leaks": leaks,
        "score": score,
    }
    if compile_error:
        metrics["compile_error"] = compile_error
        events.append({"type": "compile_error", "message": compile_error})

    frames.append(
        {
            "tick": len(frames),
            "phase": "finished",
            "frame": {
                "base_hp": max(base_hp, 0),
                "budget": budget,
                "towers": list(towers),
                "enemies": [dict(enemy) for enemy in enemies],
                "enemies_destroyed": enemies_destroyed,
                "leaks": leaks,
                "score": score,
            },
        }
    )

    return {
        "status": "finished",
        "metrics": metrics,
        "frames": frames,
        "events": events,
        "replay_ref": None,
    }


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
    slot_key: str,
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[callable, str | None]:
    code = ""
    codes = context.get("codes_by_slot")
    if isinstance(codes, dict):
        raw_code = codes.get(slot_key)
        if isinstance(raw_code, str):
            code = raw_code

    namespace: dict[str, Any] = {
        "__builtins__": {
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
            "print": _make_bot_print(events=events, role=slot_key, print_context=print_context),
            "range": range,
            "set": set,
            "str": str,
            "sum": sum,
            "tuple": tuple,
        }
    }
    compile_error: str | None = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:  # pragma: no cover - runtime integration path
            compile_error = str(exc)

    fn = namespace.get("place_tower") or namespace.get("choose_action") or namespace.get("make_move")
    if not callable(fn):
        return lambda _state: 1, compile_error
    return fn, compile_error


def _make_bot_print(
    events: list[dict[str, object]],
    role: str,
    print_context: dict[str, int],
) -> callable:
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


def _build_state(
    tick: int,
    towers: list[int],
    enemies: list[dict[str, int]],
    base_hp: int,
    budget: int,
) -> dict[str, object]:
    return {
        "tick": tick,
        "lanes": _LANES,
        "track_length": _TRACK_LENGTH,
        "base_hp": base_hp,
        "budget": budget,
        "towers": list(towers),
        "enemies": [dict(enemy) for enemy in enemies],
    }


def _normalize_lane(action: object) -> int | None:
    if isinstance(action, bool):
        return None
    if isinstance(action, int) and 0 <= action < _LANES:
        return action
    return None


def _apply_tower_damage(towers: list[int], enemies: list[dict[str, int]]) -> int:
    destroyed = 0
    for lane in range(_LANES):
        damage = towers[lane] * 2
        if damage <= 0:
            continue
        candidate = _find_front_enemy(enemies=enemies, lane=lane)
        if candidate is None:
            continue
        candidate["hp"] -= damage
        if candidate["hp"] <= 0:
            destroyed += 1
    return destroyed


def _find_front_enemy(enemies: list[dict[str, int]], lane: int) -> dict[str, int] | None:
    lane_enemies = [enemy for enemy in enemies if enemy["lane"] == lane]
    if not lane_enemies:
        return None
    lane_enemies.sort(key=lambda item: item["position"], reverse=True)
    return lane_enemies[0]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
