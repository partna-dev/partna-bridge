from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BRIDGE_", extra="ignore")

    engine_url: str = "https://partners.partnr.icu"
    engine_api_key: str = ""
    public_url: str = "http://localhost:8020"
    brand: str = "Партнёрская программа"
    currency: str = "RUB"
    destination_url: str = "http://localhost:3000"
    bridge_token: str = ""
    webhook_secret: str = ""
    allowed_origins: str = ""
    cookie_days: int = 30
    cookie_name: str = "pn_ref"
    timeout_seconds: float = 10.0
    outbox_db: str = "/data/bridge.sqlite3"
    outbox_mode: str = "queue"
    poll_seconds: float = 5.0

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
