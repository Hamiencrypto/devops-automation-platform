"""End-to-end executor: command → intent → MCP → tool → DB persistence.

This is the single entry point the API layer calls. Keeping the pipeline in
one place makes it trivial to unit-test and to instrument.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from functools import lru_cache

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.intent.engine import intent_engine
from app.mcp.registry import tool_registry
from app.mcp.router import MCPRouterError, mcp_router
from app.models import Result, Task, TaskStatus, User
from app.safety import SafetyError, audit_log, guardrails, rate_limiter
from app.config import settings
from app.intent.llm_engine import HybridIntentEngine, TTLCache
from app.intent.providers import build_provider
from app.services.llm_budget import DailyTokenBudget
from app.services.tool_execution import resolve_and_validate
from app.schemas import ExecuteResponse, IntentResult

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_intent_engine() -> HybridIntentEngine:
    """
    Built once per process: constructing a provider per request would open a
    new HTTP client each time and throw away the cache.

    With ENABLE_LLM=false, build_provider returns None and the engine is a
    thin pass-through to the existing regex engine — same behaviour as before.
    """
    return HybridIntentEngine(
        regex_engine=intent_engine,
        registry=tool_registry,
        provider=build_provider(settings),
        threshold=settings.LLM_THRESHOLD,
        max_tokens=settings.LLM_MAX_TOKENS,
        max_command_chars=settings.LLM_MAX_COMMAND_CHARS,
        cache=TTLCache(settings.LLM_CACHE_TTL, settings.LLM_CACHE_MAX_ENTRIES),
        budget=DailyTokenBudget(SessionLocal, settings.LLM_DAILY_TOKEN_BUDGET),
    )


def execute_command(
    db: Session,
    *,
    command: str,
    dry_run: bool = False,
    confirm_destructive: bool = False,
    user: User | None = None,
    ip_address: str | None = None,
) -> ExecuteResponse:
    """Full pipeline: intent detection → MCP routing → tool execution → persist."""

    # ------------------------------------------------------------------
    # 0. Rate limiting
    # ------------------------------------------------------------------
    rl_key = f"user:{user.id}" if user else f"ip:{ip_address or 'anon'}"
    allowed, remaining = rate_limiter.allow(rl_key)
    if not allowed:
        raise SafetyError(
            f"Rate limit exceeded ({rate_limiter.limit}/min). Slow down for a moment."
        )

    # ------------------------------------------------------------------
    # 1. Create task row
    # ------------------------------------------------------------------
    task = Task(
        command=command,
        dry_run=dry_run,
        status=TaskStatus.PENDING,
        user_id=user.id if user else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    started = time.time()
    warnings: list[str] = []
    result_payload: dict[str, Any] | None = None
    intent = None
    tool_call = None
    intent_source: str | None = None
    llm_tokens_used: int | None = None
    llm_latency_ms: int | None = None

    try:
        # --------------------------------------------------------------
        # 2. Intent detection
        # --------------------------------------------------------------
        # Regex first, model only on low confidence. The hybrid engine
        # returns its own Intent type; convert to IntentResult so everything
        # downstream (guardrails, router, tools) is unchanged.
        _hybrid = get_intent_engine().detect(command, user_id=rl_key)
        intent = IntentResult(
            intent=_hybrid.name,
            confidence=_hybrid.confidence,
            entities=_hybrid.entities,
            matched_pattern=_hybrid.reason or None,
            source=_hybrid.source,
            tokens_used=_hybrid.tokens_used,
            latency_ms=_hybrid.latency_ms,
        )
        logger.info(
            "intent %s via %s (confidence=%.2f, %dms, %d tokens)",
            _hybrid.name, _hybrid.source, _hybrid.confidence,
            _hybrid.latency_ms, _hybrid.tokens_used,
        )
        intent_source = _hybrid.source
        llm_tokens_used = _hybrid.tokens_used
        llm_latency_ms = _hybrid.latency_ms
        task.detected_intent = intent.intent
        task.intent_confidence = intent.confidence
        task.entities = intent.entities

        # --------------------------------------------------------------
        # 3. Safety check
        # --------------------------------------------------------------
        # Resolve the tool up front so the safety layer validates the actual
        # parameters that will be passed to it. Same lookup the MCP router
        # does below, so routing behaviour is unchanged.
        check = guardrails.check(
            command, intent, confirm_destructive=confirm_destructive
        )
        if check.warnings:
            warnings.extend(check.warnings)

        if not check.allowed:
            task.status = TaskStatus.BLOCKED
            task.error_message = check.reason
            task.completed_at = datetime.utcnow()
            task.duration_ms = int((time.time() - started) * 1000)
            db.commit()
            audit_log(
                db,
                event="command.blocked",
                severity="warn",
                task_id=task.id,
                user_id=user.id if user else None,
                details={
                    "command": command,
                    "reason": check.reason,
                    "require_confirmation": check.require_confirmation,
                },
                ip_address=ip_address,
                intent_source=intent_source,
                llm_tokens_used=llm_tokens_used,
                llm_latency_ms=llm_latency_ms,
                validation_result=f"denied: {check.reason}",
            )
            return ExecuteResponse(
                task_id=task.id,
                status=TaskStatus.BLOCKED,
                intent=intent,
                error=check.reason,
                warnings=warnings,
                duration_ms=task.duration_ms,
            )

        # --------------------------------------------------------------
        # 4. MCP routing
        # --------------------------------------------------------------
        tool_call = mcp_router.route(intent)
        task.selected_tool = tool_call.tool_name
        task.tool_params = tool_call.params

        # --------------------------------------------------------------
        # 5. Resolve + validate (the authoritative allowlist)
        # --------------------------------------------------------------
        # `resolve_and_validate` is the one sanctioned path from a tool name
        # to a tool that's safe to execute: it checks the tool is registered
        # and that its params satisfy the tool's published JSON Schema and
        # operational policy (permitted filesystem roots, bindable ports,
        # protected containers and namespaces).
        #
        # It runs here, on the final routed params, and it runs for every
        # intent source. A regex pattern that emits {"path": "/etc/passwd"}
        # is exactly as dangerous as a model that does, so neither gets its
        # own code path.
        resolution = resolve_and_validate(tool_call.tool_name, tool_call.params)
        if resolution.tool is None:
            raise MCPRouterError(f"Tool '{tool_call.tool_name}' is not loaded")
        tool = resolution.tool

        if not resolution.ok:
            task.status = TaskStatus.BLOCKED
            task.error_message = resolution.reason
            task.completed_at = datetime.utcnow()
            task.duration_ms = int((time.time() - started) * 1000)
            db.commit()
            audit_log(
                db,
                event="command.blocked",
                severity="warn",
                task_id=task.id,
                user_id=user.id if user else None,
                details={
                    "command": command,
                    "tool": tool.name,
                    "reason": resolution.reason,
                },
                ip_address=ip_address,
                intent_source=intent_source,
                llm_tokens_used=llm_tokens_used,
                llm_latency_ms=llm_latency_ms,
                validation_result=f"denied: {resolution.reason}",
            )
            return ExecuteResponse(
                task_id=task.id,
                status=TaskStatus.BLOCKED,
                intent=intent,
                error=resolution.reason,
                warnings=warnings,
                duration_ms=task.duration_ms,
            )

        # Execute the params that were checked, not the originals: the
        # validator resolves paths, and a value swapped between check and use
        # would defeat the check.
        tool_call.params = resolution.params
        task.tool_params = tool_call.params

        task.status = TaskStatus.RUNNING
        db.commit()
        exec_result = tool.execute(tool_call.params, dry_run=dry_run)

        # --------------------------------------------------------------
        # 6. Persist result
        # --------------------------------------------------------------
        result_row = Result(
            task_id=task.id,
            success=exec_result.success,
            summary=exec_result.summary,
            data=exec_result.data,
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
        )
        db.add(result_row)

        warnings.extend(exec_result.warnings or [])
        duration_ms = int((time.time() - started) * 1000)
        task.duration_ms = duration_ms
        task.completed_at = datetime.utcnow()
        task.status = (
            TaskStatus.DRY_RUN if dry_run
            else (TaskStatus.SUCCESS if exec_result.success else TaskStatus.FAILED)
        )
        if not exec_result.success:
            task.error_message = exec_result.stderr or exec_result.summary
        db.commit()

        audit_log(
            db,
            event="command.executed",
            severity="info" if exec_result.success else "error",
            task_id=task.id,
            user_id=user.id if user else None,
            details={
                "command": command,
                "tool": tool_call.tool_name,
                "dry_run": dry_run,
                "success": exec_result.success,
            },
            ip_address=ip_address,
            intent_source=intent_source,
            llm_tokens_used=llm_tokens_used,
            llm_latency_ms=llm_latency_ms,
            validation_result="valid",
        )

        result_payload = exec_result.to_dict()
        return ExecuteResponse(
            task_id=task.id,
            status=task.status,
            intent=intent,
            tool_call=tool_call,
            result=result_payload,
            summary=exec_result.summary,
            duration_ms=duration_ms,
            warnings=warnings,
        )

    except MCPRouterError as exc:
        task.status = TaskStatus.FAILED
        task.error_message = str(exc)
        task.duration_ms = int((time.time() - started) * 1000)
        task.completed_at = datetime.utcnow()
        db.commit()
        audit_log(
            db,
            event="command.routing_failed",
            severity="error",
            task_id=task.id,
            user_id=user.id if user else None,
            details={"command": command, "error": str(exc)},
            ip_address=ip_address,
            intent_source=intent_source,
            llm_tokens_used=llm_tokens_used,
            llm_latency_ms=llm_latency_ms,
            validation_result=f"routing_error: {exc}",
        )
        return ExecuteResponse(
            task_id=task.id,
            status=TaskStatus.FAILED,
            intent=intent,
            error=str(exc),
            warnings=warnings,
            duration_ms=task.duration_ms,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Executor crashed")
        task.status = TaskStatus.FAILED
        task.error_message = str(exc)
        task.duration_ms = int((time.time() - started) * 1000)
        task.completed_at = datetime.utcnow()
        db.commit()
        audit_log(
            db,
            event="command.crashed",
            severity="error",
            task_id=task.id,
            user_id=user.id if user else None,
            details={"command": command, "error": str(exc)},
            ip_address=ip_address,
            intent_source=intent_source,
            llm_tokens_used=llm_tokens_used,
            llm_latency_ms=llm_latency_ms,
            validation_result=f"error: {exc}",
        )
        return ExecuteResponse(
            task_id=task.id,
            status=TaskStatus.FAILED,
            intent=intent,
            tool_call=tool_call,
            error=str(exc),
            warnings=warnings,
            duration_ms=task.duration_ms,
        )
