"""
Tests for the fail-closed startup guard: ENABLE_AUTH=false is only permitted
when ENVIRONMENT=development. Everything else — staging, production, an
unset/typo'd value — must refuse to construct Settings rather than boot with
every endpoint open.

Settings is a pydantic-settings BaseSettings, so it reads from the process
environment / .env at construction time. These tests construct it directly
with explicit kwargs (bypassing env/`.env` entirely via `_env_file=None`) so
they're independent of whatever this machine's actual `.env` says.
"""

import pytest

from app.config import Settings


def build(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_dev_with_auth_disabled_boots():
    settings = build(ENVIRONMENT="development", ENABLE_AUTH=False)
    assert settings.ENABLE_AUTH is False


def test_dev_is_case_insensitive():
    settings = build(ENVIRONMENT="Development", ENABLE_AUTH=False)
    assert settings.ENVIRONMENT == "Development"


@pytest.mark.parametrize("environment", ["production", "staging", "prod", "PRODUCTION", ""])
def test_non_dev_with_auth_disabled_refuses_to_boot(environment):
    with pytest.raises(ValueError, match="ENABLE_AUTH must be true"):
        build(ENVIRONMENT=environment, ENABLE_AUTH=False)


def test_non_dev_with_auth_enabled_boots():
    settings = build(ENVIRONMENT="production", ENABLE_AUTH=True)
    assert settings.ENABLE_AUTH is True


def test_dev_with_auth_enabled_boots():
    settings = build(ENVIRONMENT="development", ENABLE_AUTH=True)
    assert settings.ENABLE_AUTH is True
