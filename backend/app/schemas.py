"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import TaskStatus, UserRole


# =====================================================================
# Auth schemas
# =====================================================================
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.DEVELOPER


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# =====================================================================
# Execution schemas
# =====================================================================
class ExecuteRequest(BaseModel):
    """Natural language command to execute."""

    command: str = Field(..., min_length=1, max_length=2000, description="Natural language input")
    dry_run: bool = Field(False, description="Plan only, don't actually execute")
    confirm_destructive: bool = Field(
        False, description="User has acknowledged destructive operation"
    )
    metadata: dict[str, Any] | None = None


class IntentResult(BaseModel):
    """Output of the intent engine."""

    intent: str
    confidence: float
    entities: dict[str, Any] = Field(default_factory=dict)
    matched_pattern: str | None = None
    # How this intent was decided — surfaced in the UI so an operator can see
    # when a result came from the model rather than the pattern engine.
    source: str = "regex"  # regex | llm | cache | none
    tokens_used: int = 0
    latency_ms: int = 0


class MCPToolCall(BaseModel):
    """Describes a resolved MCP tool invocation."""

    tool_name: str
    params: dict[str, Any] = Field(default_factory=dict)


class ExecuteResponse(BaseModel):
    """Full response to /execute."""

    task_id: int
    status: TaskStatus
    intent: IntentResult | None = None
    tool_call: MCPToolCall | None = None
    result: dict[str, Any] | None = None
    summary: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


# =====================================================================
# Task history schemas
# =====================================================================
class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    command: str
    status: TaskStatus
    detected_intent: str | None
    intent_confidence: float | None
    selected_tool: str | None
    duration_ms: int | None
    dry_run: bool
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class TaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TaskOut]


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    success: bool
    summary: str | None
    data: dict[str, Any] | None
    stdout: str | None
    stderr: str | None


# =====================================================================
# MCP tool catalog schemas
# =====================================================================
class ToolSchema(BaseModel):
    """MCP-compliant tool description."""

    name: str
    description: str
    input_schema: dict[str, Any]
    intents: list[str] = Field(default_factory=list)
    destructive: bool = False
    category: str = "general"


class ToolCatalogResponse(BaseModel):
    total: int
    tools: list[ToolSchema]


# =====================================================================
# Health
# =====================================================================
class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    checks: dict[str, str]
