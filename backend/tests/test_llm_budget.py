"""
Tests for the per-user daily LLM token budget.

This was previously dead code: `llm_budget.py` imported a model (`LLMUsage`)
that didn't exist in `app.models`, so importing the module — let alone using
it — would raise `ImportError`. It was never passed to `HybridIntentEngine`,
so in practice every request ran against `UnlimitedBudget` and the configured
`LLM_DAILY_TOKEN_BUDGET` cap did nothing. These tests cover the budget once
it's an importable, working, DB-backed component.
"""

from datetime import date, timedelta

from app.database import SessionLocal, init_db
from app.models import LLMUsage
from app.services.llm_budget import DailyTokenBudget


def make_budget(limit: int = 1000) -> DailyTokenBudget:
    init_db()
    return DailyTokenBudget(SessionLocal, limit)


def test_full_budget_available_with_no_usage():
    budget = make_budget(1000)
    assert budget.remaining("user:1") == 1000


def test_record_decrements_remaining():
    budget = make_budget(1000)
    budget.record("user:2", 400, "claude-haiku-4-5")
    assert budget.remaining("user:2") == 600


def test_budget_floors_at_zero_not_negative():
    budget = make_budget(100)
    budget.record("user:3", 500, "claude-haiku-4-5")
    assert budget.remaining("user:3") == 0


def test_usage_is_per_user():
    budget = make_budget(1000)
    budget.record("user:4", 900, "claude-haiku-4-5")
    assert budget.remaining("user:4") == 100
    assert budget.remaining("user:5") == 1000, "another user's spend must not leak across keys"


def test_usage_only_counts_today():
    budget = make_budget(1000)
    session = SessionLocal()
    try:
        session.add(
            LLMUsage(
                user_id="user:6",
                usage_date=date.today() - timedelta(days=1),
                model="claude-haiku-4-5",
                total_tokens=900,
            )
        )
        session.commit()
    finally:
        session.close()

    assert budget.remaining("user:6") == 1000, "yesterday's usage must not count against today's cap"


def test_zero_or_negative_limit_means_unlimited():
    budget = make_budget(0)
    assert budget.remaining("user:7") == 1_000_000_000

    unlimited = make_budget(-1)
    assert unlimited.remaining("user:7") == 1_000_000_000


def test_record_is_a_noop_for_non_positive_tokens():
    budget = make_budget(1000)
    budget.record("user:8", 0, "claude-haiku-4-5")
    assert budget.remaining("user:8") == 1000
