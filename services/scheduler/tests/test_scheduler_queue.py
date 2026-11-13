from concurrent.futures import ThreadPoolExecutor
import pytest
from redis.exceptions import ConnectionError
from scheduler_service.queue import SchedulerQueue
from scheduler_service.settings import settings


def test_enqueue_deduplicates_run(redis_client):
    queue = SchedulerQueue(redis_client)
    assert queue.enqueue("run")
    assert not queue.enqueue("run")
    assert queue.stats()["queue_depth"] == 1


def test_retry_after_lost_enqueue_response_keeps_job(redis_client):
    class LostResponse:
        first = True

        def eval(self, *args):
            result = redis_client.eval(*args)
            if self.first:
                self.first = False
                raise ConnectionError("Response lost after Redis committed enqueue")
            return result

    queue = SchedulerQueue(LostResponse())
    with pytest.raises(ConnectionError):
        queue.enqueue("run")
    assert not queue.enqueue("run")
    assert SchedulerQueue(redis_client).pull_next("worker", 100).run_id == "run"


def test_parallel_pull_assigns_exactly_one_lease(redis_client):
    queue = SchedulerQueue(redis_client)
    queue.enqueue("run")
    with ThreadPoolExecutor(max_workers=12) as pool:
        leases = list(
            pool.map(
                lambda i: SchedulerQueue(redis_client).pull_next(f"w-{i}", 100),
                range(24),
            )
        )
    assert sum(lease is not None for lease in leases) == 1


def test_expired_lease_has_new_generation_and_rejects_old_ack(redis_client):
    queue = SchedulerQueue(redis_client)
    queue.enqueue("run")
    first = queue.pull_next("old", 100)
    second = queue.pull_next("new", 100 + settings.lease_ttl_seconds + 1)
    assert second.generation > first.generation
    assert not queue.ack_finished("old", "run", first.lease_id)
    assert not queue.renew("old", "run", first.lease_id, 140)
    assert queue.stats()["known_count"] == 1
    assert queue.ack_finished("new", "run", second.lease_id)
    assert queue.stats()["known_count"] == 0


def test_renewal_prevents_reassignment(redis_client):
    queue = SchedulerQueue(redis_client)
    queue.enqueue("run")
    lease = queue.pull_next("worker", 100)
    assert queue.renew(
        "worker", "run", lease.lease_id, 100 + settings.lease_ttl_seconds - 1
    )
    assert queue.pull_next("other", 100 + settings.lease_ttl_seconds + 1) is None
    assert not queue.renew(
        "worker", "run", lease.lease_id, 100 + 2 * settings.lease_ttl_seconds
    )


def test_labels_and_cancel(redis_client):
    queue = SchedulerQueue(redis_client)
    queue.enqueue("gpu", {"pool": "gpu"})
    queue.enqueue("cpu", {"pool": "cpu"})
    assert queue.pull_next("gpu-worker", 100, {"pool": "gpu"}).run_id == "gpu"
    queue.cancel("gpu")
    queue.cancel("cpu")
    assert queue.stats()["known_count"] == 0
    assert queue.stats()["queue_depth"] == 0
    assert queue.pull_next("worker", 140, {"pool": "cpu"}) is None


def test_external_slots_are_atomic_and_keep_longer_lease_on_renewal(redis_client):
    queue = SchedulerQueue(redis_client)
    for index in range(8):
        queue.enqueue(f"external-{index}")
    with ThreadPoolExecutor(max_workers=8) as pool:
        leases = list(pool.map(lambda _: SchedulerQueue(redis_client).pull_next(
            "external", 100, max_slots=2, lease_ttl_seconds=90), range(8)))
    assigned = [lease for lease in leases if lease]
    assert len(assigned) == 2
    assert queue.renew("external", assigned[0].run_id, assigned[0].lease_id, 150)
    # The original 90-second lease survives renewal despite the 30-second internal default.
    later = SchedulerQueue(redis_client).pull_next("other", 200)
    assert later.run_id != assigned[0].run_id
    assert queue.renew("external", assigned[0].run_id, assigned[0].lease_id, 230)
