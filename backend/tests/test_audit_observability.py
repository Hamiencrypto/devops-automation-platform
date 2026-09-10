"""
Tests that the LLM-intent observability fields actually reach the DB.

The spec requires `intent_source`, `llm_tokens_used`, `llm_latency_ms` and
`validation_result` to be persisted per request in `audit_logs` — this checks
the plumbing from `audit_log()` down to the `AuditLog` row, independent of
the full executor pipeline (which has no DB-backed test harness to hang off
of yet).
"""

from app.database import SessionLocal, init_db
from app.models import AuditLog
from app.safety.audit import audit_log


def test_audit_log_persists_llm_observability_fields():
    init_db()
    db = SessionLocal()
    try:
        entry = audit_log(
            db,
            event="command.executed",
            severity="info",
            details={"command": "list containers"},
            intent_source="llm",
            llm_tokens_used=142,
            llm_latency_ms=873,
            validation_result="valid",
        )

        stored = db.query(AuditLog).filter_by(id=entry.id).one()
        assert stored.intent_source == "llm"
        assert stored.llm_tokens_used == 142
        assert stored.llm_latency_ms == 873
        assert stored.validation_result == "valid"
    finally:
        db.close()


def test_audit_log_observability_fields_default_to_none():
    init_db()
    db = SessionLocal()
    try:
        entry = audit_log(db, event="command.blocked", severity="warn")

        stored = db.query(AuditLog).filter_by(id=entry.id).one()
        assert stored.intent_source is None
        assert stored.llm_tokens_used is None
        assert stored.llm_latency_ms is None
        assert stored.validation_result is None
    finally:
        db.close()
