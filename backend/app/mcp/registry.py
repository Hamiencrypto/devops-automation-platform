"""MCP-compliant tool registry.

Tools register themselves here at application startup. The registry provides:

 * Tool discovery by name
 * Tool lookup by declared intent
 * JSON-schema exposure (for UI and API documentation)
 * A uniform interface for invocation
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.schemas import ToolSchema

if TYPE_CHECKING:
    from app.tools.base import MCPTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all MCP tools."""

    def __init__(self) -> None:
        self._tools: dict[str, "MCPTool"] = {}
        self._intent_index: dict[str, str] = {}  # intent -> tool_name

    # -----------------------------------------------------------------
    # Registration
    # -----------------------------------------------------------------
    def register(self, tool: "MCPTool") -> None:
        """Register a tool and index it by its declared intents."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        for intent in tool.intents:
            if intent in self._intent_index:
                logger.warning(
                    "Intent '%s' already routed to '%s'; overriding with '%s'",
                    intent, self._intent_index[intent], tool.name,
                )
            self._intent_index[intent] = tool.name
        logger.info("Registered MCP tool: %s (intents=%s)", tool.name, tool.intents)

    def unregister(self, tool_name: str) -> None:
        tool = self._tools.pop(tool_name, None)
        if not tool:
            return
        for intent in tool.intents:
            if self._intent_index.get(intent) == tool_name:
                self._intent_index.pop(intent, None)

    # -----------------------------------------------------------------
    # Lookup
    # -----------------------------------------------------------------
    def get(self, tool_name: str) -> "MCPTool | None":
        return self._tools.get(tool_name)

    def route_intent(self, intent: str) -> "MCPTool | None":
        tool_name = self._intent_index.get(intent)
        return self._tools.get(tool_name) if tool_name else None

    def list_tools(self) -> list["MCPTool"]:
        return list(self._tools.values())

    def list_intents(self) -> list[str]:
        return sorted(self._intent_index.keys())

    # -----------------------------------------------------------------
    # MCP schema export
    # -----------------------------------------------------------------
    def to_schema(self) -> list[ToolSchema]:
        """Return MCP-compliant tool descriptions for API and UI consumption."""
        return [
            ToolSchema(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                intents=list(tool.intents),
                destructive=tool.destructive,
                category=tool.category,
            )
            for tool in self._tools.values()
        ]


# Singleton
tool_registry = ToolRegistry()
