"""External transport and durable per-machine credentials (never passed to engines)."""

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from threading import Lock
from urllib.parse import urlparse

from worker_service.settings import settings

_lock = Lock()
_token = None
_leases = {}


def enabled():
    return bool(settings.arena_url)


def base_url():
    base = settings.arena_url.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    ):
        raise RuntimeError("External workers require HTTPS")
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise RuntimeError("ARENA_URL must contain only the server origin")
    return base + "/api/v1/worker/v1"


def _save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(state, output)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)
    path.chmod(0o600)


def ensure_enrolled(client):
    global _token
    with _lock:
        if _token:
            return
        base = base_url()
        path = Path(settings.worker_state_path)
        key = settings.enrollment_key or ""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        state = json.loads(path.read_text()) if path.exists() else {}
        if state and state.get("server") != base:
            raise RuntimeError("Credential volume belongs to another Arena server")
        if (key and state.get("enrollment_hash") != key_hash) or not state.get("token"):
            parts = key.split(".")
            if (
                len(parts) != 3
                or parts[0] != "enroll"
                or not re.fullmatch(r"external_[a-f0-9]{32}", parts[1])
            ):
                raise RuntimeError(
                    "A valid ENROLLMENT_KEY is required for first connection"
                )
            state = {
                "server": base,
                "enrollment_hash": key_hash,
                "token": f"worker.{parts[1]}.{secrets.token_urlsafe(32)}",
                "enrolled": False,
            }
            # Save before exchange: a lost response can safely retry the same token.
            _save(path, state)
        response = client.post(
            base + "/register", headers={"Authorization": "Bearer " + state["token"]}
        )
        if not state.get("enrolled") and response.status_code == 401:
            response = client.post(
                base + "/enroll", json={"enrollment_key": key, "token": state["token"]}
            )
        response.raise_for_status()
        data = response.json()
        state["enrolled"] = True
        _save(path, state)
        _token = state["token"]
        settings.worker_id = data["worker_id"]
        settings.hostname = data["hostname"]
        settings.max_slots = data["capacity_total"]
        settings.worker_labels = data["labels"]


def translate(url, payload):
    base = base_url()
    path = urlparse(url).path
    if "/internal/workers/" in path:
        suffix = path.split("/internal/workers/", 1)[1]
        if suffix == "pull-next":
            url, payload = base + "/pull-next", {"wait_seconds": 10}
        elif suffix == "register":
            url, payload = base + "/register", {}
        elif suffix.endswith("/heartbeat"):
            url = base + "/heartbeat"
        else:
            raise RuntimeError("Unsupported remote worker operation")
    elif "/internal/runs/" in path:
        suffix = path.split("/internal/runs/", 1)[1]
        if suffix in {"renew-lease", "ack-finished"}:
            url = base + "/" + suffix
        else:
            url = base + "/runs/" + suffix
    else:
        raise RuntimeError("Unsupported remote worker URL")
    headers = {"Authorization": "Bearer " + _token}
    match = re.search(r"/runs/([^/]+)/", url)
    if match and match[1] in _leases:
        headers["X-Lease-Id"] = _leases[match[1]]
    return url, payload, headers


def observe(url, response):
    if url.endswith("/pull-next"):
        data = response.json()
        if data.get("run_id") and data.get("lease_id"):
            _leases[data["run_id"]] = data["lease_id"]


def forget(run_id):
    _leases.pop(run_id, None)
