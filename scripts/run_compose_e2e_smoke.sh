#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/compose.yml"
SMOKE_SCRIPT="$ROOT_DIR/scripts/e2e_distributed_smoke.py"

PROJECT_NAME="agp-e2e-$(date +%s)"
TIMEOUT_SEC=30
NO_BUILD=false
KEEP_UP=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --project-name <name>   Docker compose project name (default: $PROJECT_NAME)
  --timeout <sec>         Timeout for smoke run final wait (default: $TIMEOUT_SEC)
  --no-build              Skip compose build step
  --keep-up               Do not teardown compose stack after run
  -h, --help              Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-name)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SEC="$2"
      shift 2
      ;;
    --no-build)
      NO_BUILD=true
      shift
      ;;
    --keep-up)
      KEEP_UP=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 127
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "compose.yml not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$SMOKE_SCRIPT" ]]; then
  echo "Smoke script not found: $SMOKE_SCRIPT" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 127
fi

teardown() {
  if [[ "$KEEP_UP" == "true" ]]; then
    echo "[teardown] skip (keep-up enabled), project=$PROJECT_NAME"
    return
  fi

  echo "[teardown] docker compose down..."
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
}

on_exit() {
  local exit_code="$1"
  if [[ "$exit_code" -ne 0 ]]; then
    echo "[failure] compose stack status:"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps || true
    echo "[failure] recent service logs:"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs --no-color --tail=200 \
      postgres redis backend-api scheduler-service worker-service builder-service frontend || true
  fi
  teardown
}

trap 'rc=$?; trap - EXIT; on_exit "$rc"; exit "$rc"' EXIT

cd "$ROOT_DIR"

echo "[1/5] project=$PROJECT_NAME"

echo "[2/5] docker compose up..."
if [[ "$NO_BUILD" == "true" ]]; then
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d
else
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build
fi

echo "[3/5] wait for health endpoints..."
"$PYTHON_BIN" - "$TIMEOUT_SEC" <<'PY'
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

TIMEOUT = int(sys.argv[1])

TARGETS = [
    ("backend", "http://localhost:8000/api/v1/health"),
    ("scheduler", "http://localhost:8010/health"),
    ("worker", "http://localhost:8020/health"),
    ("builder", "http://localhost:8030/health"),
    ("frontend", "http://localhost:8080"),
]


def is_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


deadline = time.time() + TIMEOUT
pending = {name: url for name, url in TARGETS}

while pending and time.time() < deadline:
    done = []
    for name, url in pending.items():
        if is_ok(url):
            print(f"ready: {name} -> {url}")
            done.append(name)
    for name in done:
        pending.pop(name, None)
    if pending:
        time.sleep(0.5)

if pending:
    print(f"Timeout while waiting for: {pending}", file=sys.stderr)
    raise SystemExit(1)
PY

echo "[4/5] run distributed smoke..."
"$PYTHON_BIN" "$SMOKE_SCRIPT" \
  --backend "http://localhost:8000/api/v1" \
  --scheduler "http://localhost:8010" \
  --worker "http://localhost:8020" \
  --timeout "$TIMEOUT_SEC"

echo "[5/5] success"
