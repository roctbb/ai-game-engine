from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterator

from scheduler_service.queue import SchedulerQueue
from scheduler_service.settings import settings


class FakeRedis:
    def __init__(self) -> None:
        self._sets: dict[str, set[str]] = defaultdict(set)
        self._lists: dict[str, deque[str]] = defaultdict(deque)
        self._hashes: dict[str, dict[str, object]] = defaultdict(dict)
        self.hgetall_calls: dict[str, int] = defaultdict(int)

    def sadd(self, key: str, value: str) -> int:
        if value in self._sets[key]:
            return 0
        self._sets[key].add(value)
        return 1

    def rpush(self, key: str, value: str) -> None:
        self._lists[key].append(value)

    def lpop(self, key: str) -> str | None:
        if not self._lists[key]:
            return None
        return self._lists[key].popleft()

    def hset(self, key: str, field: str, value: object) -> None:
        self._hashes[key][field] = value

    def hdel(self, key: str, field: str) -> None:
        self._hashes[key].pop(field, None)

    def hget(self, key: str, field: str) -> object | None:
        return self._hashes[key].get(field)

    def srem(self, key: str, value: str) -> None:
        self._sets[key].discard(value)

    def sismember(self, key: str, value: str) -> bool:
        return value in self._sets[key]

    def llen(self, key: str) -> int:
        return len(self._lists[key])

    def scard(self, key: str) -> int:
        return len(self._sets[key])

    def scan_iter(self, match: str) -> Iterator[str]:
        if match == "agp:worker:*:leases":
            for key in self._hashes:
                if key.startswith("agp:worker:") and key.endswith(":leases"):
                    yield key

    def hgetall(self, key: str) -> dict[str, object]:
        self.hgetall_calls[key] += 1
        return dict(self._hashes[key])


def test_enqueue_deduplicates_run() -> None:
    queue = SchedulerQueue(redis_client=FakeRedis())

    inserted_first = queue.enqueue(run_id="run-1")
    inserted_second = queue.enqueue(run_id="run-1")

    assert inserted_first is True
    assert inserted_second is False
    assert queue.stats()["queue_depth"] == 1
    assert queue.stats()["known_count"] == 1


def test_pull_next_creates_worker_lease() -> None:
    queue = SchedulerQueue(redis_client=FakeRedis())
    queue.enqueue(run_id="run-1")

    run_id = queue.pull_next(worker_id="w-1", leased_at_epoch=123)
    stats = queue.stats()

    assert run_id == "run-1"
    assert stats["queue_depth"] == 0
    assert stats["known_count"] == 1
    assert stats["worker_leases"] == {
        "w-1": [{"worker_id": "w-1", "run_id": "run-1", "leased_at": 123}]
    }


def test_ack_finished_clears_known_and_lease() -> None:
    queue = SchedulerQueue(redis_client=FakeRedis())
    queue.enqueue(run_id="run-1")
    queue.pull_next(worker_id="w-1", leased_at_epoch=123)

    acknowledged = queue.ack_finished(worker_id="w-1", run_id="run-1")
    stats = queue.stats()

    assert acknowledged is True
    assert stats["queue_depth"] == 0
    assert stats["known_count"] == 0
    assert stats["worker_leases"] == {"w-1": []}


def test_stale_ack_does_not_remove_known_run() -> None:
    queue = SchedulerQueue(redis_client=FakeRedis())
    queue.enqueue(run_id="run-1")
    queue.pull_next(worker_id="w-1", leased_at_epoch=123)

    acknowledged = queue.ack_finished(worker_id="w-2", run_id="run-1")
    stats = queue.stats()

    assert acknowledged is False
    assert stats["known_count"] == 1
    assert stats["worker_leases"] == {
        "w-1": [{"worker_id": "w-1", "run_id": "run-1", "leased_at": 123}]
    }


def test_expired_lease_requeued_on_next_pull() -> None:
    old_ttl = settings.lease_ttl_seconds
    settings.lease_ttl_seconds = 10
    try:
        queue = SchedulerQueue(redis_client=FakeRedis())
        queue.enqueue(run_id="run-1")
        first_pull = queue.pull_next(worker_id="w-1", leased_at_epoch=100)
        second_pull = queue.pull_next(worker_id="w-2", leased_at_epoch=111)

        stats = queue.stats()
        assert first_pull == "run-1"
        assert second_pull == "run-1"
        assert stats["queue_depth"] == 0
        assert stats["known_count"] == 1
        assert stats["worker_leases"] == {
            "w-1": [],
            "w-2": [{"worker_id": "w-2", "run_id": "run-1", "leased_at": 111}],
        }
    finally:
        settings.lease_ttl_seconds = old_ttl


def test_pull_next_throttles_expired_lease_scan() -> None:
    old_interval = settings.lease_requeue_check_interval_seconds
    settings.lease_requeue_check_interval_seconds = 5
    try:
        redis = FakeRedis()
        queue = SchedulerQueue(redis_client=redis)
        queue.enqueue(run_id="run-1")

        first_pull = queue.pull_next(worker_id="w-1", leased_at_epoch=100)
        second_pull = queue.pull_next(worker_id="w-2", leased_at_epoch=101)
        third_pull = queue.pull_next(worker_id="w-3", leased_at_epoch=105)

        assert first_pull == "run-1"
        assert second_pull is None
        assert third_pull is None
        assert redis.hgetall_calls[settings.run_lease_hash_key] == 2
    finally:
        settings.lease_requeue_check_interval_seconds = old_interval


def test_pull_next_respects_required_worker_labels() -> None:
    queue = SchedulerQueue(redis_client=FakeRedis())
    queue.enqueue(run_id="run-cpu", required_worker_labels={"pool": "cpu"})
    queue.enqueue(run_id="run-gpu", required_worker_labels={"pool": "gpu"})

    first = queue.pull_next(worker_id="w-gpu", leased_at_epoch=100, worker_labels={"pool": "gpu"})
    second = queue.pull_next(worker_id="w-cpu", leased_at_epoch=101, worker_labels={"pool": "cpu"})

    assert first == "run-gpu"
    assert second == "run-cpu"


def test_pull_next_keeps_unmatched_runs_in_queue() -> None:
    queue = SchedulerQueue(redis_client=FakeRedis())
    queue.enqueue(run_id="run-gpu", required_worker_labels={"pool": "gpu"})

    first = queue.pull_next(worker_id="w-cpu", leased_at_epoch=100, worker_labels={"pool": "cpu"})
    second = queue.pull_next(worker_id="w-gpu", leased_at_epoch=101, worker_labels={"pool": "gpu"})

    assert first is None
    assert second == "run-gpu"
