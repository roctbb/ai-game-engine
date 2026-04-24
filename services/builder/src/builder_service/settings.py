from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Builder Service"
    backend_api_url: str = "http://localhost:8000/api/v1"
    internal_api_token: str = "dev-internal-token"
    request_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
