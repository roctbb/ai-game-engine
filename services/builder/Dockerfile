# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/builder/pyproject.toml /app/pyproject.toml
COPY services/builder/src /app/src

RUN --mount=type=cache,target=/root/.cache/pip pip install .

EXPOSE 8030
CMD ["uvicorn", "builder_service.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8030", "--no-access-log"]
