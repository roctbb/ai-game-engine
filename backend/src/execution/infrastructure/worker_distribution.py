"""Small, immutable Docker build context; no repository credentials or game data."""

from functools import lru_cache
import gzip
import hashlib
from io import BytesIO
from pathlib import Path
import shlex
import tarfile


@lru_cache(maxsize=1)
def worker_distribution():
    root = Path("/app/worker-distribution")
    if not root.is_dir():
        root = Path(__file__).resolve().parents[4] / "services/worker"
    dockerfile = (
        (root / "Dockerfile")
        .read_text()
        .replace("COPY games /app/games\n", "")
        .replace("docker.io ca-certificates", "ca-certificates")
    )
    files = [
        ("Dockerfile", dockerfile.encode()),
        ("services/worker/pyproject.toml", (root / "pyproject.toml").read_bytes()),
    ]
    files.extend(
        ("services/worker/" + str(path.relative_to(root)), path.read_bytes())
        for path in sorted((root / "src").rglob("*.py"))
        if not path.is_symlink()
    )
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in files:
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            archive.addfile(info, BytesIO(data))
    raw = gzip.compress(buffer.getvalue(), mtime=0)
    return hashlib.sha256(raw).hexdigest(), raw


def install_command(base_url, worker_id, enrollment_key, slots):
    digest, _ = worker_distribution()
    image = "arena-worker:" + digest[:16]
    name = "arena-" + worker_id
    context = f"{base_url}/api/v1/worker/v1/distribution/{digest}.tar.gz"
    commands = [
        ["docker", "build", "--pull", "-t", image, context],
        ["docker", "pull", "python:3.12-slim"],
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--restart",
            "unless-stopped",
            "--stop-timeout",
            "30",
            "--log-opt",
            "max-size=10m",
            "--log-opt",
            "max-file=3",
            "--mount",
            "type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock",
            "--mount",
            f"type=volume,source={name},target=/var/lib/arena-worker",
            "-e",
            f"ARENA_URL={base_url}",
            "-e",
            f"ENROLLMENT_KEY={enrollment_key}",
            "-e",
            f"MAX_SLOTS={slots}",
            "-e",
            "AUTO_POLL_ENABLED=true",
            "-e",
            "EXECUTION_TIMEOUT_SECONDS=20",
            "-e",
            "REQUEST_TIMEOUT_SECONDS=30",
            image,
        ],
    ]
    lines = [shlex.join(command) for command in commands]
    lines.insert(-1, "(docker rm -f " + shlex.quote(name) + " >/dev/null 2>&1 || true)")
    return " && ".join(lines)
