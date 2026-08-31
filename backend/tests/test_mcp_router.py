"""Tests for the MCP router."""

import pytest

from app.mcp.registry import ToolRegistry
from app.mcp.router import MCPRouter, MCPRouterError
from app.schemas import IntentResult
from app.tools.base import MCPTool, ToolResult


class FakeTool(MCPTool):
    name = "fake_tool"
    description = "Fake tool for testing"
    category = "test"
    intents = ("test.ping", "test.echo")
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["action"],
    }

    def execute(self, params, dry_run=False):
        return ToolResult(success=True, summary="ok", data=params)


@pytest.fixture
def registry_with_fake():
    reg = ToolRegistry()
    reg.register(FakeTool())
    return reg


class TestRouter:
    def test_route_known_intent(self, registry_with_fake):
        router = MCPRouter(registry=registry_with_fake)
        intent = IntentResult(intent="test.ping", confidence=0.9, entities={})
        call = router.route(intent)
        assert call.tool_name == "fake_tool"
        assert call.params["action"] == "ping"

    def test_route_unknown_intent(self, registry_with_fake):
        router = MCPRouter(registry=registry_with_fake)
        intent = IntentResult(intent="unknown", confidence=0.0)
        with pytest.raises(MCPRouterError):
            router.route(intent)

    def test_route_unregistered_intent(self, registry_with_fake):
        router = MCPRouter(registry=registry_with_fake)
        intent = IntentResult(intent="nonexistent.thing", confidence=0.9)
        with pytest.raises(MCPRouterError):
            router.route(intent)

    def test_entity_passthrough(self, registry_with_fake):
        router = MCPRouter(registry=registry_with_fake)
        intent = IntentResult(
            intent="test.echo",
            confidence=0.9,
            entities={"message": "hello"},
        )
        call = router.route(intent)
        assert call.params["message"] == "hello"
        assert call.params["action"] == "echo"


class TestRegistry:
    def test_register_tool(self):
        reg = ToolRegistry()
        reg.register(FakeTool())
        assert reg.get("fake_tool") is not None
        assert "test.ping" in reg.list_intents()

    def test_duplicate_registration_raises(self):
        reg = ToolRegistry()
        reg.register(FakeTool())
        with pytest.raises(ValueError):
            reg.register(FakeTool())

    def test_schema_export(self):
        reg = ToolRegistry()
        reg.register(FakeTool())
        schemas = reg.to_schema()
        assert len(schemas) == 1
        assert schemas[0].name == "fake_tool"
