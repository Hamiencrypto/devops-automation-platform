-- Adds llm_usage, backing the per-user daily LLM token budget
-- (settings.LLM_DAILY_TOKEN_BUDGET, enforced by DailyTokenBudget in
-- app/services/llm_budget.py).
--
-- Not needed for a fresh deployment: Base.metadata.create_all() (called from
-- init_db() at startup) creates this table already, since LLMUsage is on the
-- ORM Base. This migration is only for a database that predates this model.
--
-- Apply with (from the repo root):
--   docker compose exec -T db psql -U devops -d devops_mcp -f - < database/migrations/0002_llm_usage_table.sql

CREATE TABLE IF NOT EXISTS llm_usage (
    id            SERIAL PRIMARY KEY,
    user_id       VARCHAR(128) NOT NULL,
    usage_date    DATE NOT NULL,
    model         VARCHAR(64) NOT NULL,
    total_tokens  INTEGER NOT NULL,
    created_at    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_llm_usage_user_id    ON llm_usage (user_id);
CREATE INDEX IF NOT EXISTS ix_llm_usage_usage_date ON llm_usage (usage_date);
