"""
Regression test for the direct container-management endpoints.

These routes let the UI stop/remove a container by ID without going through
natural-language intent detection, and their own docstring used to claim
they "reuse the DockerTool so the same audit trail and safety checks apply."
They didn't: `stop_container_by_id` / `remove_container_by_id` built params
from the URL and called `tool.execute(params)` directly, with no call into
`guardrails.validate_params()` anywhere in between. That meant the
protected-container policy (mcp-backend/mcp-frontend/mcp-postgres must never
be stopped or removed) — enforced everywhere else in the app — was fully
bypassable through this one route. Fixed by routing every call through
`app.services.tool_execution.resolve_and_validate()`, the same chokepoint
`executor.py` uses for the natural-language path.

This test isolates the *wiring* (does the route call resolve_and_validate
and honour a denial before touching the tool) from the *policy* (covered in
test_structured_validator.py) by faking `resolve_and_validate`.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import containers
from app.services.tool_execution import ToolResolution
from app.safety.structured_validator import ValidationResult


class FakeDockerTool:
    def __init__(self):
        self.calls = []

    def execute(self, params, dry_run=False):
        self.calls.append(params)
        return SimpleNamespace(
            success=True, summary="ok", data={}, stdout="", stderr=""
        )


class FakeAuditLog:
    """Records calls instead of touching a real DB session — these tests
    pass db=None, matching the rest of this file's style of faking out
    everything below the route function itself."""

    def __init__(self):
        self.calls = []

    def __call__(self, db, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id=len(self.calls))


FAKE_REQUEST = SimpleNamespace(client=None)


def denied_resolution(tool, reason, *, rule_id=None, ruleset_version=None, ruleset_hash=None):
    return ToolResolution(
        tool_name="docker_manager",
        tool=tool,
        check=ValidationResult(
            False,
            reason=reason,
            rule_id=rule_id,
            ruleset_version=ruleset_version,
            ruleset_hash=ruleset_hash,
        ),
    )


def allowed_resolution(tool, params):
    return ToolResolution(
        tool_name="docker_manager", tool=tool, check=ValidationResult(True, params=params)
    )


def test_stop_endpoint_denies_before_touching_the_tool(monkeypatch):
    tool = FakeDockerTool()
    audit = FakeAuditLog()
    monkeypatch.setattr(
        containers,
        "resolve_and_validate",
        lambda name, params: denied_resolution(
            tool,
            "mcp-postgres is part of the platform itself",
            rule_id="docker.name.not_protected",
            ruleset_version="1.0.0",
            ruleset_hash="abc123",
        ),
    )
    monkeypatch.setattr(containers, "audit_log", audit)

    with pytest.raises(HTTPException) as exc_info:
        containers.stop_container_by_id(
            "mcp-postgres", FAKE_REQUEST, db=None, user=None
        )

    assert exc_info.value.status_code == 403
    assert tool.calls == [], "the tool must never run once resolve_and_validate denies the call"

    assert len(audit.calls) == 1, "a denial that reaches this boundary must be audited"
    call = audit.calls[0]
    assert call["event"] == "container.direct_action.blocked"
    assert call["rule_id"] == "docker.name.not_protected"
    assert call["ruleset_version"] == "1.0.0"
    assert call["ruleset_hash"] == "abc123"


def test_remove_endpoint_denies_before_touching_the_tool(monkeypatch):
    tool = FakeDockerTool()
    audit = FakeAuditLog()
    monkeypatch.setattr(
        containers,
        "resolve_and_validate",
        lambda name, params: denied_resolution(tool, "mcp-backend is part of the platform itself"),
    )
    monkeypatch.setattr(containers, "audit_log", audit)

    with pytest.raises(HTTPException) as exc_info:
        containers.remove_container_by_id(
            "mcp-backend", FAKE_REQUEST, db=None, user=None
        )

    assert exc_info.value.status_code == 403
    assert tool.calls == [], "the tool must never run once resolve_and_validate denies the call"
    assert len(audit.calls) == 1


def test_stop_endpoint_executes_with_the_checked_params(monkeypatch):
    """A validator can normalise params (e.g. resolved paths); the value that
    was checked must be the value executed, not the original request body."""
    tool = FakeDockerTool()
    normalised = {"action": "stop", "container": "web-1"}
    monkeypatch.setattr(
        containers, "resolve_and_validate", lambda name, params: allowed_resolution(tool, normalised)
    )
    monkeypatch.setattr(containers, "_persist", lambda *a, **k: SimpleNamespace(id=1))

    result = containers.stop_container_by_id(
        "web-1", FAKE_REQUEST, db=None, user=None
    )

    assert tool.calls == [normalised]
    assert result["success"] is True


def test_unregistered_tool_returns_503(monkeypatch):
    audit = FakeAuditLog()
    monkeypatch.setattr(
        containers,
        "resolve_and_validate",
        lambda name, params: ToolResolution(
            tool_name="docker_manager", tool=None, check=ValidationResult(False, reason="n/a")
        ),
    )
    monkeypatch.setattr(containers, "audit_log", audit)

    with pytest.raises(HTTPException) as exc_info:
        containers.stop_container_by_id("web-1", FAKE_REQUEST, db=None, user=None)

    assert exc_info.value.status_code == 503
    assert len(audit.calls) == 1
