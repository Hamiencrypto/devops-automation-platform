"""
The single sanctioned path from a tool name + params to a validated tool.

Every caller that wants to run an MCP tool — the natural-language executor,
the direct container-management API, and anything added after this comment —
resolves the tool through `resolve_and_validate()` before calling
`MCPTool.execute()`. That used to be a convention two call sites happened to
follow independently; one of them (`app/api/containers.py`) stopped
following it and called `tool.execute()` directly, silently bypassing
`guardrails.validate_params()` and the protected-container policy with it.

Centralising the lookup+validate step here doesn't make a bypass impossible
by itself — Python won't stop a future call site from fetching the tool
straight off `tool_registry` again. `tests/test_tool_execution_boundary.py`
is what makes it structurally hard to reintroduce: it fails if any
`tool.execute(...)` call appears in the codebase without a validation call
in the same function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.mcp.registry import tool_registry
from app.safety import guardrails
from app.safety.structured_validator import ValidationResult
from app.tools.base import MCPTool


@dataclass
class ToolResolution:
    tool_name: str
    tool: MCPTool | None
    check: ValidationResult

    @property
    def ok(self) -> bool:
        return self.tool is not None and bool(self.check)

    @property
    def reason(self) -> str:
        return self.check.reason

    @property
    def params(self) -> dict[str, Any]:
        """The checked, normalised params — execute with these, not the
        originals a caller passed in (the validator resolves paths, and the
        value that was checked must be the value used)."""
        return self.check.params or {}


def resolve_and_validate(tool_name: str, params: dict[str, Any]) -> ToolResolution:
    """Look up the tool and validate params against its schema + policy.

    Nothing here executes anything. It exists so that every caller performs
    the same two checks — the tool is registered, its params pass
    `guardrails.validate_params()` — through one function instead of each
    call site remembering to do both itself.
    """
    tool = tool_registry.get(tool_name)
    if tool is None:
        return ToolResolution(
            tool_name=tool_name,
            tool=None,
            check=ValidationResult(False, reason=f"tool '{tool_name}' is not loaded"),
        )

    check = guardrails.validate_params(tool_name, params)
    return ToolResolution(tool_name=tool_name, tool=tool, check=check)
