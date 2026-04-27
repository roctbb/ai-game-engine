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
        "error",
    }
)


def compact_result_payload(payload: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    return {key: value for key, value in payload.items() if key in COMPACT_RESULT_PAYLOAD_KEYS}
