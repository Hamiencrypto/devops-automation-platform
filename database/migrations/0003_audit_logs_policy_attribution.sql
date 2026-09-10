-- Adds declarative-policy attribution columns to audit_logs.
--
-- Not needed for a fresh deployment: SQLAlchemy's Base.metadata.create_all()
-- (called from init_db() at startup) creates audit_logs with these columns
-- already, since they're on the AuditLog model. This migration is only for
-- a database that already has an audit_logs table from before this change —
-- create_all() does not ALTER existing tables.
--
-- Apply with (from the repo root):
--   docker compose exec -T db psql -U devops -d devops_mcp -f - < database/migrations/0003_audit_logs_policy_attribution.sql
--
-- rule_id is set only for a Layer-2 (declarative ruleset) denial — never for
-- a Layer-1 schema failure or an unregistered-tool denial, and never for an
-- allow (no single rule "approves" a call, all of them simply passed).
-- ruleset_version and ruleset_hash are set on both an allow and a deny, so
-- either is attributable to exactly which ruleset evaluated it. Two
-- different questions, two columns: ruleset_version is what a human reads
-- ("denied under ruleset v1.0.0"); ruleset_hash is what actually proves
-- which bytes ran, independent of anyone remembering to bump the version
-- string. See app/safety/policy/rules.yaml's header comment for the full
-- scope note on what "declarative" does and doesn't cover.

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS rule_id          VARCHAR(128),
    ADD COLUMN IF NOT EXISTS ruleset_version  VARCHAR(32),
    ADD COLUMN IF NOT EXISTS ruleset_hash     VARCHAR(64);

CREATE INDEX IF NOT EXISTS ix_audit_logs_rule_id ON audit_logs (rule_id);
