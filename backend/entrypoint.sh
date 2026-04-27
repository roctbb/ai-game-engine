#!/bin/sh
set -e
cd /app
alembic upgrade head
exec uvicorn app.main:app --app-dir src --host 0.0.0.0 --port 8000 --workers "${BACKEND_WORKERS:-2}"
