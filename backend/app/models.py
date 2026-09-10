"""SQLAlchemy ORM models for users, tasks, results, and audit logs."""

from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"  # Blocked by safety guardrails
    DRY_RUN = "dry_run"


class UserRole(str, PyEnum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


# ---------------------------------------------------------------------
# User
# ---------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.DEVELOPER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------
# Task (one per user command)
# ---------------------------------------------------------------------
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    # Input
    command: Mapped[str] = mapped_column(Text, nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Intent detection outputs
    detected_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(nullable=True)
    entities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # MCP routing outputs
    selected_tool: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status + metrics
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="tasks")
    result: Mapped["Result | None"] = relationship(
        "Result", back_populates="task", uselist=False, cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="task", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------
# Result (raw tool output)
# ---------------------------------------------------------------------
class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"), unique=True, nullable=False, index=True
    )

    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    task: Mapped["Task"] = relationship("Task", back_populates="result")


# ---------------------------------------------------------------------
# AuditLog (every privileged / destructive action)
# ---------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Hybrid intent layer observability — how this request's intent was
    # decided and what the structured-validation boundary did with it.
    intent_source: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    llm_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_result: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Policy attribution (declarative Layer-2 ruleset — app/safety/policy/).
    # Set only for a ruleset denial: no single rule "approves" an allow, so
    # rule_id stays null there, but ruleset_version/hash are still recorded
    # so an allow is attributable to exactly which ruleset evaluated it.
    # Two separate version fields, answering two different questions: the
    # human-controlled version string is what a person reads ("denied under
    # ruleset v1.0.0"); the content hash is what actually proves which bytes
    # ran, immune to someone forgetting to bump the version string.
    rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ruleset_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ruleset_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    task: Mapped["Task | None"] = relationship("Task", back_populates="audit_logs")


# ---------------------------------------------------------------------
# LLMUsage (per-user daily token consumption, backs the LLM budget cap)
# ---------------------------------------------------------------------
class LLMUsage(Base):
    """
    One row per (user_id, model, request). Summed by usage_date in
    DailyTokenBudget to enforce settings.LLM_DAILY_TOKEN_BUDGET. `user_id` is
    a free-form string key rather than a FK to `users.id` because the same
    accounting applies when auth is disabled (e.g. "ip:203.0.113.4") — not
    every caller is a registered user.
    """

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
