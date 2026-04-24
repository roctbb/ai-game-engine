#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

WITH_SMOKE=0
WITH_COMPOSE_SMOKE=0
BACKEND_URL="${BACKEND_URL:-http://localhost:8000/api/v1}"
SCHEDULER_URL="${SCHEDULER_URL:-http://localhost:8010}"
WORKER_URL="${WORKER_URL:-http://localhost:8020}"
SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-60}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-smoke)
      WITH_SMOKE=1
      shift
      ;;
    --with-compose-smoke)
      WITH_COMPOSE_SMOKE=1
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: scripts/verify_v2.sh [--with-smoke] [--with-compose-smoke]"
      exit 2
      ;;
  esac
done

echo "[1/4] backend+services tests"
pytest -q backend/tests services/scheduler/tests services/worker/tests services/builder/tests

echo "[2/4] frontend build"
npm --prefix frontend run build

echo "[3/4] python smoke script syntax check"
python3 -m py_compile scripts/e2e_distributed_smoke.py

if [[ "$WITH_COMPOSE_SMOKE" -eq 1 ]]; then
  echo "[4/4] distributed compose smoke execution"
  bash scripts/run_compose_e2e_smoke.sh --timeout "$SMOKE_TIMEOUT"
elif [[ "$WITH_SMOKE" -eq 1 ]]; then
  echo "[4/4] distributed smoke execution"
  python3 scripts/e2e_distributed_smoke.py \
    --backend "$BACKEND_URL" \
    --scheduler "$SCHEDULER_URL" \
    --worker "$WORKER_URL" \
    --timeout "$SMOKE_TIMEOUT"
else
  echo "[4/4] distributed smoke execution skipped (use --with-smoke)"
fi

echo "verify_v2: OK"
