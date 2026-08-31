# Integration patches — LLM intent layer

Four existing files change. Each patch is additive; nothing is deleted, so
`ENABLE_LLM=false` restores the current behaviour exactly.

---

## 1. `backend/app/config.py`

Add to the `Settings` class:

```python
    # --- LLM intent layer -------------------------------------------------
    ENABLE_LLM: bool = False          # off by default; opt in per environment
    LLM_PROVIDER: str = "anthropic"   # anthropic | openai
    LLM_MODEL: str = "claude-haiku-4-5"
    LLM_API_KEY: str = ""
    LLM_THRESHOLD: float = 0.65       # regex confidence below this -> ask the model
    LLM_MAX_TOKENS: int = 512
    LLM_TIMEOUT_SECONDS: float = 20.0
    LLM_CACHE_TTL: int = 86_400       # 24h
    LLM_CACHE_MAX_ENTRIES: int = 2_000
    LLM_MAX_COMMAND_CHARS: int = 1_000
    LLM_DAILY_TOKEN_BUDGET: int = 50_000   # per user, per UTC day; 0 = unlimited

    @field_validator("LLM_THRESHOLD")
    @classmethod
    def _valid_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("LLM_THRESHOLD must be between 0 and 1")
        return v
```

Import `field_validator` from `pydantic` if it is not already imported.

A note on the threshold. 0.65 is a starting point, not a discovered value.
Once you have a few hundred real commands in `tasks`, plot regex confidence
against whether the resulting execution succeeded, and set the threshold at
the point where regex accuracy starts falling off. Being able to say "we
tuned this from our own logs, here is the curve" is worth more in a viva
than any individual number.

---

## 2. `backend/app/models.py`

```python
from sqlalchemy import Column, Date, DateTime, Integer, String, Index, func

class LLMUsage(Base):
    """One row per LLM call. Powers budgets and the cost panel."""
    __tablename__ = "llm_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    usage_date = Column(Date, nullable=False, index=True)
    model = Column(String(100), nullable=False)
    total_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_llm_usage_user_date", "user_id", "usage_date"),
    )
```

And add three columns to the existing `Task` model so every execution
records how its intent was decided:

```python
    intent_source = Column(String(20), nullable=True)   # regex | llm | cache | none
    intent_reason = Column(String(500), nullable=True)
    llm_tokens = Column(Integer, nullable=False, default=0)
```

Migration (Alembic autogenerate will produce equivalent SQL):

```sql
CREATE TABLE llm_usage (
    id           SERIAL PRIMARY KEY,
    user_id      VARCHAR(255) NOT NULL,
    usage_date   DATE         NOT NULL,
    model        VARCHAR(100) NOT NULL,
    total_tokens INTEGER      NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX ix_llm_usage_user_date ON llm_usage (user_id, usage_date);

ALTER TABLE tasks ADD COLUMN intent_source VARCHAR(20);
ALTER TABLE tasks ADD COLUMN intent_reason VARCHAR(500);
ALTER TABLE tasks ADD COLUMN llm_tokens INTEGER NOT NULL DEFAULT 0;
```

---

## 3. `backend/app/services/executor.py`

Build the engine once at startup, not per request — constructing a provider
per call would open a new HTTP client every time and throw away the cache.

```python
# --- module level, built once -------------------------------------------
from functools import lru_cache

from app.config import settings
from app.database import SessionLocal
from app.intent.engine import IntentEngine
from app.intent.llm_engine import HybridIntentEngine, TTLCache, UnlimitedBudget
from app.intent.providers import build_provider
from app.mcp.registry import tool_registry
from app.services.llm_budget import DailyTokenBudget


@lru_cache(maxsize=1)
def get_intent_engine() -> HybridIntentEngine:
    budget = (
        DailyTokenBudget(SessionLocal, settings.LLM_DAILY_TOKEN_BUDGET)
        if settings.LLM_DAILY_TOKEN_BUDGET > 0
        else UnlimitedBudget()
    )
    return HybridIntentEngine(
        regex_engine=IntentEngine(),
        registry=tool_registry,
        provider=build_provider(settings),
        threshold=settings.LLM_THRESHOLD,
        max_tokens=settings.LLM_MAX_TOKENS,
        max_command_chars=settings.LLM_MAX_COMMAND_CHARS,
        cache=TTLCache(settings.LLM_CACHE_TTL, settings.LLM_CACHE_MAX_ENTRIES),
        budget=budget,
    )
```

Then in `execute_command()`, replace the intent detection block:

```python
    # was: intent, confidence, entities = intent_engine.detect(command)
    intent = get_intent_engine().detect(
        command,
        user_id=str(user.id) if user else "anonymous",
        history=recent_turns,          # list[{"role": ..., "content": ...}] or []
    )

    task.intent = intent.name
    task.confidence = intent.confidence
    task.intent_source = intent.source
    task.intent_reason = intent.reason
    task.llm_tokens = intent.tokens_used

    if not intent.resolved:
        audit.write(
            action="intent.unresolved",
            severity="warning",
            details={"command": command, "reason": intent.reason,
                     "source": intent.source},
        )
        return ExecuteResponse(
            task_id=task.id, success=False,
            message=intent.reason or "Could not determine what to run.",
            intent=None,
        )

    # Everything below is UNCHANGED. Guardrails still run, the router still
    # resolves the tool, destructive confirmation is still required. The LLM
    # widened what we can understand; it did not widen what we can do.
    warnings = guardrails.check(command, intent.name, intent.confidence)
    ...
```

The ordering matters and is the thing to say out loud in a viva: intent
resolution happens *before* guardrails, and guardrails are unaware of
whether a regex or a model produced the intent. There is no code path where
an LLM-sourced intent skips a check that a regex-sourced one would face.

Audit the source too:

```python
    audit.write(
        action="intent.resolved",
        severity="info",
        details={
            "intent": intent.name,
            "source": intent.source,          # regex | llm | cache
            "confidence": intent.confidence,
            "tokens": intent.tokens_used,
            "latency_ms": intent.latency_ms,
        },
    )
```

---

## 4. `.env.example`

```bash
# --- LLM intent layer ---------------------------------------------------
# Off by default. The platform runs fine on regex alone; turning this on
# adds natural-language understanding and a per-request API cost.
ENABLE_LLM=false
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5

# Never commit a real key. In production, inject via your secret manager
# rather than a .env file on disk.
LLM_API_KEY=

LLM_THRESHOLD=0.65
LLM_MAX_TOKENS=512
LLM_TIMEOUT_SECONDS=20
LLM_CACHE_TTL=86400
LLM_MAX_COMMAND_CHARS=1000
LLM_DAILY_TOKEN_BUDGET=50000
```

`docker-compose.yml`, under the backend service:

```yaml
    environment:
      - ENABLE_LLM=${ENABLE_LLM:-false}
      - LLM_PROVIDER=${LLM_PROVIDER:-anthropic}
      - LLM_MODEL=${LLM_MODEL:-claude-haiku-4-5}
      - LLM_API_KEY=${LLM_API_KEY:-}
      - LLM_THRESHOLD=${LLM_THRESHOLD:-0.65}
      - LLM_DAILY_TOKEN_BUDGET=${LLM_DAILY_TOKEN_BUDGET:-50000}
```

Add to `requirements.txt`:

```
anthropic>=0.40.0
jsonschema>=4.21.0
```

---

## Testing without spending money

You asked this in your doc. Three layers, and only the third costs anything:

1. **Unit tests** use `FakeProvider` from `tests/test_llm_engine.py`. No
   network, no key, runs in CI. This covers the routing logic, the cache, the
   budget, and every rejection path — which is most of what can actually break.
2. **Recorded fixtures.** Capture ~20 real provider responses once, store the
   JSON under `tests/fixtures/llm/`, and replay them. One-time cost of a few
   cents, and you get realistic payloads forever.
3. **Live smoke test** marked `@pytest.mark.live`, excluded from the default
   run via `addopts = -m "not live"` in `pytest.ini`. Run it before a demo.

With `LLM_MAX_TOKENS=512` and Haiku-class pricing, a full manual demo session
is well under a cent. The budget cap exists for runaway loops, not for demos.
