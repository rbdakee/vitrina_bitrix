from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    db_host: str | None = Field(default=None, alias="DB_HOST")
    db_port: int | None = Field(default=None, alias="DB_PORT")
    db_name: str | None = Field(default=None, alias="DB_NAME")
    db_user: str | None = Field(default=None, alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")

    admin_api_token: str = Field(default="change-me", alias="ADMIN_API_TOKEN")

    bitrix_enabled: bool = Field(default=False, alias="BITRIX_ENABLED")
    bitrix_portal_domain: str | None = Field(default=None, alias="BITRIX_PORTAL_DOMAIN")
    bitrix_app_client_id: str | None = Field(default=None, alias="BITRIX_APP_CLIENT_ID")
    bitrix_app_client_secret: str | None = Field(default=None, alias="BITRIX_APP_CLIENT_SECRET")
    bitrix_app_public_base_url: str | None = Field(default=None, alias="BITRIX_APP_PUBLIC_BASE_URL")
    bitrix_deal_stage_id: str | None = Field(default=None, alias="BITRIX_DEAL_STAGE_ID")
    bitrix_deal_category_id: str | None = Field(default=None, alias="BITRIX_DEAL_CATEGORY_ID")
    bitrix_complex_cache_path: str = Field(
        default="var/complex_cache.json", alias="BITRIX_COMPLEX_CACHE_PATH"
    )

    request_timeout_seconds: float = Field(default=30.0, alias="REQUEST_TIMEOUT_SECONDS")
    skip_startup_validation: bool = Field(default=False, alias="SKIP_STARTUP_VALIDATION")

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.database_url

        missing = [name for name, value in (
            ("DB_HOST", self.db_host),
            ("DB_PORT", self.db_port),
            ("DB_NAME", self.db_name),
            ("DB_USER", self.db_user),
        ) if not value]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Database settings are incomplete. Missing: {joined}")

        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def bitrix_toolbar_url(self) -> str | None:
        if not self.bitrix_app_public_base_url:
            return None
        return f"{self.bitrix_app_public_base_url.rstrip('/')}/bitrix/toolbar"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

