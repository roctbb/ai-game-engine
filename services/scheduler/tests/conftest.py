"""Production Lua is tested against a private Redis, never a user's database."""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
import pytest
from redis import Redis
from redis.exceptions import ConnectionError


@pytest.fixture(scope="session")
def redis_server():
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server is required for scheduler integration tests")
    with tempfile.TemporaryDirectory(prefix="agp-redis-", dir="/tmp") as directory:
        socket = str(Path(directory) / "redis.sock")
        process = subprocess.Popen(
            [
                binary,
                "--port",
                "0",
                "--unixsocket",
                socket,
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        client = Redis(unix_socket_path=socket)
        try:
            for _ in range(200):
                try:
                    if client.ping():
                        break
                except ConnectionError:
                    time.sleep(0.025)
            else:
                raise RuntimeError("Private test Redis failed to start")
            yield client
        finally:
            client.close()
            process.terminate()
            process.wait(timeout=5)


@pytest.fixture()
def redis_client(redis_server):
    redis_server.flushdb()
    return redis_server
