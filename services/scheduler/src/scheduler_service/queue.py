from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4
from typing import Any

from redis import Redis

from scheduler_service.settings import settings
from scheduler_service import scripts


@dataclass(frozen=True, slots=True)
class Lease:
    worker_id: str
    run_id: str
    lease_id: str
    leased_at: float
    generation: int = 0
    expires_at: float = 0


class SchedulerQueue:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client
        self._last_requeue_check_epoch: float | None = None

    def _eval(self, script: str, *args: object) -> Any:
        return self._redis.eval(
            script,
            6,
            settings.queue_key,
            settings.queued_set_key,
            settings.known_set_key,
            settings.run_lease_hash_key,
            settings.run_requirements_hash_key,
            settings.lease_sequence_key,
            *args,
        )

    def enqueue(
        self, run_id: str, required_worker_labels: dict[str, str] | None = None
    ) -> bool:
        return bool(
            self._eval(
                scripts.ENQUEUE,
                run_id,
                json.dumps(self._normalize_label_map(required_worker_labels)),
            )
        )

    def pull_next(
        self,
        worker_id: str,
        leased_at_epoch: float,
        worker_labels: dict[str, str] | None = None,
    ) -> Lease | None:
        scan = (
            self._last_requeue_check_epoch is None
            or leased_at_epoch - self._last_requeue_check_epoch
            >= settings.lease_requeue_check_interval_seconds
        )
        if scan:
            self._last_requeue_check_epoch = leased_at_epoch
        raw = self._eval(
            scripts.PULL,
            worker_id,
            leased_at_epoch,
            settings.lease_ttl_seconds,
            json.dumps(self._normalize_label_map(worker_labels)),
            f"lease_{uuid4().hex}",
            int(scan),
        )
        return self._lease_from_payload("", raw) if raw else None

    def ack_finished(self, worker_id: str, run_id: str, lease_id: str) -> bool:
        return bool(self._eval(scripts.ACK, run_id, worker_id, lease_id))

    def renew(
        self, worker_id: str, run_id: str, lease_id: str, now_epoch: float
    ) -> bool:
        return bool(
            self._eval(
                scripts.RENEW,
                run_id,
                worker_id,
                lease_id,
                now_epoch,
                settings.lease_ttl_seconds,
            )
        )

    def cancel(self, run_id: str) -> None:
        self._eval(scripts.CANCEL, run_id)

    def stats(self) -> dict[str, object]:
        queue_depth = int(self._redis.llen(settings.queue_key))
        known_count = int(self._redis.scard(settings.known_set_key))

        worker_leases: dict[str, list[Lease]] = {}
        for raw_key in self._redis.scan_iter(match="agp:worker:*:leases"):
            key = (
                raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
            )
            worker_id = key.split(":")[2]
            leases_raw = self._redis.hgetall(key)
            worker_leases[worker_id] = []
            for raw_run_id, raw_payload in leases_raw.items():
                run_id = (
                    raw_run_id.decode("utf-8")
                    if isinstance(raw_run_id, bytes)
                    else str(raw_run_id)
                )
                lease = self._lease_from_payload(run_id=run_id, raw_payload=raw_payload)
                if lease is not None:
                    worker_leases[worker_id].append(lease)

        return {
            "queue_depth": queue_depth,
            "known_count": known_count,
            "worker_leases": {
                worker_id: [
                    {
                        "worker_id": lease.worker_id,
                        "run_id": lease.run_id,
                        "lease_id": lease.lease_id,
                        "leased_at": lease.leased_at,
                    }
                    for lease in leases
                ]
                for worker_id, leases in worker_leases.items()
            },
        }

    @staticmethod
    def _lease_from_payload(run_id: str, raw_payload: object) -> Lease | None:
        payload_text = (
            raw_payload.decode("utf-8")
            if isinstance(raw_payload, bytes)
            else str(raw_payload)
        )
        try:
            data = json.loads(payload_text)
        except json.JSONDecodeError:
            return None

        worker_id = data.get("worker_id")
        lease_id = data.get("lease_id")
        leased_at = data.get("leased_at")
        if not isinstance(worker_id, str):
            return None
        if not isinstance(lease_id, str) or not lease_id:
            return None
        if not isinstance(leased_at, (int, float)):
            return None

        return Lease(
            worker_id=worker_id,
            run_id=str(data.get("run_id") or run_id),
            lease_id=lease_id,
            leased_at=leased_at,
            generation=int(data.get("generation", 0)),
            expires_at=int(
                data.get("expires_at", leased_at + settings.lease_ttl_seconds)
            ),
        )

    @staticmethod
    def _lease_key(worker_id: str) -> str:
        return f"agp:worker:{worker_id}:leases"

    def _required_worker_labels(self, run_id: str) -> dict[str, str]:
        raw = self._redis.hget(settings.run_requirements_hash_key, run_id)
        if raw is None:
            return {}
        payload_text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        try:
            parsed = json.loads(payload_text)
        except json.JSONDecodeError:
            self._redis.hdel(settings.run_requirements_hash_key, run_id)
            return {}
        if not isinstance(parsed, dict):
            self._redis.hdel(settings.run_requirements_hash_key, run_id)
            return {}
        return self._normalize_label_map(parsed)

    @staticmethod
    def _labels_match(required: dict[str, str], worker_labels: dict[str, str]) -> bool:
        for key, value in required.items():
            if worker_labels.get(key) != value:
                return False
        return True

    @staticmethod
    def _normalize_label_map(raw_labels: object) -> dict[str, str]:
        if not isinstance(raw_labels, dict):
            return {}
        normalized: dict[str, str] = {}
        for key, value in raw_labels.items():
            label_key = str(key).strip()
            label_value = str(value).strip()
            if not label_key or not label_value:
                continue
            normalized[label_key] = label_value
        return normalized
