"""FastAPI application entry point.

Wires together: database, MCP tool registry, API routers, CORS, and health.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings
from app.database import init_db
from app.mcp.registry import tool_registry
from app.schemas import HealthResponse
from app.tools import load_all_tools

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s",
)
logger = logging.getLogger("devops-mcp")


# ---------------------------------------------------------------------
# Lifespan — runs once at startup and once at shutdown
# ---------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    # Load all MCP tools (self-register with tool_registry)
    load_all_tools()
    logger.info("Loaded %d MCP tool(s): %s",
                len(tool_registry.list_tools()),
                [t.name for t in tool_registry.list_tools()])
    # Create database tables if they don't exist
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database init failed (continuing): %s", exc)

    yield

    logger.info("Shutting down %s", settings.APP_NAME)


# ---------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered DevOps Automation Platform with MCP (Model Context Protocol) "
        "Routing. Accepts natural-language commands and routes them to the "
        "appropriate DevOps tool."
    ),
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------
# Root & health endpoints
# ---------------------------------------------------------------------
@app.get("/", summary="Root / banner")
def root() -> dict:
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "registered_tools": len(tool_registry.list_tools()),
    }


@app.get("/health", response_model=HealthResponse, summary="Health check")
def health() -> HealthResponse:
    checks: dict[str, str] = {
        "api": "ok",
        "tools_loaded": str(len(tool_registry.list_tools())),
    }
    # DB check
    try:
        from sqlalchemy import text

        from app.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    # Docker check (non-fatal)
    try:
        import docker
        docker.from_env().ping()
        checks["docker"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["docker"] = f"unavailable: {exc}"

    overall = "ok" if checks.get("database") == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        checks=checks,
    )


# Mount all API routes
app.include_router(api_router)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
