"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized settings. Override with environment variables or .env file."""

    # ----------------------------------------------------------------
    # App metadata
    # ----------------------------------------------------------------
    APP_NAME: str = "DevOps MCP Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ----------------------------------------------------------------
    # Server
    # ----------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ----------------------------------------------------------------
    # Database
    # ----------------------------------------------------------------
    DATABASE_URL: str = (
        "postgresql+psycopg2://devops:devops_pass@db:5432/devops_mcp"
    )
    DATABASE_ECHO: bool = False

    # ----------------------------------------------------------------
    # Security
    # ----------------------------------------------------------------
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ENABLE_AUTH: bool = False  # Set True to require JWT on /execute

    # ----------------------------------------------------------------
    # Docker
    # ----------------------------------------------------------------
    DOCKER_SOCKET: str = "unix:///var/run/docker.sock"
    DOCKER_NETWORK: str = "devops-mcp-net"
    CONTAINER_PREFIX: str = "mcp-managed-"

    # ----------------------------------------------------------------
    # Safety / Guardrails
    # ----------------------------------------------------------------
    ENABLE_DRY_RUN_DEFAULT: bool = False
    REQUIRE_CONFIRM_DESTRUCTIVE: bool = True
    MAX_EXECUTIONS_PER_MINUTE: int = 30
    MAX_FILE_SIZE_MB: int = 50

    # ----------------------------------------------------------------
    # Logging
    # ----------------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton accessor for settings."""
    return Settings()


settings = get_settings()
