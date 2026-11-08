import importlib.util
from pathlib import Path


def test_compose_smoke_observes_runs_already_completed_by_automatic_workers(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts" / "e2e_distributed_smoke.py"
    spec = importlib.util.spec_from_file_location("execution_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    def request(method, url):
        calls.append((method, url))
        assert method == "GET"
        return 200, {"status": "finished"}

    monkeypatch.setattr(module, "_request", request)
    module._drain_worker_until_completed(
        "http://worker", "http://backend", ["primary", "shadow"], 1
    )
    assert len(calls) == 2
