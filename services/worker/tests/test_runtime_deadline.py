from io import BytesIO
import subprocess
import sys
import tarfile

from worker_service.main import _build_package_archive


def test_container_local_deadline_stops_engine_without_host_watchdog(tmp_path):
    package = tmp_path / "game"
    package.mkdir()
    (package / "engine.py").write_text("while True: pass\n")
    raw = _build_package_archive(package)
    with tarfile.open(fileobj=BytesIO(raw), mode="r:gz") as archive:
        archive.extractall(tmp_path / "runtime")
    completed = subprocess.run(
        [sys.executable, ".agp-runtime/supervisor.py", "engine.py", "0.1"],
        cwd=tmp_path / "runtime",
        capture_output=True,
        timeout=5,
    )
    assert completed.returncode == 124
    assert b"deadline exceeded" in completed.stderr


def test_archive_cache_uses_contents_and_includes_runtime(tmp_path):
    (tmp_path / "engine.py").write_text("print('old')")
    old = _build_package_archive(tmp_path)
    assert old == _build_package_archive(tmp_path)
    (tmp_path / "engine.py").write_text("print('new')")
    new = _build_package_archive(tmp_path)
    assert new != old
    with tarfile.open(fileobj=BytesIO(new), mode="r:gz") as archive:
        assert archive.extractfile("engine.py").read() == b"print('new')"
        assert ".agp-runtime/supervisor.py" in archive.getnames()
