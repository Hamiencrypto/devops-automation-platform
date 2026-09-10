"""Direct container management endpoints (ID-based, no NL).

These endpoints let the frontend drive stop/remove actions from the UI
(click a row's action button) instead of having to type a natural
language command. Every call routes through
`app.services.tool_execution.resolve_and_validate()` before touching the
tool — the same structured-validator boundary the natural-language path
goes through — so the protected-container policy applies here too.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Result, Task, TaskStatus, User
from app.safety import audit_log
from app.services.tool_execution import resolve_and_validate
from app.tools.base import ToolResult

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_and_validate(params: dict[str, Any]):
    """Resolve + validate against docker_manager's schema and policy. Raises
    the same way for an unregistered tool or a denied call, so a caller
    can't reach `tool.execute()` without going through this."""
    resolution = resolve_and_validate("docker_manager", params)
    if resolution.tool is None:
        raise HTTPException(status_code=503, detail="Docker tool is not loaded")
    if not resolution.ok:
        raise HTTPException(status_code=403, detail=resolution.reason)
    return resolution


def _persist(
    db: Session,
    *,
    command: str,
    intent: str,
    params: dict[str, Any],
    result: ToolResult,
    user: User,
    ip_address: str | None,
) -> Task:
    task = Task(
        command=command,
        dry_run=False,
        status=(TaskStatus.SUCCESS if result.success else TaskStatus.FAILED),
        detected_intent=intent,
        intent_confidence=1.0,
        entities=params,
        selected_tool="docker_manager",
        tool_params=params,
        completed_at=datetime.utcnow(),
        duration_ms=0,
        user_id=user.id if user else None,
    )
    db.add(task)
    db.flush()
    db.add(
        Result(
            task_id=task.id,
            success=result.success,
            summary=result.summary,
            data=result.data,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    )
    audit_log(
        db,
        event="container.direct_action",
        severity="info" if result.success else "error",
        task_id=task.id,
        user_id=user.id if user else None,
        details={"intent": intent, "params": params, "success": result.success},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(task)
    return task


@router.get("/", summary="List all containers")
def list_containers(
    user: User = Depends(get_current_user),
):
    resolution = _resolve_and_validate({"action": "list"})
    tool = resolution.tool
    res = tool.execute(resolution.params)
    if not res.success:
        raise HTTPException(status_code=502, detail=res.stderr or res.summary)
    containers = res.data.get("containers", []) if res.data else []
    # Decorate with managed flag based on our label convention
    for c in containers:
        name = c.get("name") or ""
        c["managed"] = name.startswith("mcp-managed-")
    return {"total": len(containers), "containers": containers}


@router.post("/{container_id}/stop", summary="Stop a container by ID or name")
def stop_container_by_id(
    container_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not container_id or len(container_id) < 3:
        raise HTTPException(status_code=400, detail="Invalid container identifier")
    resolution = _resolve_and_validate({"action": "stop", "container": container_id})
    tool = resolution.tool
    params = resolution.params
    res = tool.execute(params)
    task = _persist(
        db,
        command=f"stop {container_id}",
        intent="docker.stop",
        params=params,
        result=res,
        user=user,
        ip_address=request.client.host if request.client else None,
    )
    return {
        "task_id": task.id,
        "success": res.success,
        "summary": res.summary,
        "data": res.data,
    }


@router.delete("/{container_id}", summary="Remove a container by ID or name")
def remove_container_by_id(
    container_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not container_id or len(container_id) < 3:
        raise HTTPException(status_code=400, detail="Invalid container identifier")
    resolution = _resolve_and_validate({"action": "remove", "container": container_id})
    tool = resolution.tool
    params = resolution.params
    res = tool.execute(params)
    task = _persist(
        db,
        command=f"remove {container_id}",
        intent="docker.remove",
        params=params,
        result=res,
        user=user,
        ip_address=request.client.host if request.client else None,
    )
    return {
        "task_id": task.id,
        "success": res.success,
        "summary": res.summary,
        "data": res.data,
    }
