# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

ARG DOCKER_CLI_VERSION=26.1.4
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io ca-certificates curl tar \
    && arch="$(dpkg --print-architecture)" \
    && case "$arch" in \
         amd64) docker_arch="x86_64" ;; \
         arm64) docker_arch="aarch64" ;; \
         *) echo "Unsupported architecture for Docker CLI: $arch" && exit 1 ;; \
       esac \
    && curl -fsSL "https://download.docker.com/linux/static/stable/${docker_arch}/docker-${DOCKER_CLI_VERSION}.tgz" -o /tmp/docker.tgz \
    && tar -xzf /tmp/docker.tgz -C /tmp \
    && install -m 0755 /tmp/docker/docker /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz \
    && rm -rf /var/lib/apt/lists/*

COPY services/worker/pyproject.toml /app/pyproject.toml
COPY services/worker/src /app/src

RUN --mount=type=cache,target=/root/.cache/pip pip install .

COPY games /app/games

EXPOSE 8020
CMD ["uvicorn", "worker_service.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8020", "--no-access-log"]
