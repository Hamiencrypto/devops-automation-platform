"""Dynamic MCP router.

Responsibilities:
 1. Take the IntentResult from the intent engine.
 2. Look up the appropriate MCP tool via the registry.
 3. Map extracted entities onto the tool's input schema.
 4. Validate parameters against the tool's JSON schema.
 5. Return a resolved MCPToolCall ready for execution.

This keeps intent detection and tool execution cleanly separated, so either
layer can be swapped independently (regex -> LLM, Docker -> Kubernetes, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from app.mcp.registry import tool_registry
from app.schemas import IntentResult, MCPToolCall

logger = logging.getLogger(__name__)


class MCPRouterError(Exception):
    """Raised when routing or parameter binding fails."""


class MCPRouter:
    """Routes detected intents to MCP tools with validated parameters."""

    def __init__(self, registry=None) -> None:
        self.registry = registry or tool_registry

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def route(self, intent_result: IntentResult) -> MCPToolCall:
        """Resolve an intent to a concrete tool invocation."""
        if intent_result.intent == "unknown":
            raise MCPRouterError(
                "Could not determine intent from the command. "
                "Try something like: 'deploy nginx', 'list containers', "
                "'analyze logs', or 'system health'."
            )

        tool = self.registry.route_intent(intent_result.intent)
        if not tool:
            raise MCPRouterError(
                f"Intent '{intent_result.intent}' is recognized but has no "
                "registered MCP tool handler."
            )

        params = self._bind_params(tool, intent_result)
        self._validate_params(tool, params)

        logger.info(
            "MCP routed intent=%s -> tool=%s with params=%s",
            intent_result.intent, tool.name, params,
        )
        return MCPToolCall(tool_name=tool.name, params=params)

    # -----------------------------------------------------------------
    # Parameter binding
    # -----------------------------------------------------------------
    def _bind_params(self, tool, intent_result: IntentResult) -> dict[str, Any]:
        """Map extracted entities and intent sub-type onto tool parameters."""
        params: dict[str, Any] = dict(intent_result.entities)
        # Inject the sub-action derived from the intent, e.g. 'docker.deploy' -> 'deploy'
        if "." in intent_result.intent:
            _, action = intent_result.intent.split(".", 1)
            params.setdefault("action", action)
        return params

    def _validate_params(self, tool, params: dict[str, Any]) -> None:
        """Lightweight JSON-schema required-field check."""
        schema = tool.input_schema or {}
        required = schema.get("required", [])
        missing = [k for k in required if k not in params or params[k] in (None, "")]
        if missing:
            raise MCPRouterError(
                f"Tool '{tool.name}' is missing required parameter(s): {missing}. "
                "Please include them in your command."
            )


# Singleton
mcp_router = MCPRouter()
