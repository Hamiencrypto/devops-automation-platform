"""
End-to-end: a real policy denial, through the real validator, into a real
audit_logs row — proving `rule_id` / `ruleset_version` / `ruleset_hash`
actually reach the database, not just that the engine computes them.
"""

from app.database import SessionLocal, init_db
from app.models import AuditLog
from app.safety.audit import audit_log
from app.safety.structured_validator import (
    RULESET,
    SafetyPolicy,
    StructuredOutputValidator,
)


class FakeTool:
    def __init__(self, name, schema):
        self.name = name
        self.description = f"fake {name}"
        self.intents = (f"{name}.act",)
        self.input_schema = schema


class FakeRegistry:
    def __init__(self, tools):
        self._tools = {t.name: t for t in tools}

    def get(self, name):
        return self._tools.get(name)


DOCKER_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["action"],
}


def make_validator() -> StructuredOutputValidator:
    registry = FakeRegistry([FakeTool("docker_tool", DOCKER_SCHEMA)])
    return StructuredOutputValidator(registry, SafetyPolicy())


def test_denial_is_attributed_to_the_rule_and_ruleset_that_fired():
    validator = make_validator()

    result = validator.validate_tool_call(
        "docker_tool", {"action": "stop", "name": "mcp-postgres"}
    )

    assert not result
    assert result.rule_id == "docker.name.not_protected"
    assert result.ruleset_version == RULESET.version
    assert result.ruleset_hash == RULESET.content_hash


def test_attribution_reaches_the_audit_row():
    validator = make_validator()
    result = validator.validate_tool_call(
        "docker_tool", {"action": "stop", "name": "mcp-backend"}
    )
    assert not result

    init_db()
    db = SessionLocal()
    try:
        entry = audit_log(
            db,
            event="command.blocked",
            severity="warn",
            details={"reason": result.reason},
            validation_result=f"denied: {result.reason}",
            rule_id=result.rule_id,
            ruleset_version=result.ruleset_version,
            ruleset_hash=result.ruleset_hash,
        )

        stored = db.query(AuditLog).filter_by(id=entry.id).one()
        assert stored.rule_id == "docker.name.not_protected"
        assert stored.ruleset_version == RULESET.version
        assert stored.ruleset_hash == RULESET.content_hash
    finally:
        db.close()


def test_allow_is_attributed_to_the_ruleset_but_not_a_rule():
    """No single rule 'approves' a call — every rule simply passed — so
    rule_id stays null on an allow, while the ruleset version/hash that
    evaluated it are still recorded."""
    validator = make_validator()

    result = validator.validate_tool_call("docker_tool", {"action": "list"})

    assert result
    assert result.rule_id is None
    assert result.ruleset_version == RULESET.version
    assert result.ruleset_hash == RULESET.content_hash


def test_schema_denial_carries_no_rule_attribution():
    """Layer 1 (JSON Schema) is out of scope for this refactor — a schema
    failure isn't a ruleset evaluation, so it must not appear to be one."""
    validator = make_validator()

    result = validator.validate_tool_call("docker_tool", {})  # missing required 'action'

    assert not result
    assert result.rule_id is None
    assert result.ruleset_version is None
    assert result.ruleset_hash is None
