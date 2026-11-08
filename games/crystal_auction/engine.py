from __future__ import annotations

import json
import os
import random
from typing import Any, Callable

CONFIG = {
    "dir": "crystal_auction",
    "id": "crystal_auction_v1",
    "title": "Аукцион кристаллов",
    "difficulty": "hard",
    "section": "Соревновательные стратегии",
    "topics": ["соревнование", "арифметика", "стратегия"],
    "kind": "crystal_auction",
    "mode": "small_match",
    "instruction": "Определите функцию bid(state), которая возвращает ставку на текущий кристалл.",
    "learning_section": "Соревновательные стратегии",
    "slots": [{"key": "left"}, {"key": "right"}],
}


def run(context: dict[str, Any] | None = None) -> dict[str, object]:
    ctx = context or _load_context()
    participants = ctx.get("participants")
    if isinstance(participants, list) and len(participants) >= 2:
        run_ids = [
            str(p.get("run_id", ""))
            for p in participants
            if isinstance(p, dict) and p.get("run_id")
        ]
        seed = min(run_ids) if run_ids else str(ctx.get("run_id") or CONFIG["id"])
    else:
        seed = str(ctx.get("run_id") or CONFIG["id"])
    rng = random.Random(seed)
    return _run_match(ctx, rng)


def _load_context() -> dict[str, Any]:
    raw = os.getenv("AGP_RUN_CONTEXT")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_participants(ctx, slots):
    participants = ctx.get("participants")
    if isinstance(participants, list) and len(participants) >= 2:
        role_code = {}
        role_team = {}
        role_name = {}
        for i, role in enumerate(slots):
            p = participants[i]
            codes = p.get("codes_by_slot") if isinstance(p, dict) else {}
            code = codes.get("player", "") if isinstance(codes, dict) else ""
            role_code[role] = str(code) if code else ""
            tid = str(p.get("team_id", role)) if isinstance(p, dict) else role
            role_team[role] = tid
            name = (
                p.get("display_name") or p.get("captain_user_id")
                if isinstance(p, dict)
                else None
            )
            role_name[role] = str(name) if name else tid
        return role_code, role_team, role_name
    codes = ctx.get("codes_by_slot")
    if isinstance(codes, dict):
        code = str(codes.get("player", ""))
        return {r: code for r in slots}, {r: r for r in slots}, {r: r for r in slots}
    return {r: "" for r in slots}, {r: r for r in slots}, {r: r for r in slots}


def _build_fn_from_code(code, slot, events, print_context):
    namespace = {"__builtins__": _builtins(slot, events, print_context)}
    compile_error = None
    if code.strip():
        try:
            exec(code, namespace, namespace)
        except Exception as exc:
            compile_error = str(exc)
    for name in (
        "play",
        "solve",
        "choose_action",
        "choose_actions",
        "choose_target",
        "choose_item",
        "choose_potion",
        "schedule",
        "decode",
        "run_tape",
        "paint",
        "scan",
        "build_numbers",
        "count_plants",
        "trace",
        "simulate",
        "make_plan",
        "make_move",
        "bid",
    ):
        candidate = namespace.get(name)
        if callable(candidate):
            return candidate, compile_error
    return None, compile_error


def _run_match(ctx: dict[str, Any], rng: random.Random) -> dict[str, object]:
    events: list[dict[str, object]] = []
    slots = [slot["key"] for slot in CONFIG["slots"]]
    print_context = {"tick": 0}
    role_code, role_team, role_name = _resolve_participants(ctx, slots)
    bots = {
        slot: _build_fn_from_code(role_code.get(slot, ""), slot, events, print_context)
        for slot in slots
    }
    result = _crystal_auction(slots, bots, events, print_context, rng)
    for frame in result.get("frames", []):
        inner = frame.get("frame") if isinstance(frame, dict) else None
        if isinstance(inner, dict):
            inner["labels"] = {slot: role_name.get(slot, slot) for slot in slots}
    slot_scores = result["slot_scores"]
    scores = {role_team[slot]: int(slot_scores[slot]) for slot in slots}
    placements = _placements(role_team, slot_scores, slots)
    metrics = {
        **result["metrics"],
        "slot_scores": slot_scores,
        "winner_slots": _winner_slots(slot_scores, slots),
    }
    compile_errors = {slot: err for slot, (_fn, err) in bots.items() if err}
    if compile_errors:
        metrics["compile_errors"] = compile_errors
        for slot, message in compile_errors.items():
            events.append({"type": "compile_error", "slot": slot, "message": message})
    payload: dict[str, object] = {
        "status": "finished",
        "metrics": metrics,
        "frames": result["frames"],
        "events": events,
        "scores": scores,
    }
    payload["placements"] = placements
    if len(set(placements.values())) != len(placements):
        payload["tie_resolution"] = "explicit_tie"
    return payload


def _builtins(
    slot: str, events: list[dict[str, object]], print_context: dict[str, int]
) -> dict[str, object]:
    def bot_print(
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: object | None = None,
        flush: bool = False,
    ) -> None:
        if file is not None:
            return
        message = sep.join(str(value) for value in values)
        if end and end != "\n":
            message += end
        for line in message.splitlines() or [""]:
            events.append(
                {
                    "type": "bot_print",
                    "tick": int(print_context.get("tick", 0)),
                    "role": slot,
                    "message": line,
                }
            )

    return {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "isinstance": isinstance,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": bot_print,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }


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


def _crystal_auction(
    slots: list[str],
    bots: dict[str, tuple[Callable[..., object] | None, str | None]],
    events: list[dict[str, object]],
    print_context: dict[str, int],
    rng: random.Random,
) -> dict[str, object]:
    budget = {slot: 70 for slot in slots}
    value = {slot: 0 for slot in slots}
    spent = {slot: 0 for slot in slots}
    frames = []
    crystals = [rng.randint(8, 22) for _ in range(4)] + [
        rng.randint(18, 34) for _ in range(4)
    ]
    for turn, crystal in enumerate(crystals, start=1):
        print_context["tick"] = turn
        bids = {}
        fair_bid = max(1, crystal // 2 + (3 if turn > len(crystals) // 2 else 0))
        for slot in slots:
            state = {
                "turn": turn,
                "crystal_value": crystal,
                "budget": budget[slot],
                "my_value": value[slot],
                "rounds_left": len(crystals) - turn,
                "fair_bid": fair_bid,
                "average_value": sum(crystals) // len(crystals),
            }
            raw = _call(bots[slot][0], state)
            try:
                bid = int(raw)
            except Exception:
                bid = 0
            bids[slot] = max(0, min(budget[slot], bid))
        winner = max(slots, key=lambda s: (bids[s], -slots.index(s)))
        if bids[slots[0]] == bids[slots[1]]:
            winner = slots[(turn + crystal) % 2]
        budget[winner] -= bids[winner]
        spent[winner] += bids[winner]
        value[winner] += crystal
        deal = {slot: (crystal - bids[slot] if slot == winner else 0) for slot in slots}
        frames.append(
            {
                "tick": turn,
                "phase": "running",
                "frame": _match_frame(
                    {
                        "crystal": crystal,
                        "bids": bids,
                        "winner": winner,
                        "budget": budget.copy(),
                        "value": value.copy(),
                        "spent": spent.copy(),
                        "deal": deal,
                        "fair_bid": fair_bid,
                        "rounds_left": len(crystals) - turn,
                    }
                ),
            }
        )
    slot_scores = {slot: value[slot] + budget[slot] for slot in slots}
    frames.append(
        {
            "tick": len(frames) + 1,
            "phase": "finished",
            "frame": _match_frame(
                {"budget": budget, "value": value, "spent": spent, "score": slot_scores}
            ),
        }
    )
    return {
        "slot_scores": slot_scores,
        "metrics": {
            "budget": budget,
            "value": value,
            "spent": spent,
            "crystals": crystals,
        },
        "frames": frames,
    }


def _match_frame(payload: dict[str, object]) -> dict[str, object]:
    return {
        "title": CONFIG["title"],
        "kind": CONFIG["kind"],
        "learning_section": CONFIG["learning_section"],
        "difficulty": CONFIG["difficulty"],
        **_normalize(payload),
    }


def _placements(
    role_team: dict[str, str], slot_scores: dict[str, int], slots: list[str]
) -> dict[str, int]:
    ordered = sorted(slots, key=lambda slot: (-slot_scores[slot], slot))
    placements: dict[str, int] = {}
    last_score = None
    last_place = 0
    for index, slot in enumerate(ordered, start=1):
        score = slot_scores[slot]
        place = last_place if score == last_score else index
        placements[role_team[slot]] = place
        last_score = score
        last_place = place
    return placements


def _winner_slots(slot_scores: dict[str, int], slots: list[str]) -> list[str]:
    best = max(slot_scores[slot] for slot in slots)
    return [slot for slot in slots if slot_scores[slot] == best]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
