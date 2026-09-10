"""
Regression test for the direct container-management endpoints.

These routes let the UI stop/remove a container by ID without going through
natural-language intent detection, and their own docstring claims they
"reuse the DockerTool so the same audit trail and safety checks apply." They
did not: `stop_container_by_id` / `remove_container_by_id` built params from
the URL and called `tool.execute(params)` directly, with no call into
`guardrails.validate_params()` anywhere in between. That meant the
protected-container policy (mcp-backend/mcp-frontend/mcp-postgres must never
be stopped or removed) — enforced everywhere else in the app — was fully
bypassable through this one route. Fixed by routing params through
`guardrails.validate_params("docker_manager", params)` before execution,
mirroring what `executor.py` already does for the natural-language path.

This test isolates the *wiring* (does the route call validate_params and
honour a denial before touching the tool) from the *policy* (already covered
in test_structured_validator.py) by faking guardrails.validate_params.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import containers
from app.safety.structured_validator import ValidationResult


class FakeDockerTool:
    def __init__(self):
        self.calls = []

    def execute(self, params, dry_run=False):
        self.calls.append(params)
        return SimpleNamespace(
            success=True, summary="ok", data={}, stdout="", stderr=""
        )


class FakeRegistry:
    def __init__(self, tool):
        self._tool = tool

    def get(self, name):
        return self._tool if name == "docker_manager" else None


class FakeGuardrails:
    """Stands in for the real `guardrails` singleton so this test exercises
    the route's wiring, not the policy — the policy itself (protected
    containers, etc.) is covered in test_structured_validator.py."""

    def __init__(self, result: ValidationResult):
        self.result = result
        self.calls = []

    def validate_params(self, tool_name, params):
        self.calls.append((tool_name, params))
        return self.result


FAKE_REQUEST = SimpleNamespace(client=None)


def test_stop_endpoint_denies_before_touching_the_tool(monkeypatch):
    tool = FakeDockerTool()
    monkeypatch.setattr(containers, "tool_registry", FakeRegistry(tool))
    fake_guards = FakeGuardrails(
        ValidationResult(valid=False, reason="mcp-postgres is part of the platform itself")
    )
    monkeypatch.setattr(containers, "guardrails", fake_guards)

    with pytest.raises(HTTPException) as exc_info:
        containers.stop_container_by_id(
            "mcp-postgres", FAKE_REQUEST, db=None, user=None
        )

    assert exc_info.value.status_code == 403
    assert fake_guards.calls == [("docker_manager", {"action": "stop", "container": "mcp-postgres"})]
    assert tool.calls == [], "the tool must never run once validate_params denies the call"


def test_remove_endpoint_denies_before_touching_the_tool(monkeypatch):
    tool = FakeDockerTool()
    monkeypatch.setattr(containers, "tool_registry", FakeRegistry(tool))
    fake_guards = FakeGuardrails(
        ValidationResult(valid=False, reason="mcp-backend is part of the platform itself")
    )
    monkeypatch.setattr(containers, "guardrails", fake_guards)

    with pytest.raises(HTTPException) as exc_info:
        containers.remove_container_by_id(
            "mcp-backend", FAKE_REQUEST, db=None, user=None
        )

    assert exc_info.value.status_code == 403
    assert tool.calls == [], "the tool must never run once validate_params denies the call"


def test_stop_endpoint_executes_with_the_checked_params(monkeypatch):
    """A validator can normalise params (e.g. resolved paths); the value that
    was checked must be the value executed, not the original request body."""
    tool = FakeDockerTool()
    monkeypatch.setattr(containers, "tool_registry", FakeRegistry(tool))
    normalised = {"action": "stop", "container": "web-1"}
    fake_guards = FakeGuardrails(ValidationResult(valid=True, params=normalised))
    monkeypatch.setattr(containers, "guardrails", fake_guards)
    monkeypatch.setattr(containers, "_persist", lambda *a, **k: SimpleNamespace(id=1))

    result = containers.stop_container_by_id(
        "web-1", FAKE_REQUEST, db=None, user=None
    )

    assert tool.calls == [normalised]
    assert result["success"] is True
