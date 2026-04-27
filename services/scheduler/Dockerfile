# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/scheduler/pyproject.toml /app/pyproject.toml
COPY services/scheduler/src /app/src

RUN --mount=type=cache,target=/root/.cache/pip pip install .

EXPOSE 8010
CMD ["uvicorn", "scheduler_service.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8010", "--no-access-log"]
