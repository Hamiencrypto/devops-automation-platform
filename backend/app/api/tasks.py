"""Task history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Result, Task
from app.schemas import ResultOut, TaskListResponse, TaskOut

router = APIRouter()


@router.get("/", response_model=TaskListResponse, summary="List task history")
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None, description="Filter by status"),
    intent: str | None = Query(None, description="Filter by intent name"),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    if intent:
        query = query.filter(Task.detected_intent == intent)
    total = query.count()
    items = (
        query.order_by(desc(Task.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TaskListResponse(
        total=total, page=page, page_size=page_size, items=items
    )


@router.get("/{task_id}", response_model=TaskOut, summary="Get single task")
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get(
    "/{task_id}/result",
    response_model=ResultOut,
    summary="Get raw result for a task",
)
def get_task_result(task_id: int, db: Session = Depends(get_db)) -> Result:
    result = db.query(Result).filter(Result.task_id == task_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result
