"""Regex-based intent detection engine with confidence scoring.

Architecture:
 1. Accept a raw natural-language command string.
 2. Run every registered IntentPattern against it.
 3. Score matches by (pattern weight) * (match length / command length).
 4. Return the best match's intent, confidence, and extracted entities.

Post-processing:
 * For `docker.deploy`, the raw `image` entity is passed through
   `normalize_image_alias()` which canonicalizes typos and spacing
   (e.g. 'rabbbit mq' -> 'rabbitmq', 'mongo db' -> 'mongo').

This design is deliberately pluggable: swapping in an LLM-backed engine
later only requires conforming to the same `detect()` signature.
"""

from __future__ import annotations

import logging
from typing import Any

from app.intent.patterns import (
    ALL_PATTERNS,
    DESTRUCTIVE_INTENTS,
    IntentPattern,
    normalize_image_alias,
)
from app.schemas import IntentResult

logger = logging.getLogger(__name__)


class IntentEngine:
    """Detects the most likely intent from a natural language command."""

    def __init__(self, patterns: list[IntentPattern] | None = None) -> None:
        self.patterns: list[IntentPattern] = patterns or ALL_PATTERNS

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def detect(self, command: str) -> IntentResult:
        """Return the best matching intent or a fallback 'unknown' result."""
        if not command or not command.strip():
            return IntentResult(
                intent="unknown",
                confidence=0.0,
                entities={},
                matched_pattern=None,
            )

        cleaned = command.strip()
        best_intent: IntentResult | None = None
        best_score: float = 0.0

        for pat in self.patterns:
            match = pat.pattern.search(cleaned)
            if not match:
                continue
            score = self._score(pat, match, cleaned)
            if score > best_score:
                best_intent = IntentResult(
                    intent=pat.intent,
                    confidence=round(min(score, 1.0), 3),
                    entities=self._extract_entities(pat, match),
                    matched_pattern=pat.example or pat.pattern.pattern[:80],
                )
                best_score = score

        if best_intent:
            # Post-process the entities for known intents.
            best_intent = self._post_process(best_intent)
            logger.debug(
                "Intent detected: %s (confidence=%.2f, entities=%s)",
                best_intent.intent, best_intent.confidence, best_intent.entities,
            )
            return best_intent

        logger.info("No intent matched command: %r", cleaned[:100])
        return IntentResult(intent="unknown", confidence=0.0)

    @staticmethod
    def is_destructive(intent: str) -> bool:
        return intent in DESTRUCTIVE_INTENTS

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------
    @staticmethod
    def _score(pattern: IntentPattern, match, command: str) -> float:
        """Compute confidence: weight * (matched_span / command_length)."""
        span_len = match.end() - match.start()
        if not command:
            return 0.0
        coverage = min(1.0, span_len / max(len(command), 1))
        # Smooth so short commands still score well
        coverage = max(coverage, 0.35)
        return pattern.weight * coverage

    @staticmethod
    def _extract_entities(pattern: IntentPattern, match) -> dict[str, Any]:
        """Pull named groups out of the match into a typed dict."""
        groups = match.groupdict()
        result: dict[str, Any] = {}
        for name, value in groups.items():
            if value is None:
                continue
            # Auto-cast numeric entities
            if name in ("port", "replicas", "lines"):
                try:
                    result[name] = int(value)
                    continue
                except (TypeError, ValueError):
                    pass
            result[name] = value.strip()
        return result

    @staticmethod
    def _post_process(intent: IntentResult) -> IntentResult:
        """Normalize entities after a match.

        Currently:
          * `image` entities on docker.deploy / k8s.deploy are passed through
            the alias/typo table to get a clean, pullable image reference.
        """
        entities = dict(intent.entities or {})
        raw_image = entities.get("image")
        if raw_image and intent.intent in {"docker.deploy", "k8s.deploy"}:
            canonical = normalize_image_alias(raw_image)
            # Strip trailing "on port" fragments that slipped through
            canonical = canonical.split(" on ")[0].strip()
            if canonical:
                entities["image"] = canonical
                if raw_image.strip().lower() != canonical.lower():
                    entities["original_image"] = raw_image.strip()

        return IntentResult(
            intent=intent.intent,
            confidence=intent.confidence,
            entities=entities,
            matched_pattern=intent.matched_pattern,
        )


# Singleton used across the application
intent_engine = IntentEngine()
