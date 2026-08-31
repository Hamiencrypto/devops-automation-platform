"""POST /execute — the primary entry point for natural-language commands."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user_optional
from app.database import get_db
from app.models import User
from app.safety import SafetyError
from app.schemas import ExecuteRequest, ExecuteResponse
from app.services import execute_command

router = APIRouter()


@router.post("/execute", response_model=ExecuteResponse, summary="Execute NL command")
def execute(
    payload: ExecuteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> ExecuteResponse:
    """Accept a natural-language DevOps command and run it through the MCP pipeline."""
    try:
        return execute_command(
            db,
            command=payload.command,
            dry_run=payload.dry_run,
            confirm_destructive=payload.confirm_destructive,
            user=user,
            ip_address=request.client.host if request.client else None,
        )
    except SafetyError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
