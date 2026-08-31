"""Tool catalog endpoints — expose MCP-compliant descriptions to UI/API clients."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.mcp.registry import tool_registry
from app.schemas import ToolCatalogResponse, ToolSchema

router = APIRouter()


@router.get("/", response_model=ToolCatalogResponse, summary="List MCP tools")
def list_tools() -> ToolCatalogResponse:
    schemas = tool_registry.to_schema()
    return ToolCatalogResponse(total=len(schemas), tools=schemas)


@router.get("/intents", summary="List all registered intents")
def list_intents() -> dict:
    return {"intents": tool_registry.list_intents()}


@router.get("/{tool_name}", response_model=ToolSchema, summary="Get tool schema")
def get_tool(tool_name: str) -> ToolSchema:
    tool = tool_registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return ToolSchema(
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        intents=list(tool.intents),
        destructive=tool.destructive,
        category=tool.category,
    )
