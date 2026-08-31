"""
Guardrails — the single gate every execution passes through.

Ordering, and why it is this ordering:

  1. raw-text sanity      cheap, bounded checks on the sentence itself
  2. structured validation schema + policy on the resolved tool call
  3. destructive intent    does this need a human to confirm or approve

Step 1 is not an allowlist. Allowlisting raw natural language would defeat the
point of having a language model read it. What step 1 does is bound the input:
length, control characters, and a small banned-token filter that catches the
obvious. It is defence in depth, not the security boundary.

Step 2 is the security boundary. It runs identically whether the intent came
from a regex pattern or a model, because a regex that emits
`{"path": "/etc/shadow"}` is exactly as dangerous as a model that does.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.safety.structured_validator import StructuredOutputValidator

log = logging.getLogger(__name__)


@dataclass
class GuardrailDecision:
    allowed: bool
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    requires_approval: bool = False
    params: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.allowed


# Destructive by intent name, not by parsing English. The intent is already
# resolved at this point, so there is no need to guess from the wording — and
# guessing from wording is how "please remove the old container" slips past a
# filter looking for the word "delete".
DESTRUCTIVE_INTENTS = frozenset(
    {
        "docker.stop", "docker.remove", "docker.restart", "docker.kill",
        "docker.prune", "file.delete", "file.write", "kubernetes.scale",
        "kubernetes.delete", "kubernetes.rollout_restart", "system.reboot",
    }
)

# Actions that additionally need a second person, not just a checkbox from the
# operator who typed them.
APPROVAL_INTENTS = frozenset(
    {"docker.remove", "docker.prune", "kubernetes.delete", "system.reboot"}
)

BANNED_TOKENS = (
    r"rm\s+-[rf]{1,2}\s+/",
    r":\(\)\s*\{.*\|\s*:",          # fork bomb
    r"mkfs(\.\w+)?\s",
    r"dd\s+if=.*of=/dev/",
    r">\s*/dev/sd[a-z]",
    r"chmod\s+-R\s+777\s+/",
    r"curl[^|]*\|\s*(ba)?sh",
    r"wget[^|]*\|\s*(ba)?sh",
)
_BANNED = [re.compile(p, re.IGNORECASE) for p in BANNED_TOKENS]

MAX_COMMAND_CHARS = 1_000
LOW_CONFIDENCE_WARN = 0.75


class Guardrails:
    def __init__(
        self,
        validator: StructuredOutputValidator,
        *,
        require_approval_for: frozenset[str] = APPROVAL_INTENTS,
        destructive_intents: frozenset[str] = DESTRUCTIVE_INTENTS,
    ):
        self.validator = validator
        self.approval_intents = require_approval_for
        self.destructive_intents = destructive_intents

    # -- step 1 ------------------------------------------------------------

    def check_raw(self, command: str) -> GuardrailDecision:
        if not command or not command.strip():
            return GuardrailDecision(False, "Enter a command to run.")

        if len(command) > MAX_COMMAND_CHARS:
            return GuardrailDecision(
                False, f"Commands are limited to {MAX_COMMAND_CHARS} characters."
            )

        # Normalise before matching so homoglyph and compatibility-form tricks
        # do not slide past the token filter.
        normalised = unicodedata.normalize("NFKC", command)

        if any(ord(c) < 32 and c not in "\t\n" for c in normalised):
            return GuardrailDecision(False, "Command contains control characters.")

        for pattern in _BANNED:
            if pattern.search(normalised):
                log.warning("banned token matched in command: %s", pattern.pattern)
                return GuardrailDecision(
                    False, "This command matches a pattern the platform refuses to run."
                )

        return GuardrailDecision(True)

    # -- steps 2 and 3 -----------------------------------------------------

    def check(self, intent, tool_name: str, *, confirm_destructive: bool = False,
              user_role: str = "developer") -> GuardrailDecision:
        """
        `intent` is the object from HybridIntentEngine. Note that nothing here
        reads `intent.source`. That is deliberate and worth stating plainly:
        there is no branch where a model-derived call is trusted more or less
        than a pattern-derived one.
        """
        warnings: list[str] = []

        result = self.validator.validate_tool_call(tool_name, intent.entities)
        if not result:
            return GuardrailDecision(False, result.reason)

        params = result.params or dict(intent.entities)

        if intent.confidence < LOW_CONFIDENCE_WARN:
            warnings.append(
                f"Intent matched at {intent.confidence:.0%} confidence. "
                "Check the tool call below before continuing."
            )

        is_destructive = intent.name in self.destructive_intents
        needs_approval = intent.name in self.approval_intents

        if needs_approval and user_role != "admin":
            return GuardrailDecision(
                True,
                warnings=warnings,
                requires_approval=True,
                params=params,
                reason="This action needs approval from an administrator.",
            )

        if is_destructive and not confirm_destructive:
            return GuardrailDecision(
                False,
                reason=(
                    "This action changes or removes running infrastructure. "
                    "Resend with confirmation to proceed."
                ),
                warnings=warnings,
                requires_confirmation=True,
                params=params,
            )

        return GuardrailDecision(True, warnings=warnings, params=params)
