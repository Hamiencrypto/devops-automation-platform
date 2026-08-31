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
