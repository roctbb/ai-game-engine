"""Track engine processes so cancellation also stops execution and descendants."""

from __future__ import annotations

import os
import signal
import subprocess
from threading import Event, Lock
from typing import Any

_lock = Lock()
_processes: dict[str, subprocess.Popen[Any]] = {}
_stops: dict[str, Event] = {}


def prepare(run_id: str) -> None:
    with _lock:
        _stops[run_id] = Event()


def _kill(process: subprocess.Popen[Any]) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def stop(run_id: str) -> None:
    with _lock:
        event = _stops.setdefault(run_id, Event())
        event.set()
        process = _processes.get(run_id)
        if process is not None:
            _kill(process)


def forget(run_id: str) -> None:
    with _lock:
        _stops.pop(run_id, None)
        _processes.pop(run_id, None)


def run_command(
    command: list[str],
    *,
    context: dict[str, object],
    timeout: float,
    input: bytes | str | None = None,
    text: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    run_id = str(context.get("run_id", "offline"))
    kwargs.pop("capture_output", None)
    kwargs.pop("check", None)
    with _lock:
        if _stops.get(run_id, Event()).is_set():
            raise RuntimeError("Execution canceled before process startup")
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            start_new_session=True,
            **kwargs,
        )
        _processes[run_id] = process
    try:
        try:
            stdout, stderr = process.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill(process)
            process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        with _lock:
            _processes.pop(run_id, None)
