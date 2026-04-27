from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Game Worker Service"
    scheduler_url: str = "http://localhost:8010"
    backend_api_url: str = "http://localhost:8000/api/v1"
    internal_api_token: str = "dev-internal-token"
    worker_id: str = "worker-local-1"
    hostname: str = "localhost"
    max_slots: int = 1
    worker_labels: dict[str, str] = {}
    games_root: str = "/app/games"
    execution_mode: Literal["docker", "local_process"] = "docker"
    docker_binary: str = "docker"
    docker_image: str = "python:3.12-slim"
    docker_network_mode: str = "none"
    docker_log_driver: str = "json-file"
    docker_log_max_size: str = "10m"
    docker_log_max_file: str = "3"
    docker_cpu_limit: str = "1.0"
    docker_memory_limit: str = "256m"
    docker_pids_limit: int = 128
    docker_tmpfs_size: str = "64m"
    execution_timeout_seconds: float = 5.0
    engine_timeout_cap_seconds: float = 60.0
    result_max_turns: int = 500
    request_timeout_seconds: float = 5.0
    request_max_attempts: int = 3
    retry_base_delay_ms: int = 100
    retry_max_delay_ms: int = 1000
    auto_poll_enabled: bool = False
    auto_poll_interval_seconds: float = 1.0
    auto_poll_error_backoff_seconds: float = 3.0
    worker_registration_ttl_seconds: float = 30.0
    worker_heartbeat_interval_seconds: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
