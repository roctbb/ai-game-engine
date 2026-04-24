from __future__ import annotations

import json
import os
from typing import Any, Callable


_WIDTH = 9
_HEIGHT = 7
_MAX_TICKS = 80
_PLAYER_START = (1, 3)
_ENEMY_START = (7, 3)
_FLAG_START = (4, 3)
_ACTIONS = {"up", "down", "left", "right", "stay"}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    events: list[dict[str, object]] = []
    print_context = {"tick": 0}
    driver_fn, driver_compile_error = _build_slot_callable(
        ctx=ctx,
        slot_key="driver",
        function_names=("make_choice", "make_move"),
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

    player_pos = list(_PLAYER_START)
    enemy_pos = list(_ENEMY_START)
    player_base = _PLAYER_START
    enemy_base = _ENEMY_START
    flag_pos = list(_FLAG_START)
    carrier: str | None = None
    winner: str | None = None

    player_invalid_actions = 0
    enemy_invalid_actions = 0
    support_invalid_actions = 0
    boost_cooldown = 0
    ticks_played = 0
    frames: list[dict[str, object]] = [
        {
            "tick": 0,
            "phase": "running",
            "frame": {
                "player": {"x": player_pos[0], "y": player_pos[1]},
                "enemy": {"x": enemy_pos[0], "y": enemy_pos[1]},
                "flag": {"x": flag_pos[0], "y": flag_pos[1], "carrier": carrier or "none"},
                "boost_cooldown": boost_cooldown,
                "winner": "none",
            },
        }
    ]

    for tick in range(_MAX_TICKS):
        print_context["tick"] = tick
        ticks_played = tick + 1
        state = _build_state(
            tick=tick,
            player_pos=player_pos,
            enemy_pos=enemy_pos,
            flag_pos=flag_pos,
            carrier=carrier,
            player_base=player_base,
            enemy_base=enemy_base,
            boost_cooldown=boost_cooldown,
        )

        support_action = _call_support(support_fn=support_fn, state=state)
        use_boost = False
        if support_action == "boost":
            if boost_cooldown == 0:
                use_boost = True
                boost_cooldown = 4
                events.append({"type": "support_boost", "tick": tick + 1})
            else:
                support_invalid_actions += 1
                events.append({"type": "invalid_support_action", "tick": tick + 1, "action": support_action})
        elif support_action != "none":
            support_invalid_actions += 1
            events.append({"type": "invalid_support_action", "tick": tick + 1, "action": support_action})

        player_action = _call_driver(driver_fn=driver_fn, x=player_pos[0], y=player_pos[1], state=state)
        player_steps = 2 if use_boost else 1
        if not _apply_action(player_pos, player_action, steps=player_steps):
            player_invalid_actions += 1
            events.append({"type": "invalid_driver_action", "tick": tick + 1, "action": player_action})

        enemy_action = _enemy_policy(enemy_pos=enemy_pos, carrier=carrier, flag_pos=flag_pos, enemy_base=enemy_base)
        if not _apply_action(enemy_pos, enemy_action, steps=1):
            enemy_invalid_actions += 1
            events.append({"type": "invalid_enemy_action", "tick": tick + 1, "action": enemy_action})

        if boost_cooldown > 0:
            boost_cooldown -= 1

        carrier, flag_pos = _resolve_flag_logic(
            player_pos=player_pos,
            enemy_pos=enemy_pos,
            flag_pos=flag_pos,
            carrier=carrier,
            player_base=player_base,
            enemy_base=enemy_base,
        )
        events.append(
            {
                "type": "tick_resolved",
                "tick": tick + 1,
                "player": {"x": player_pos[0], "y": player_pos[1]},
                "enemy": {"x": enemy_pos[0], "y": enemy_pos[1]},
                "flag": {"x": flag_pos[0], "y": flag_pos[1], "carrier": carrier or "none"},
            }
        )

        if carrier == "player" and tuple(player_pos) == player_base:
            winner = "player"
            events.append({"type": "winner", "tick": tick + 1, "winner": winner})
            frames.append(
                {
                    "tick": tick + 1,
                    "phase": "running",
                    "frame": {
                        "player": {"x": player_pos[0], "y": player_pos[1]},
                        "enemy": {"x": enemy_pos[0], "y": enemy_pos[1]},
                        "flag": {"x": flag_pos[0], "y": flag_pos[1], "carrier": carrier or "none"},
                        "boost_cooldown": boost_cooldown,
                        "winner": winner,
                    },
                }
            )
            break
        if carrier == "enemy" and tuple(enemy_pos) == enemy_base:
            winner = "enemy"
            events.append({"type": "winner", "tick": tick + 1, "winner": winner})
            frames.append(
                {
                    "tick": tick + 1,
                    "phase": "running",
                    "frame": {
                        "player": {"x": player_pos[0], "y": player_pos[1]},
                        "enemy": {"x": enemy_pos[0], "y": enemy_pos[1]},
                        "flag": {"x": flag_pos[0], "y": flag_pos[1], "carrier": carrier or "none"},
                        "boost_cooldown": boost_cooldown,
                        "winner": winner,
                    },
                }
            )
            break
        frames.append(
            {
                "tick": tick + 1,
                "phase": "running",
                "frame": {
                    "player": {"x": player_pos[0], "y": player_pos[1]},
                    "enemy": {"x": enemy_pos[0], "y": enemy_pos[1]},
                    "flag": {"x": flag_pos[0], "y": flag_pos[1], "carrier": carrier or "none"},
                    "boost_cooldown": boost_cooldown,
                    "winner": winner or "none",
                },
            }
        )

    team_player_id = _resolve_team_player_id(ctx)
    team_enemy_id = "team-bot"
    scores = _build_scores(team_player_id=team_player_id, team_enemy_id=team_enemy_id, winner=winner)
    placements = _build_placements(team_player_id=team_player_id, team_enemy_id=team_enemy_id, winner=winner)

    metrics: dict[str, object] = {
        "ticks_played": ticks_played,
        "winner": winner or "draw",
        "player_invalid_actions": player_invalid_actions,
        "enemy_invalid_actions": enemy_invalid_actions,
        "support_invalid_actions": support_invalid_actions,
        "flag_carrier_final": carrier or "none",
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
    }
    run_kind = str(ctx.get("run_kind") or "training_match")
    if run_kind == "competition_match":
        payload["scores"] = scores
        payload["placements"] = placements
        if winner is None:
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
                "player": {"x": player_pos[0], "y": player_pos[1]},
                "enemy": {"x": enemy_pos[0], "y": enemy_pos[1]},
                "flag": {"x": flag_pos[0], "y": flag_pos[1], "carrier": carrier or "none"},
                "boost_cooldown": boost_cooldown,
                "winner": winner or "draw",
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


def _build_slot_callable(
    ctx: dict[str, Any],
    slot_key: str,
    function_names: tuple[str, ...],
    fallback: Callable[..., object] | None = None,
    events: list[dict[str, object]] | None = None,
    print_context: dict[str, int] | None = None,
) -> tuple[Callable[..., object], str | None]:
    code = _code_for_slot(ctx=ctx, slot_key=slot_key)
    namespace: dict[str, Any] = {
        "__builtins__": _safe_builtins(
            print_fn=_make_bot_print(
                events=events if events is not None else [],
                role=slot_key,
                print_context=print_context if print_context is not None else {"tick": 0},
            ),
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

    return (fallback or _fallback_driver), compile_error


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
    raw = codes.get(slot_key)
    return raw if isinstance(raw, str) else ""


def _build_state(
    tick: int,
    player_pos: list[int],
    enemy_pos: list[int],
    flag_pos: list[int],
    carrier: str | None,
    player_base: tuple[int, int],
    enemy_base: tuple[int, int],
    boost_cooldown: int,
) -> dict[str, object]:
    return {
        "tick": tick,
        "map": {"width": _WIDTH, "height": _HEIGHT},
        "self": {"x": player_pos[0], "y": player_pos[1]},
        "enemy": {"x": enemy_pos[0], "y": enemy_pos[1]},
        "flag": {"x": flag_pos[0], "y": flag_pos[1], "carrier": carrier or "none"},
        "bases": {
            "player": {"x": player_base[0], "y": player_base[1]},
            "enemy": {"x": enemy_base[0], "y": enemy_base[1]},
        },
        "support": {"boost_cooldown": boost_cooldown},
    }


def _call_driver(driver_fn: Callable[..., object], x: int, y: int, state: dict[str, object]) -> str:
    try:
        result = driver_fn(x, y, state)
    except TypeError:
        try:
            result = driver_fn(state)
        except Exception:  # pragma: no cover - runtime path
            return "stay"
    except Exception:  # pragma: no cover - runtime path
        return "stay"
    return _normalize_action(result)


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


def _normalize_action(raw: object) -> str:
    if isinstance(raw, str):
        action = raw.strip().lower()
        if action in _ACTIONS:
            return action
    return "stay"


def _apply_action(position: list[int], action: str, steps: int) -> bool:
    if action not in _ACTIONS:
        return False
    moved = True
    for _ in range(max(steps, 1)):
        x, y = position
        if action == "up":
            y -= 1
        elif action == "down":
            y += 1
        elif action == "left":
            x -= 1
        elif action == "right":
            x += 1
        else:
            continue
        if x < 0 or y < 0 or x >= _WIDTH or y >= _HEIGHT:
            moved = False
            continue
        position[0] = x
        position[1] = y
    return moved


def _enemy_policy(enemy_pos: list[int], carrier: str | None, flag_pos: list[int], enemy_base: tuple[int, int]) -> str:
    if carrier == "enemy":
        target = enemy_base
    else:
        target = (flag_pos[0], flag_pos[1])
    return _move_towards(enemy_pos=enemy_pos, target=target)


def _move_towards(enemy_pos: list[int], target: tuple[int, int]) -> str:
    dx = target[0] - enemy_pos[0]
    dy = target[1] - enemy_pos[1]
    if abs(dx) >= abs(dy) and dx != 0:
        return "right" if dx > 0 else "left"
    if dy != 0:
        return "down" if dy > 0 else "up"
    return "stay"


def _resolve_flag_logic(
    player_pos: list[int],
    enemy_pos: list[int],
    flag_pos: list[int],
    carrier: str | None,
    player_base: tuple[int, int],
    enemy_base: tuple[int, int],
) -> tuple[str | None, list[int]]:
    if carrier == "player":
        flag_pos = [player_pos[0], player_pos[1]]
    elif carrier == "enemy":
        flag_pos = [enemy_pos[0], enemy_pos[1]]

    if tuple(player_pos) == tuple(enemy_pos):
        if carrier == "player":
            carrier = None
            flag_pos = [player_pos[0], player_pos[1]]
        elif carrier == "enemy":
            carrier = None
            flag_pos = [enemy_pos[0], enemy_pos[1]]

    if carrier is None:
        player_on_flag = tuple(player_pos) == tuple(flag_pos)
        enemy_on_flag = tuple(enemy_pos) == tuple(flag_pos)
        if player_on_flag and not enemy_on_flag:
            carrier = "player"
        elif enemy_on_flag and not player_on_flag:
            carrier = "enemy"

    if carrier == "player":
        flag_pos = [player_pos[0], player_pos[1]]
        if tuple(player_pos) == player_base:
            return carrier, flag_pos
    elif carrier == "enemy":
        flag_pos = [enemy_pos[0], enemy_pos[1]]
        if tuple(enemy_pos) == enemy_base:
            return carrier, flag_pos

    return carrier, flag_pos


def _fallback_driver(_x: int, _y: int, state: dict[str, object]) -> str:
    flag = state["flag"]
    own = state["self"]
    if not isinstance(flag, dict) or not isinstance(own, dict):
        return "stay"
    dx = int(flag.get("x", 0)) - int(own.get("x", 0))
    dy = int(flag.get("y", 0)) - int(own.get("y", 0))
    if abs(dx) >= abs(dy) and dx != 0:
        return "right" if dx > 0 else "left"
    if dy != 0:
        return "down" if dy > 0 else "up"
    return "stay"


def _fallback_support(_state: dict[str, object]) -> str:
    return "none"


def _build_scores(team_player_id: str, team_enemy_id: str, winner: str | None) -> dict[str, int]:
    if winner == "player":
        return {team_player_id: 3, team_enemy_id: 0}
    if winner == "enemy":
        return {team_player_id: 0, team_enemy_id: 3}
    return {team_player_id: 1, team_enemy_id: 1}


def _build_placements(team_player_id: str, team_enemy_id: str, winner: str | None) -> dict[str, int]:
    if winner == "player":
        return {team_player_id: 1, team_enemy_id: 2}
    if winner == "enemy":
        return {team_player_id: 2, team_enemy_id: 1}
    return {team_player_id: 1, team_enemy_id: 1}


def _resolve_team_player_id(ctx: dict[str, Any]) -> str:
    team_id = ctx.get("team_id")
    if isinstance(team_id, str) and team_id.strip():
        return team_id
    return "team-player"


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
