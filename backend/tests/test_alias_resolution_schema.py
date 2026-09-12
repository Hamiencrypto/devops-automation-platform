"""
Regression test for a real bug found in production use: `deploy mongodb` /
`spin up a redis server` were denied with "unrecognised parameters for
docker_manager: ['original_image']".

app/intent/engine.py::_post_process() resolves a typo'd or aliased image
name ("redis" -> "redis:latest") and, when the resolved form differs from
what the user typed, adds `original_image` to the entities purely so
docker_tool.py can show a friendly "Interpreted 'redis' as 'redis:latest'"
message. But `DockerTool.input_schema` never declared that property, so
Layer 1 (JSON Schema) rejected the call before it ever reached the tool —
breaking exactly the "typo-tolerant image resolution" the UI advertises,
and only when the alias table actually did something (typing the canonical
name directly never sets `original_image`, so the bug was invisible to
anyone testing with exact image names).

These tests exercise the REAL tool registry and REAL tool classes — not
FakeTool doubles with a hand-rolled schema — because the bug was in the
gap between what the intent engine actually produces and what the shipped
schema actually declares, which a fixture schema can't catch.
"""

from app.mcp.registry import tool_registry
from app.safety.structured_validator import SafetyPolicy, StructuredOutputValidator
from app.tools import load_all_tools

load_all_tools()


def test_docker_manager_schema_declares_original_image():
    tool = tool_registry.get("docker_manager")
    assert tool is not None
    assert "original_image" in tool.input_schema["properties"]


def test_kubernetes_manager_schema_declares_original_image():
    tool = tool_registry.get("kubernetes_manager")
    assert tool is not None
    assert "original_image" in tool.input_schema["properties"]


def test_deploy_with_alias_resolved_image_is_not_rejected_by_schema():
    """The exact shape app/intent/engine.py::_post_process() actually
    produces for e.g. 'spin up a redis server' -> image resolved to
    redis:latest, original_image kept as 'redis'."""
    validator = StructuredOutputValidator(tool_registry, SafetyPolicy())

    result = validator.validate_tool_call(
        "docker_manager",
        {"action": "deploy", "image": "redis:latest", "original_image": "redis"},
    )

    assert result, result.reason
    assert "unrecognised parameters" not in result.reason


def test_k8s_deploy_with_alias_resolved_image_is_not_rejected_by_schema():
    validator = StructuredOutputValidator(tool_registry, SafetyPolicy())

    result = validator.validate_tool_call(
        "kubernetes_manager",
        {"action": "deploy", "image": "redis:latest", "original_image": "redis"},
    )

    assert result, result.reason
    assert "unrecognised parameters" not in result.reason
