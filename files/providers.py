"""
LLM provider abstraction.

The rest of the intent layer never imports `anthropic` or `openai` directly.
It talks to a `LLMProvider` and gets back a normalised `ProviderResponse`.
That keeps the engine testable (a fake provider is ~10 lines) and makes
swapping vendors a config change rather than a refactor.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


class LLMError(Exception):
    """Base for all provider failures. The engine catches this and falls back."""


class LLMRateLimitError(LLMError):
    """Provider returned 429 / overloaded. Worth retrying, but not right now."""


class LLMAuthError(LLMError):
    """Bad or missing API key. Retrying will not help — log loudly."""


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ProviderResponse:
    """Normalised shape returned by every provider."""

    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    """Interface every provider must satisfy."""

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> ProviderResponse:
        ...

    @abstractmethod
    def ping(self) -> bool:
        """Cheap liveness check used by /health. Must not raise."""


class AnthropicProvider(LLMProvider):
    """
    Anthropic Messages API.

    Tool schemas are passed through unchanged — our MCP `input_schema` is
    already a JSON Schema object, which is exactly what this API expects.
    That is the whole reason the MCP registry pays off here.
    """

    def __init__(self, api_key: str, model: str, timeout: float = 20.0):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise LLMError(
                "anthropic package not installed. Add `anthropic>=0.40` to requirements.txt"
            ) from exc

        self._sdk = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.model = model

    def complete(self, *, system, messages, tools, max_tokens):
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
            )
        except self._sdk.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except (self._sdk.RateLimitError, self._sdk.APIStatusError) as exc:
            status = getattr(exc, "status_code", None)
            if status in (429, 529):
                raise LLMRateLimitError(str(exc)) from exc
            raise LLMError(f"anthropic api error (status={status}): {exc}") from exc
        except Exception as exc:  # network, timeout, malformed payload
            raise LLMError(f"anthropic request failed: {exc}") from exc

        calls, text = [], []
        for block in resp.content:
            if block.type == "tool_use":
                calls.append(ToolCall(name=block.name, arguments=dict(block.input)))
            elif block.type == "text":
                text.append(block.text)

        return ProviderResponse(
            tool_calls=calls,
            text="\n".join(text),
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            model=self.model,
        )

    def ping(self) -> bool:
        try:
            self._client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ok"}],
            )
            return True
        except Exception as exc:
            log.warning("anthropic ping failed: %s", exc)
            return False


class OpenAIProvider(LLMProvider):
    """
    OpenAI Chat Completions. Included so the platform is not vendor-locked —
    a legitimate thing to be asked about in a viva.

    Note the schema key differs: OpenAI wants `parameters`, Anthropic wants
    `input_schema`. Translation happens here, not in the engine.
    """

    def __init__(self, api_key: str, model: str, timeout: float = 20.0):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - import guard
            raise LLMError("openai package not installed") from exc

        self._sdk = openai
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self.model = model

    def complete(self, *, system, messages, tools, max_tokens):
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, *messages],
                tools=oai_tools,
            )
        except self._sdk.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except self._sdk.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except Exception as exc:
            raise LLMError(f"openai request failed: {exc}") from exc

        import json

        choice = resp.choices[0].message
        calls = []
        for tc in choice.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                log.warning("openai returned unparseable tool arguments; skipping call")
                continue
            calls.append(ToolCall(name=tc.function.name, arguments=args))

        return ProviderResponse(
            tool_calls=calls,
            text=choice.content or "",
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
            model=self.model,
        )

    def ping(self) -> bool:
        try:
            self._client.models.retrieve(self.model)
            return True
        except Exception as exc:
            log.warning("openai ping failed: %s", exc)
            return False


def build_provider(settings) -> LLMProvider | None:
    """
    Factory driven by config. Returns None when LLM is disabled or unconfigured
    — callers treat None as 'regex only', which is a valid running state.
    """
    if not settings.ENABLE_LLM:
        log.info("LLM disabled by config; using regex intent engine only")
        return None
    if not settings.LLM_API_KEY:
        log.warning("ENABLE_LLM=true but LLM_API_KEY is empty; falling back to regex only")
        return None

    provider = settings.LLM_PROVIDER.lower()
    try:
        if provider == "anthropic":
            return AnthropicProvider(
                settings.LLM_API_KEY, settings.LLM_MODEL, settings.LLM_TIMEOUT_SECONDS
            )
        if provider == "openai":
            return OpenAIProvider(
                settings.LLM_API_KEY, settings.LLM_MODEL, settings.LLM_TIMEOUT_SECONDS
            )
    except LLMError as exc:
        log.error("could not build LLM provider: %s", exc)
        return None

    log.error("unknown LLM_PROVIDER %r; falling back to regex only", provider)
    return None
