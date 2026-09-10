-- Adds hybrid-intent observability columns to audit_logs.
--
-- Not needed for a fresh deployment: SQLAlchemy's Base.metadata.create_all()
-- (called from init_db() at startup) creates audit_logs with these columns
-- already, since they're on the AuditLog model. This migration is only for
-- a database that already has an audit_logs table from before this change —
-- create_all() does not ALTER existing tables.
--
-- Apply with (from the repo root):
--   docker compose exec -T db psql -U devops -d devops_mcp -f - < database/migrations/0001_audit_logs_llm_observability.sql

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS intent_source     VARCHAR(16),
    ADD COLUMN IF NOT EXISTS llm_tokens_used    INTEGER,
    ADD COLUMN IF NOT EXISTS llm_latency_ms     INTEGER,
    ADD COLUMN IF NOT EXISTS validation_result  VARCHAR(255);

CREATE INDEX IF NOT EXISTS ix_audit_logs_intent_source ON audit_logs (intent_source);
