from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BSM_",
        env_file=".env",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    database_url: str = "postgresql+psycopg://bsm:bsm-change-me@postgres:5432/bsm"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "change-me-in-production"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000
    agent_token_ttl_seconds: int = 7_776_000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
