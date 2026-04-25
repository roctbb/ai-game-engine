from __future__ import annotations

import json
import os
from pathlib import Path
import random
import sys
from typing import Any, Callable


_GAME_ROOT = Path(__file__).resolve().parent
if str(_GAME_ROOT) not in sys.path:
    sys.path.insert(0, str(_GAME_ROOT))

from domain.common import Booster, Decision, Point  # noqa: E402
from domain.game import Game  # noqa: E402
from domain.general_player import GeneralPlayer  # noqa: E402
from domain.maps.tanks import TankMap  # noqa: E402


_MAX_TICKS = 120
_SUPPORT_COOLDOWN = 5
_TEAM_PLAYER_ID = "team-player"
_TEAM_ENEMY_ID = "team-bot"

_ACTION_ALIASES = {
    "up": Decision.GO_UP,
    "down": Decision.GO_DOWN,
    "left": Decision.GO_LEFT,
    "right": Decision.GO_RIGHT,
    "go_up": Decision.GO_UP,
    "go_down": Decision.GO_DOWN,
    "go_left": Decision.GO_LEFT,
    "go_right": Decision.GO_RIGHT,
    "fire_up": Decision.FIRE_UP,
    "fire_down": Decision.FIRE_DOWN,
    "fire_left": Decision.FIRE_LEFT,
    "fire_right": Decision.FIRE_RIGHT,
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}

    driver_fn, driver_compile_error = _build_slot_callable(
        ctx=ctx,
        slot_key="driver",
        function_names=("make_choice", "make_move"),
        fallback=_fallback_driver,
        events=events,
        print_context=print_context,
    )
    support_fn, support_compile_error = _build_slot_callable(
        ctx=ctx,
        slot_key="support",
        function_names=("make_support", "choose_support", "make_choice"),
        fallback=_fallback_support,
        events=events,
        print_context=print_context,
    )

    seed = str(ctx.get("run_id") or "tanks_legacy_offline")
    random.seed(seed)

    game = Game()
    TankMap.init(game, players=[])
    player = RuntimeTank(
        slot_key="driver",
        strategy=driver_fn,
        events=events,
        print_context=print_context,
        properties={"team": "Radient", "name": "you"},
    )
    spawn = _pick_spawn(game)
    game.players[(spawn.x, spawn.y)] = player
    player_spawn = (spawn.x, spawn.y)

    frames: list[dict[str, object]] = []
    support_cooldown = 0
    support_invalid_actions = 0
    ticks_played = 0
    winner: str | None = None

    _update_metadata(
        game=game,
        tick=0,
        player=player,
        player_spawn=player_spawn,
        support_cooldown=support_cooldown,
    )
    frames.append(_frame_envelope(tick=0, phase="running", frame=game.as_dict()))

    for tick in range(_MAX_TICKS):
        print_context["tick"] = tick
        ticks_played = tick + 1

        _update_metadata(
            game=game,
            tick=tick,
            player=player,
            player_spawn=player_spawn,
            support_cooldown=support_cooldown,
        )
        support_action = _call_support(
            support_fn=support_fn,
            state=dict(game.metadata),
        )
        if support_action == "boost":
            if support_cooldown == 0:
                player.boosters.append(Booster("speed", 1, 2))
                player.boosters[-1].apply(player)
                support_cooldown = _SUPPORT_COOLDOWN
                events.append({"type": "support_boost", "tick": tick + 1, "message": "Speed boost applied for one move."})
            else:
                support_invalid_actions += 1
                events.append(
                    {
                        "type": "invalid_support_action",
                        "tick": tick + 1,
                        "action": support_action,
                        "message": "Boost is still on cooldown.",
                    }
                )
        elif support_action != "none":
            support_invalid_actions += 1
            events.append(
                {
                    "type": "invalid_support_action",
                    "tick": tick + 1,
                    "action": support_action,
                    "message": "Support action must be 'boost' or 'none'.",
                }
            )

        game.metadata["support"] = {"boost_cooldown": support_cooldown}
        frame = game.make_step()
        _append_legacy_events(events=events, tick=tick + 1, frame=frame)
        frames.append(_frame_envelope(tick=tick + 1, phase="running", frame=frame))

        if support_cooldown > 0:
            support_cooldown -= 1

        if not _is_player_alive(game, player):
            winner = "enemy"
            events.append({"type": "winner", "tick": tick + 1, "winner": winner, "message": "Your tank was destroyed."})
            break
        if _dare_core_destroyed(game):
            winner = "player"
            events.append({"type": "winner", "tick": tick + 1, "winner": winner, "message": "Dare base was destroyed."})
            break

    if winner is None:
        winner = "draw"

    final_frame = game.as_dict()
    frames.append(_frame_envelope(tick=ticks_played, phase="finished", frame=final_frame))

    team_player_id = _resolve_team_player_id(ctx)
    scores = _build_scores(team_player_id=team_player_id, team_enemy_id=_TEAM_ENEMY_ID, winner=winner)
    placements = _build_placements(team_player_id=team_player_id, team_enemy_id=_TEAM_ENEMY_ID, winner=winner)
    is_tie = winner == "draw"

    metrics: dict[str, object] = {
        "ticks_played": ticks_played,
        "winner": winner,
        "draw": is_tie,
        "player_alive": _is_player_alive(game, player),
        "player_position": _player_position_dict(game, player),
        "support_invalid_actions": support_invalid_actions,
        "shots": sum(1 for event in events if event.get("type") == "shot"),
        "deaths": sum(1 for event in events if event.get("type") == "death"),
    }
    if driver_compile_error:
        metrics["compile_error_driver"] = driver_compile_error
        events.append({"type": "compile_error_driver", "message": driver_compile_error})
    if support_compile_error:
        metrics["compile_error_support"] = support_compile_error
        events.append({"type": "compile_error_support", "message": support_compile_error})

    payload: dict[str, object] = {
        "status": "finished",
        "metrics": metrics,
        "frames": frames,
        "events": events,
        "scores": scores,
        "winner_slots": [] if is_tie else ([team_player_id] if winner == "player" else [_TEAM_ENEMY_ID]),
        "is_tie": is_tie,
    }
    run_kind = str(ctx.get("run_kind") or "training_match")
    if run_kind == "competition_match":
        payload["placements"] = placements
        if is_tie:
            payload["tie_resolution"] = "explicit_tie"
    elif run_kind == "training_match":
        payload["placements"] = placements
    else:
        payload["replay_ref"] = None

    return payload


class RuntimeTank(GeneralPlayer):
    def __init__(
        self,
        *,
        slot_key: str,
        strategy: Callable[..., object],
        events: list[dict[str, object]],
        print_context: dict[str, int],
        properties: dict[str, object],
    ):
        super().__init__()
        self.slot_key = slot_key
        self.strategy = strategy
        self.events = events
        self.print_context = print_context
        self.properties.update(properties)

    def as_dict(self, point):
        data = super().as_dict(point)
        data["type"] = "Player"
        return data

    def step(self, point: Point, map_state: object):
        for booster in self.boosters[:]:
            booster.tick()
            if booster.over():
                booster.deapply(self)
                self.boosters.remove(booster)

        choice = _call_driver_strategy(self.strategy, point.x, point.y, map_state)
        if not choice:
            self.history.append("stay")
            return None

        parts = choice.split()
        if not parts or not Decision.has_value(parts[0]):
            self.errors.append(Exception("Invalid choice: " + choice))
            self.history.append("invalid_choice")
            self.events.append(
                {
                    "type": "invalid_driver_action",
                    "tick": int(self.print_context.get("tick", 0)) + 1,
                    "message": str(self.errors[-1]) if self.errors else "Invalid driver action.",
                }
            )
            return None

        self.history.append(choice)
        if parts[0] == Decision.USE.value:
            if len(parts) != 2:
                self.errors.append(Exception("Invalid choice: " + choice))
                self.history.append("invalid_choice")
                return None
            item = self.inventory.pop(parts[1])
            if not item:
                self.errors.append(Exception("No item in inventory: " + choice))
                self.history.append("invalid_choice")
                return None
            item.apply(self)
            return None

        return Decision(parts[0])


def _load_context() -> dict[str, Any]:
    raw = os.getenv("AGP_RUN_CONTEXT")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_slot_callable(
    ctx: dict[str, Any],
    slot_key: str,
    function_names: tuple[str, ...],
    fallback: Callable[..., object],
    events: list[dict[str, object]],
    print_context: dict[str, int],
) -> tuple[Callable[..., object], str | None]:
    code = _code_for_slot(ctx=ctx, slot_key=slot_key)
    namespace: dict[str, Any] = {
        "__name__": f"tanks_slot_{slot_key}",
        "__builtins__": _safe_builtins(
            print_fn=_make_bot_print(events=events, role=slot_key, print_context=print_context)
        )
    }
    compile_error: str | None = None

    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:  # pragma: no cover - runtime path
            compile_error = str(exc)

    for fn_name in function_names:
        candidate = namespace.get(fn_name)
        if callable(candidate):
            return candidate, compile_error

    bot_cls = namespace.get("Bot")
    if isinstance(bot_cls, type):
        try:
            instance = bot_cls()
            for fn_name in function_names:
                method = getattr(instance, fn_name, None)
                if callable(method):
                    return method, compile_error
        except Exception as exc:  # pragma: no cover - runtime path
            compile_error = str(exc)

    return fallback, compile_error


def _safe_builtins(print_fn: Callable[..., None]) -> dict[str, object]:
    return {
        "__build_class__": __build_class__,
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "getattr": getattr,
        "hasattr": hasattr,
        "int": int,
        "isinstance": isinstance,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "object": object,
        "print": print_fn,
        "range": range,
        "reversed": reversed,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
        "Exception": Exception,
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
        for line in message.splitlines() or [""]:
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
    raw = codes.get(slot_key)
    return raw if isinstance(raw, str) else ""


def _call_driver_strategy(strategy: Callable[..., object], x: int, y: int, map_state: object) -> str | None:
    try:
        raw = strategy(x, y, map_state)
    except TypeError:
        try:
            raw = strategy(map_state)
        except Exception:  # pragma: no cover - runtime path
            return None
    except Exception:  # pragma: no cover - runtime path
        return None
    return _normalize_driver_action(raw)


def _normalize_driver_action(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    action = raw.strip().lower()
    if not action or action == "stay":
        return None
    if action.startswith("use "):
        return action
    mapped = _ACTION_ALIASES.get(action)
    return str(mapped.value if isinstance(mapped, Decision) else mapped) if mapped else action


def _call_support(support_fn: Callable[..., object], state: dict[str, object]) -> str:
    try:
        result = support_fn(state)
    except Exception:  # pragma: no cover - runtime path
        return "none"
    if isinstance(result, str):
        lowered = result.strip().lower()
        if lowered in {"none", "boost"}:
            return lowered
    return "none"


def _fallback_driver(x: int, y: int, map_state: object) -> str:
    target = _nearest_target(x=x, y=y, map_state=map_state)
    if target is None:
        return "fire_right"
    tx, ty = target
    if abs(tx - x) >= abs(ty - y) and tx != x:
        return "go_right" if tx > x else "go_left"
    if ty != y:
        return "go_down" if ty > y else "go_up"
    return "fire_right"


def _fallback_support(_state: dict[str, object]) -> str:
    return "none"


def _nearest_target(x: int, y: int, map_state: object) -> tuple[int, int] | None:
    if not isinstance(map_state, list):
        return None
    best: tuple[int, int] | None = None
    best_dist = 10**9
    for tx, column in enumerate(map_state):
        if not isinstance(column, list):
            continue
        for ty, cell in enumerate(column):
            if not isinstance(cell, dict):
                continue
            items = cell.get("items") or []
            obj = cell.get("object")
            is_coin = any(isinstance(item, dict) and item.get("type") == "Coin" for item in items)
            is_enemy_core = isinstance(obj, dict) and obj.get("type") in {"DareAncient", "Tower"}
            if not is_coin and not is_enemy_core:
                continue
            dist = abs(tx - x) + abs(ty - y)
            if dist < best_dist:
                best = (tx, ty)
                best_dist = dist
    return best


def _pick_spawn(game: Game) -> Point:
    for _ in range(2000):
        x = random.randint(0, game.width - 1)
        y = random.randint(0, game.height - 1)
        point = Point(x, y)
        if game.can_move(point) and (x, y) not in game.items and (x, y) not in game.players:
            return point
    for x in range(game.width):
        for y in range(game.height):
            point = Point(x, y)
            if game.can_move(point) and (x, y) not in game.items and (x, y) not in game.players:
                return point
    return Point(0, 0)


def _update_metadata(
    *,
    game: Game,
    tick: int,
    player: RuntimeTank,
    player_spawn: tuple[int, int],
    support_cooldown: int,
) -> None:
    player_pos = _player_position(game, player)
    target = _nearest_target(player_pos[0], player_pos[1], game.get_state()) if player_pos else None
    game.metadata = {
        "tick": tick,
        "map": {"width": game.width, "height": game.height},
        "self": {"x": player_pos[0], "y": player_pos[1]} if player_pos else None,
        "support": {"boost_cooldown": support_cooldown},
        "spawn": {"x": player_spawn[0], "y": player_spawn[1]},
        # Compatibility with the temporary simplified version.
        "flag": {"x": target[0], "y": target[1], "carrier": "none"} if target else {"x": player_spawn[0], "y": player_spawn[1], "carrier": "none"},
        "bases": {"player": {"x": player_spawn[0], "y": player_spawn[1]}},
        "enemy": _nearest_enemy_dict(game=game, player=player),
    }


def _nearest_enemy_dict(game: Game, player: RuntimeTank) -> dict[str, int]:
    player_pos = _player_position(game, player)
    if player_pos is None:
        return {"x": 0, "y": 0}
    px, py = player_pos
    best = None
    best_dist = 10**9
    for (x, y), obj in {**game.players, **game.objects}.items():
        if obj is player:
            continue
        props = getattr(obj, "properties", {})
        if props.get("team") == player.properties.get("team"):
            continue
        if not getattr(obj, "is_flat", False):
            dist = abs(px - x) + abs(py - y)
            if dist < best_dist:
                best = (x, y)
                best_dist = dist
    if best is None:
        return {"x": 0, "y": 0}
    return {"x": best[0], "y": best[1]}


def _append_legacy_events(events: list[dict[str, object]], tick: int, frame: dict[str, object]) -> None:
    for legacy_event in frame.get("events", []):
        if not isinstance(legacy_event, dict):
            continue
        event = dict(legacy_event)
        event["tick"] = tick
        params = event.get("params")
        if isinstance(params, dict) and "message" not in event:
            event["message"] = _event_message(event_type=str(event.get("type") or ""), params=params)
        events.append(event)


def _event_message(event_type: str, params: dict[str, object]) -> str:
    if event_type == "shot":
        return f"Shot from {params.get('from')} to {params.get('to')}."
    if event_type == "death":
        return f"Object destroyed at {params.get('at')}."
    return event_type


def _frame_envelope(tick: int, phase: str, frame: dict[str, object]) -> dict[str, object]:
    return {"tick": tick, "phase": phase, "frame": frame}


def _player_position(game: Game, player: RuntimeTank) -> tuple[int, int] | None:
    for (x, y), candidate in game.players.items():
        if candidate is player:
            return (x, y)
    return None


def _player_position_dict(game: Game, player: RuntimeTank) -> dict[str, int] | None:
    pos = _player_position(game, player)
    return {"x": pos[0], "y": pos[1]} if pos else None


def _is_player_alive(game: Game, player: RuntimeTank) -> bool:
    return _player_position(game, player) is not None


def _dare_core_destroyed(game: Game) -> bool:
    return not any(obj.__class__.__name__ == "DareAncient" for obj in game.objects.values())


def _build_scores(team_player_id: str, team_enemy_id: str, winner: str) -> dict[str, int]:
    if winner == "player":
        return {team_player_id: 3, team_enemy_id: 0}
    if winner == "enemy":
        return {team_player_id: 0, team_enemy_id: 3}
    return {team_player_id: 1, team_enemy_id: 1}


def _build_placements(team_player_id: str, team_enemy_id: str, winner: str) -> dict[str, int]:
    if winner == "player":
        return {team_player_id: 1, team_enemy_id: 2}
    if winner == "enemy":
        return {team_player_id: 2, team_enemy_id: 1}
    return {team_player_id: 1, team_enemy_id: 1}


def _resolve_team_player_id(ctx: dict[str, Any]) -> str:
    team_id = ctx.get("team_id")
    if isinstance(team_id, str) and team_id.strip():
        return team_id
    return _TEAM_PLAYER_ID


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
