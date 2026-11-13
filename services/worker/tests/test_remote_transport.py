import json
import stat

import httpx
import pytest

from worker_service import remote
from worker_service.settings import settings


@pytest.fixture
def remote_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "arena_url", "https://arena.example")
    monkeypatch.setattr(
        settings, "worker_state_path", str(tmp_path / "state/credentials.json")
    )
    monkeypatch.setattr(
        settings, "enrollment_key", "enroll.external_" + "a" * 32 + "." + "b" * 43
    )
    monkeypatch.setattr(remote, "_token", None)
    monkeypatch.setattr(remote, "_leases", {})
    for field in ("worker_id", "hostname", "max_slots", "worker_labels"):
        monkeypatch.setattr(settings, field, getattr(settings, field))
    return tmp_path


def test_enrollment_survives_lost_response_restart_and_missing_bootstrap(
    remote_settings, monkeypatch
):
    attempts = []

    def handler(request):
        if request.url.path.endswith("/enroll"):
            token = json.loads(request.content)["token"]
            attempts.append(token)
            if len(attempts) == 1:
                raise httpx.ReadError("Lost enrollment reply", request=request)
        else:
            if not attempts:
                return httpx.Response(401)
            assert request.headers["Authorization"] == "Bearer " + attempts[0]
        return httpx.Response(
            200,
            json={
                "worker_id": "external_" + "a" * 32,
                "hostname": "Runner",
                "capacity_total": 2,
                "labels": {"pool": "external"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ReadError):
            remote.ensure_enrolled(client)
        remote.ensure_enrolled(client)
        assert (
            len(attempts) == 1
        )  # The saved token confirms the exchange after its reply was lost.
        from pathlib import Path

        assert stat.S_IMODE(Path(settings.worker_state_path).stat().st_mode) == 0o600
        monkeypatch.setattr(remote, "_token", None)
        monkeypatch.setattr(settings, "enrollment_key", None)
        remote.ensure_enrolled(client)
        assert len(attempts) == 1  # Restart uses the saved node token.
        assert settings.max_slots == 2


def test_only_gateway_receives_bearer_and_lease_headers(remote_settings, monkeypatch):
    monkeypatch.setattr(remote, "_token", "private-token")
    remote.observe(
        "https://arena.example/api/v1/worker/v1/pull-next",
        httpx.Response(200, json={"run_id": "run-1", "lease_id": "lease-1"}),
    )
    url, payload, headers = remote.translate(
        settings.backend_api_url + "/internal/runs/run-1/package", None
    )
    assert url == "https://arena.example/api/v1/worker/v1/runs/run-1/package"
    assert headers == {"Authorization": "Bearer private-token", "X-Lease-Id": "lease-1"}
    assert "X-Internal-Token" not in headers
    url, payload, _ = remote.translate(
        settings.scheduler_url + "/internal/workers/pull-next", {"worker_id": "spoof"}
    )
    assert payload == {"wait_seconds": 10}
    remote.forget("run-1")
    assert not remote._leases
    with pytest.raises(RuntimeError):
        remote.translate("https://elsewhere.example/anything", None)


def test_plain_http_external_origin_is_rejected(remote_settings, monkeypatch):
    monkeypatch.setattr(settings, "arena_url", "http://external.example")
    with pytest.raises(RuntimeError, match="HTTPS"):
        remote.base_url()
