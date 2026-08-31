"""MCP tool implementations.

Each tool subclasses MCPTool and self-registers with the tool_registry when
imported. `load_all_tools()` imports every tool module so the registry is
fully populated at application startup.
"""

from app.tools.base import MCPTool, ToolResult


def load_all_tools() -> None:
    """Import every tool module to trigger self-registration."""
    # Importing has the side effect of calling tool_registry.register()
    from app.tools import docker_tool  # noqa: F401
    from app.tools import logs_tool  # noqa: F401
    from app.tools import file_tool  # noqa: F401
    from app.tools import kubernetes_tool  # noqa: F401
    from app.tools import system_tool  # noqa: F401


__all__ = ["MCPTool", "ToolResult", "load_all_tools"]
