"""Tests for the safety guardrails and rate limiter."""

import pytest

from app.safety.guardrails import Guardrails, RateLimiter
from app.schemas import IntentResult


@pytest.fixture
def guards():
    return Guardrails()


class TestGuardrails:
    def test_allows_safe_command(self, guards):
        intent = IntentResult(intent="docker.list", confidence=0.9)
        check = guards.check("list all containers", intent, False)
        assert check.allowed is True

    def test_blocks_banned_pattern(self, guards):
        intent = IntentResult(intent="unknown", confidence=0.0)
        check = guards.check("rm -rf /", intent, False)
        assert check.allowed is False

    def test_destructive_requires_confirmation(self, guards):
        intent = IntentResult(intent="docker.stop", confidence=0.9)
        check = guards.check("stop nginx", intent, confirm_destructive=False)
        assert check.allowed is False
        assert check.require_confirmation is True

    def test_destructive_allowed_with_confirmation(self, guards):
        intent = IntentResult(intent="docker.stop", confidence=0.9)
        check = guards.check("stop nginx", intent, confirm_destructive=True)
        assert check.allowed is True

    def test_low_confidence_warning(self, guards):
        intent = IntentResult(intent="docker.list", confidence=0.2)
        check = guards.check("sort of list things", intent, False)
        assert check.allowed is True
        assert any("Low-confidence" in w for w in (check.warnings or []))


class TestRateLimiter:
    def test_allow_within_limit(self):
        rl = RateLimiter(limit_per_minute=3)
        assert rl.allow("user:1")[0] is True
        assert rl.allow("user:1")[0] is True
        assert rl.allow("user:1")[0] is True

    def test_block_over_limit(self):
        rl = RateLimiter(limit_per_minute=2)
        rl.allow("user:1")
        rl.allow("user:1")
        allowed, remaining = rl.allow("user:1")
        assert allowed is False
        assert remaining == 0

    def test_separate_buckets_per_user(self):
        rl = RateLimiter(limit_per_minute=1)
        assert rl.allow("user:1")[0] is True
        assert rl.allow("user:2")[0] is True
        assert rl.allow("user:1")[0] is False
