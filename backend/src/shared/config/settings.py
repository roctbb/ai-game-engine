from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


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
    matchmaking_lock_ttl_seconds: float = 30.0
    matchmaking_lock_blocking_timeout_seconds: float = 5.0
    training_lobby_auto_matchmaking_enabled: bool = False
    training_lobby_auto_matchmaking_interval_seconds: float = 1.0
    scheduler_service_url: str | None = None
    builder_service_url: str | None = None
    enable_dev_login: bool = True
    enable_geekclass_login: bool = True
    jwt_secret: str = "change-me-in-prod-super-secret-key-32"
    jwt_max_age_seconds: int = 60
    internal_api_token: str = "dev-internal-token"
    geekclass_host: str = "https://codingprojects.ru"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8080"
    core_repository_backend: str = "memory"
    core_repository_auto_create_tables: bool = True
    execution_repository_backend: str = "memory"
    execution_repository_auto_create_tables: bool = True
    session_repository_backend: str = "memory"
    session_repository_auto_create_tables: bool = True
    games_root: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(
            hide_password=False
        )


settings = Settings()
