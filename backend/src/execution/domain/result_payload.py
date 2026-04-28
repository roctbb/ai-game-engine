from __future__ import annotations


COMPACT_RESULT_PAYLOAD_KEYS = frozenset(
    {
        "status",
        "score",
        "scores",
        "placement",
        "placements",
        "winner",
        "winners",
        "metrics",
        "match_participants",
        "participants",
        "replay_frame_count",
        "error",
    }
)


def compact_result_payload(payload: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    return {key: value for key, value in payload.items() if key in COMPACT_RESULT_PAYLOAD_KEYS}


def result_summary_from_payload(payload: dict[str, object] | None) -> dict[str, object] | None:
    compact = compact_result_payload(payload)
    if compact is None:
        return None
    frames = payload.get("frames") if isinstance(payload, dict) else None
    if isinstance(frames, list) and frames:
        compact["replay_frame_count"] = len(frames)
    elif "replay_frame_count" not in compact:
        compact["replay_frame_count"] = 1
    return compact
