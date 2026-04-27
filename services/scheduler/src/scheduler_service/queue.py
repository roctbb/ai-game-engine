from __future__ import annotations

import json
from dataclasses import dataclass

from redis import Redis

from scheduler_service.settings import settings


@dataclass(frozen=True, slots=True)
class Lease:
    worker_id: str
    run_id: str
    leased_at: int


class SchedulerQueue:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client
        self._last_requeue_check_epoch: int | None = None

    def enqueue(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> bool:
        normalized_required_labels = self._normalize_label_map(required_worker_labels)
        if normalized_required_labels:
            self._redis.hset(
                settings.run_requirements_hash_key,
                run_id,
                json.dumps(normalized_required_labels),
            )
        else:
            self._redis.hdel(settings.run_requirements_hash_key, run_id)

        inserted = self._redis.sadd(settings.known_set_key, run_id)
        if inserted == 0:
            return False
        queued_inserted = self._redis.sadd(settings.queued_set_key, run_id)
        if queued_inserted == 1:
            self._redis.rpush(settings.queue_key, run_id)
        return True

    def pull_next(
        self,
        worker_id: str,
        leased_at_epoch: int,
        worker_labels: dict[str, str] | None = None,
    ) -> str | None:
        self._requeue_expired_leases_if_due(now_epoch=leased_at_epoch)
        normalized_worker_labels = self._normalize_label_map(worker_labels)
        queue_depth = int(self._redis.llen(settings.queue_key))

        for _ in range(queue_depth):
            raw_run_id = self._redis.lpop(settings.queue_key)
            if raw_run_id is None:
                return None

            run_id = raw_run_id.decode("utf-8") if isinstance(raw_run_id, bytes) else str(raw_run_id)
            if not bool(self._redis.sismember(settings.known_set_key, run_id)):
                self._redis.srem(settings.queued_set_key, run_id)
                self._redis.hdel(settings.run_requirements_hash_key, run_id)
                continue

            required_worker_labels = self._required_worker_labels(run_id)
            if self._labels_match(required_worker_labels, normalized_worker_labels):
                self._redis.srem(settings.queued_set_key, run_id)
                lease_key = self._lease_key(worker_id)
                self._redis.hset(lease_key, run_id, leased_at_epoch)
                self._redis.hset(
                    settings.run_lease_hash_key,
                    run_id,
                    json.dumps({"worker_id": worker_id, "leased_at": leased_at_epoch}),
                )
                return run_id

            self._redis.rpush(settings.queue_key, run_id)

        return None

    def ack_finished(self, worker_id: str, run_id: str) -> bool:
        raw_payload = self._redis.hget(settings.run_lease_hash_key, run_id)
        if raw_payload is None:
            return False

        lease = self._lease_from_payload(run_id=run_id, raw_payload=raw_payload)
        if lease is None or lease.worker_id != worker_id:
            return False

        pipe = self._redis.pipeline()
        pipe.hdel(settings.run_lease_hash_key, run_id)
        pipe.hdel(self._lease_key(worker_id), run_id)
        pipe.hdel(settings.run_requirements_hash_key, run_id)
        pipe.srem(settings.known_set_key, run_id)
        pipe.srem(settings.queued_set_key, run_id)
        pipe.execute()
        return True

    def stats(self) -> dict[str, object]:
        queue_depth = int(self._redis.llen(settings.queue_key))
        known_count = int(self._redis.scard(settings.known_set_key))

        worker_leases: dict[str, list[Lease]] = {}
        for raw_key in self._redis.scan_iter(match="agp:worker:*:leases"):
            key = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
            worker_id = key.split(":")[2]
            leases_raw = self._redis.hgetall(key)
            worker_leases[worker_id] = [
                Lease(
                    worker_id=worker_id,
                    run_id=(run_id.decode("utf-8") if isinstance(run_id, bytes) else str(run_id)),
                    leased_at=int(ts),
                )
                for run_id, ts in leases_raw.items()
            ]

        return {
            "queue_depth": queue_depth,
            "known_count": known_count,
            "worker_leases": {
                worker_id: [
                    {
                        "worker_id": lease.worker_id,
                        "run_id": lease.run_id,
                        "leased_at": lease.leased_at,
                    }
                    for lease in leases
                ]
                for worker_id, leases in worker_leases.items()
            },
        }

    def _requeue_expired_leases_if_due(self, now_epoch: int) -> None:
        if self._last_requeue_check_epoch is not None:
            elapsed = now_epoch - self._last_requeue_check_epoch
            if elapsed < settings.lease_requeue_check_interval_seconds:
                return

        self._last_requeue_check_epoch = now_epoch
        self._requeue_expired_leases(now_epoch=now_epoch)

    def _requeue_expired_leases(self, now_epoch: int) -> None:
        raw_leases = self._redis.hgetall(settings.run_lease_hash_key)
        expired: list[tuple[str, Lease]] = []
        for raw_run_id, raw_payload in raw_leases.items():
            run_id = raw_run_id.decode("utf-8") if isinstance(raw_run_id, bytes) else str(raw_run_id)
            lease = self._lease_from_payload(run_id=run_id, raw_payload=raw_payload)
            if lease is None:
                self._redis.hdel(settings.run_lease_hash_key, run_id)
                continue
            if now_epoch - lease.leased_at >= settings.lease_ttl_seconds:
                expired.append((run_id, lease))

        if not expired:
            return

        pipe = self._redis.pipeline()
        for run_id, lease in expired:
            pipe.hdel(settings.run_lease_hash_key, run_id)
            pipe.hdel(self._lease_key(lease.worker_id), run_id)
        pipe.execute()

        for run_id, _lease in expired:
            if bool(self._redis.sismember(settings.known_set_key, run_id)):
                queued_inserted = self._redis.sadd(settings.queued_set_key, run_id)
                if queued_inserted == 1:
                    self._redis.rpush(settings.queue_key, run_id)

    @staticmethod
    def _lease_from_payload(run_id: str, raw_payload: object) -> Lease | None:
        payload_text = raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else str(raw_payload)
        try:
            data = json.loads(payload_text)
        except json.JSONDecodeError:
            return None

        worker_id = data.get("worker_id")
        leased_at = data.get("leased_at")
        if not isinstance(worker_id, str):
            return None
        if not isinstance(leased_at, int):
            return None

        return Lease(worker_id=worker_id, run_id=run_id, leased_at=leased_at)

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
