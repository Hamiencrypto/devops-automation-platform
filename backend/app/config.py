"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import model_validator
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

    # ----------------------------------------------------------------
    # LLM intent layer
    # ----------------------------------------------------------------
    # Off by default. The platform runs fine on regex alone; turning this on
    # adds natural-language understanding and a per-request API cost.
    ENABLE_LLM: bool = False
    LLM_PROVIDER: str = "ollama"      # ollama | anthropic | openai
    # Ollama runs on the host, not in the compose network, so the backend
    # container reaches it through Docker's host gateway alias.
    OLLAMA_HOST: str = "http://host.docker.internal:11434"
    LLM_MODEL: str = "claude-haiku-4-5"
    LLM_API_KEY: str = ""
    LLM_THRESHOLD: float = 0.65       # regex confidence below this asks the model
    LLM_MAX_TOKENS: int = 512
    LLM_TIMEOUT_SECONDS: float = 20.0
    LLM_CACHE_TTL: int = 86_400
    LLM_CACHE_MAX_ENTRIES: int = 2_000
    LLM_MAX_COMMAND_CHARS: int = 1_000
    LLM_DAILY_TOKEN_BUDGET: int = 50_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _auth_required_outside_dev(self) -> "Settings":
        """
        Fail closed: `ENABLE_AUTH=false` is only permitted when `ENVIRONMENT`
        is explicitly "development". Anything else — staging, production, an
        unset default, a typo — must not boot with every endpoint open. The
        failure mode being guarded against is silent: a deploy that comes up
        cheerfully with no authentication is not something anyone will
        notice from the outside until it's found the hard way.
        """
        if self.ENVIRONMENT.strip().lower() != "development" and not self.ENABLE_AUTH:
            raise ValueError(
                f"ENABLE_AUTH must be true when ENVIRONMENT={self.ENVIRONMENT!r} "
                "(only ENVIRONMENT=development may run with auth disabled)"
            )
        return self


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton accessor for settings."""
    return Settings()


settings = get_settings()
