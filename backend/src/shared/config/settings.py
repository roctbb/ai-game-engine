from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Game Platform API"
    app_env: str = "development"
    debug: bool = True

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "game-engine"
    db_user: str = "postgres"
    db_password: str = "postgres"
    database_url_override: str | None = None

    redis_url: str = "redis://localhost:6379/0"
    scheduler_service_url: str | None = None
    builder_service_url: str | None = None
    enable_dev_login: bool = True
    enable_geekclass_login: bool = True
    jwt_secret: str = "change-me-in-prod-super-secret-key-32"
    jwt_max_age_seconds: int = 60
    geekclass_host: str = "https://codingprojects.ru"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8080"
    core_repository_backend: str = "memory"
    core_repository_auto_create_tables: bool = True
    execution_repository_backend: str = "memory"
    execution_repository_auto_create_tables: bool = True
    games_root: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
