"""FastAPI router package."""

from fastapi import APIRouter

from app.api import auth as auth_routes
from app.api import containers as container_routes
from app.api import execute as execute_routes
from app.api import tasks as task_routes
from app.api import tools as tool_routes
from app.api import websocket as ws_routes

api_router = APIRouter()
api_router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
api_router.include_router(execute_routes.router, tags=["execute"])
api_router.include_router(task_routes.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(tool_routes.router, prefix="/tools", tags=["tools"])
api_router.include_router(
    container_routes.router, prefix="/containers", tags=["containers"]
)
api_router.include_router(ws_routes.router, tags=["websocket"])
