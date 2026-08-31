"""Safety guardrails: destructive-command detection, rate limiting, input filters."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from app.config import settings
from app.intent.engine import intent_engine
from app.schemas import IntentResult

logger = logging.getLogger(__name__)


class SafetyError(Exception):
    """Raised when a command is blocked by the safety layer."""


@dataclass
class SafetyCheck:
    allowed: bool
    reason: str = ""
    warnings: list[str] = None  # type: ignore[assignment]
    require_confirmation: bool = False


# ---------------------------------------------------------------------
# Blocked / banned token list
# ---------------------------------------------------------------------
BANNED_TOKENS = [
    r"\brm\s+-rf\s+/\b",
    r":\s*\(\s*\)\s*\{.*\}\s*;.*:\s*&",  # fork bomb
    r"\bmkfs\.",  # filesystem formatting
    r"\bdd\s+if=.*of=/dev/",  # disk writes
    r"\bchmod\s+-R\s+777\s+/\b",
    r"\s>\s+/dev/sd[a-z]",
]
BANNED_RE = [re.compile(p, re.IGNORECASE) for p in BANNED_TOKENS]


class Guardrails:

    def __init__(self) -> None:
        self._validator = StructuredOutputValidator(tool_registry, SafetyPolicy())

    def __init__(self) -> None:
        self._validator = StructuredOutputValidator(tool_registry, SafetyPolicy())
    """Evaluates whether a natural-language command is safe to execute."""

    def check(
        self, command: str, intent: IntentResult, confirm_destructive: bool = False
    ) -> SafetyCheck:
        warnings: list[str] = []

        # 1. Banned tokens
        for rex in BANNED_RE:
            if rex.search(command):
                return SafetyCheck(
                    allowed=False,
                    reason=(
                        "Command contains a dangerous pattern that is blocked "
                        "by platform policy."
                    ),
                    warnings=warnings,
                )

        # 2. Unknown intent
        if intent.intent == "unknown":
            warnings.append("Intent could not be determined from the input.")

        # 3. Low confidence warning
        if 0 < intent.confidence < 0.45:
            warnings.append(
                f"Low-confidence intent match ({intent.confidence:.2f}). "
                "Double-check the action."
            )

        # 4. Destructive operations require explicit user confirmation
        if (
            intent_engine.is_destructive(intent.intent)
            and settings.REQUIRE_CONFIRM_DESTRUCTIVE
            and not confirm_destructive
        ):
            return SafetyCheck(
                allowed=False,
                reason=(
                    f"Action '{intent.intent}' is destructive. "
                    "Re-submit with `confirm_destructive=true` to proceed."
                ),
                warnings=warnings,
                require_confirmation=True,
            )

        return SafetyCheck(allowed=True, reason="", warnings=warnings)


guardrails = Guardrails()


# ---------------------------------------------------------------------
# In-memory rate limiter (per-user, sliding 60s window)
# ---------------------------------------------------------------------
class RateLimiter:
    def __init__(self, limit_per_minute: int | None = None) -> None:
        self.limit = limit_per_minute or settings.MAX_EXECUTIONS_PER_MINUTE
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, remaining). Evicts old entries."""
        now = time.monotonic()
        window_start = now - 60
        bucket = self._buckets[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False, 0
        bucket.append(now)
        return True, self.limit - len(bucket)


rate_limiter = RateLimiter()
