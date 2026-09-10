"""
Tests for the single sanctioned tool-lookup+validate chokepoint.

`resolve_and_validate` calls into the real `guardrails` singleton, which is
bound to the real global `tool_registry` (not whatever a test patches
`tool_execution.tool_registry` to) — so these tests fake `validate_params`
itself to isolate resolve_and_validate's own wiring (does it look the tool
up, does it call validate_params, does it surface a denial) from policy
correctness, which belongs to test_structured_validator.py.
"""

from app.mcp.registry import ToolRegistry
from app.safety.structured_validator import ValidationResult
from app.services import tool_execution
from app.tools.base import MCPTool, ToolResult


class FakeTool(MCPTool):
    name = "fake_tool"
    description = "test double"
    category = "test"
    intents = ("test.ping",)
    input_schema = {
        "type": "object",
        "properties": {"action": {"type": "string"}},
        "required": ["action"],
    }

    def execute(self, params, dry_run=False):
        return ToolResult(success=True, summary="ok", data=params)


def test_unregistered_tool_is_not_ok():
    resolution = tool_execution.resolve_and_validate("nonexistent_tool", {})
    assert resolution.tool is None
    assert not resolution.ok
    assert "not loaded" in resolution.reason


def test_registered_tool_with_allowed_params_is_ok(monkeypatch):
    reg = ToolRegistry()
    reg.register(FakeTool())
    monkeypatch.setattr(tool_execution, "tool_registry", reg)
    monkeypatch.setattr(
        tool_execution.guardrails,
        "validate_params",
        lambda tool_name, params: ValidationResult(True, params={**params, "normalised": True}),
    )

    resolution = tool_execution.resolve_and_validate("fake_tool", {"action": "list"})

    assert resolution.ok
    assert resolution.tool is not None
    assert resolution.params["normalised"] is True, "must surface the checked/normalised params, not the raw input"


def test_registered_tool_with_denied_params_is_not_ok(monkeypatch):
    reg = ToolRegistry()
    reg.register(FakeTool())
    monkeypatch.setattr(tool_execution, "tool_registry", reg)
    monkeypatch.setattr(
        tool_execution.guardrails,
        "validate_params",
        lambda tool_name, params: ValidationResult(False, reason="denied by policy"),
    )

    resolution = tool_execution.resolve_and_validate("fake_tool", {"action": "delete"})

    assert resolution.tool is not None, "the tool is still registered, just the params are bad"
    assert not resolution.ok
    assert resolution.reason == "denied by policy"
