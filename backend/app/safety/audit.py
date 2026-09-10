"""Audit-trail helper — writes structured events to the audit_logs table."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger(__name__)


def audit_log(
    db: Session,
    *,
    event: str,
    severity: str = "info",
    task_id: int | None = None,
    user_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    intent_source: str | None = None,
    llm_tokens_used: int | None = None,
    llm_latency_ms: int | None = None,
    validation_result: str | None = None,
    rule_id: str | None = None,
    ruleset_version: str | None = None,
    ruleset_hash: str | None = None,
    commit: bool = True,
) -> AuditLog:
    """Persist an audit entry. Use for every privileged / destructive action."""
    entry = AuditLog(
        event=event,
        severity=severity,
        task_id=task_id,
        user_id=user_id,
        details=details or {},
        ip_address=ip_address,
        intent_source=intent_source,
        llm_tokens_used=llm_tokens_used,
        llm_latency_ms=llm_latency_ms,
        validation_result=validation_result,
        rule_id=rule_id,
        ruleset_version=ruleset_version,
        ruleset_hash=ruleset_hash,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    logger.info(
        "AUDIT %s [%s] user=%s task=%s %s",
        event, severity, user_id, task_id, details or {},
    )
    return entry
