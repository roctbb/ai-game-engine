from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Scheduler Service"
    redis_url: str = "redis://localhost:6379/0"
    queue_key: str = "agp:runs:queued"
    queued_set_key: str = "agp:runs:queued:set"
    known_set_key: str = "agp:runs:known"
    run_lease_hash_key: str = "agp:runs:leases"
    run_requirements_hash_key: str = "agp:runs:requirements"
    lease_ttl_seconds: int = 30
    lease_requeue_check_interval_seconds: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
