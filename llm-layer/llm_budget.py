"""
Per-user daily LLM token budget, backed by Postgres.

Why a budget at all: the LLM path is the only part of this system with a
marginal cost per request. Without a cap, one runaway client loop is an
unbounded bill. The cap is per user per UTC day and fails closed — if we
cannot read the budget we assume it is spent, because a temporarily
degraded system is cheaper than an unmetered one.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import LLMUsage

log = logging.getLogger(__name__)


class DailyTokenBudget:
    def __init__(self, session_factory, daily_limit: int):
        self._session_factory = session_factory
        self.daily_limit = daily_limit

    def remaining(self, user_id: str) -> int:
        if self.daily_limit <= 0:
            return 1_000_000_000  # 0 or negative means "no limit configured"
        try:
            with self._session_factory() as session:  # type: Session
                used = (
                    session.query(func.coalesce(func.sum(LLMUsage.total_tokens), 0))
                    .filter(
                        LLMUsage.user_id == user_id,
                        LLMUsage.usage_date == date.today(),
                    )
                    .scalar()
                    or 0
                )
            return max(0, self.daily_limit - int(used))
        except Exception as exc:
            log.error("could not read LLM budget for %s, failing closed: %s", user_id, exc)
            return 0

    def record(self, user_id: str, tokens: int, model: str) -> None:
        if tokens <= 0:
            return
        try:
            with self._session_factory() as session:  # type: Session
                session.add(
                    LLMUsage(
                        user_id=user_id,
                        usage_date=date.today(),
                        model=model,
                        total_tokens=tokens,
                    )
                )
                session.commit()
        except Exception as exc:
            # Never let accounting break a request that already succeeded.
            log.error("failed to record %d LLM tokens for %s: %s", tokens, user_id, exc)

    def used_today(self, user_id: str) -> int:
        return max(0, self.daily_limit - self.remaining(user_id))
