"""Base classes for MCP-compliant tools.

Every tool implements:

 * `name`          – unique identifier used in the registry
 * `description`   – human-readable, surfaces in UI and API docs
 * `input_schema`  – JSON-Schema describing expected params
 * `intents`       – set of intent names this tool handles
 * `destructive`   – True if a run can delete or disrupt state
 * `category`      – grouping for UI (docker / logs / file / ...)
 * `execute()`     – performs the actual work and returns a ToolResult

Dry-run semantics: if `dry_run=True` is passed in params, the tool must
describe what it *would* do without performing side effects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Normalized output of any MCPTool.execute() call."""

    success: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "summary": self.summary,
            "data": self.data,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "warnings": self.warnings,
        }


class MCPTool(ABC):
    """Abstract base for all MCP tools."""

    # Subclasses MUST override these.
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    intents: tuple[str, ...] = ()
    destructive: bool = False
    category: str = "general"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Sanity-check subclass contract.
        if cls is not MCPTool and not cls.name:
            raise TypeError(
                f"{cls.__name__} must define a non-empty 'name' attribute"
            )

    @abstractmethod
    def execute(self, params: dict[str, Any], dry_run: bool = False) -> ToolResult:
        """Run the tool. Override in subclasses."""
        raise NotImplementedError

    # -----------------------------------------------------------------
    # Convenience helpers
    # -----------------------------------------------------------------
    @staticmethod
    def ok(summary: str, **data: Any) -> ToolResult:
        return ToolResult(success=True, summary=summary, data=data)

    @staticmethod
    def fail(summary: str, stderr: str = "", **data: Any) -> ToolResult:
        return ToolResult(success=False, summary=summary, stderr=stderr, data=data)
