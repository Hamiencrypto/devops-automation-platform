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


class OllamaProvider(LLMProvider):
    """
    Local inference via Ollama.

    Chosen over a hosted API for a reason worth stating plainly: DevOps
    commands carry infrastructure details — container names, paths, ports,
    cluster topology. Sending those to a third party is a data-egress decision
    many operators cannot make. Running the model on the same host removes
    that question, and removes the API bill with it.

    The trade-off is capability. A 3B model is meaningfully weaker than a
    frontier model and will sometimes propose the wrong tool. That is a
    usability cost, not a safety one: every proposal is still checked against
    the tool's JSON Schema and its operational policy before anything runs, so
    a weaker model produces more rejections, never a wider blast radius.
    """

    def __init__(self, host, model, timeout=120.0, temperature=0.0):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        # Deterministic decoding: the same sentence should resolve to the same
        # tool call every time. Creativity is not a virtue here.
        self.temperature = temperature

    def complete(self, *, system, messages, tools, max_tokens):
        import json

        import requests

        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = [
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
            resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError as exc:
            raise LLMError(
                f"cannot reach Ollama at {self.host}. Is `ollama serve` running?"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise LLMError(
                f"Ollama did not respond within {self.timeout}s. A cold model load can "
                "exceed this; retry once the model is resident."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc

        if resp.status_code == 404:
            raise LLMError(f"model {self.model!r} is not pulled. Run: ollama pull {self.model}")
        if resp.status_code >= 400:
            raise LLMError(f"Ollama returned {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMError("Ollama returned a non-JSON response") from exc

        message = data.get("message") or {}
        calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name")
            if not name:
                continue
            args = fn.get("arguments")
            # Usually an object, but some models emit a JSON string. Accept
            # both rather than silently dropping the call.
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    log.warning("Ollama returned unparseable arguments for %s", name)
                    continue
            if not isinstance(args, dict):
                log.warning("Ollama returned non-object arguments for %s", name)
                continue
            calls.append(ToolCall(name=name, arguments=args))

        return ProviderResponse(
            tool_calls=calls,
            text=message.get("content") or "",
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            model=self.model,
        )

    def ping(self) -> bool:
        try:
            import requests

            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            names = {m.get("name", "") for m in resp.json().get("models", [])}
            return any(n == self.model or n.startswith(f"{self.model}:") for n in names)
        except Exception as exc:
            log.warning("Ollama ping failed: %s", exc)
            return False


def build_provider(settings) -> LLMProvider | None:
    """
    Factory driven by config. Returns None when LLM is disabled or unconfigured
    — callers treat None as 'regex only', which is a valid running state.
    """
    if not settings.ENABLE_LLM:
        log.info("LLM disabled by config; using regex intent engine only")
        return None
    provider = settings.LLM_PROVIDER.lower()

    # Ollama runs locally and needs no credential; the key check below applies
    # only to hosted providers.
    if provider == "ollama":
        return OllamaProvider(
            settings.OLLAMA_HOST, settings.LLM_MODEL, settings.LLM_TIMEOUT_SECONDS
        )

    if not settings.LLM_API_KEY:
        log.warning("ENABLE_LLM=true but LLM_API_KEY is empty; falling back to regex only")
        return None

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
