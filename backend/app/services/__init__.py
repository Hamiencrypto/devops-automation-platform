"""Service layer — orchestrates intent → MCP → tool execution."""

from app.services.executor import execute_command

__all__ = ["execute_command"]
