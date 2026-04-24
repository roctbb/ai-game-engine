from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"


def sse_envelope(
    *,
    channel: str,
    entity_id: str,
    kind: str,
    payload: dict[str, Any] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "channel": channel,
        "entity_id": entity_id,
        "kind": kind,
        "emitted_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
    }
    if payload is not None:
        item["payload"] = payload
    if status is not None:
        item["status"] = status
    return item
