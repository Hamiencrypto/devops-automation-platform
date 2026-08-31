"""System health MCP tool — report host CPU, memory, disk, and platform info.

Uses stdlib only (no psutil dependency) so it works on a minimal container.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import time
from typing import Any

from app.mcp.registry import tool_registry
from app.tools.base import MCPTool, ToolResult

logger = logging.getLogger(__name__)


class SystemTool(MCPTool):
    name = "system_inspector"
    description = (
        "Report the health and resource usage of this host. Use this when "
        "asked whether the system is healthy or under load, how much memory "
        "or RAM is in use, how much disk space is free or whether the host is "
        "running out of space, what the CPU load is, how long the machine has "
        "been up, or which operating system it runs. Read-only."
    )
    category = "system"
    destructive = False
    intents = ("system.health", "system.disk", "system.memory")
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["health", "disk", "memory"],
            },
        },
        "required": ["action"],
    }

    # -----------------------------------------------------------------
    def execute(self, params: dict[str, Any], dry_run: bool = False) -> ToolResult:
        action = params.get("action")
        try:
            if action == "health":
                return self._health()
            if action == "disk":
                return self._disk()
            if action == "memory":
                return self._memory()
            return self.fail(f"Unknown system action: {action}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("System tool failed")
            return self.fail(f"System error: {exc}", stderr=str(exc))

    # -----------------------------------------------------------------
    def _health(self) -> ToolResult:
        disk = shutil.disk_usage("/")
        load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        data = {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "load_avg": {"1m": load[0], "5m": load[1], "15m": load[2]},
            "disk_total_gb": round(disk.total / 1024**3, 2),
            "disk_used_gb": round(disk.used / 1024**3, 2),
            "disk_free_gb": round(disk.free / 1024**3, 2),
            "timestamp": int(time.time()),
        }
        return self.ok(
            f"{data['system']} {data['release']} on {data['machine']} — "
            f"{data['cpu_count']} CPU, {data['disk_free_gb']} GB free",
            **data,
        )

    def _disk(self) -> ToolResult:
        usage = shutil.disk_usage("/")
        pct = (usage.used / usage.total) * 100 if usage.total else 0
        return self.ok(
            f"Disk: {usage.used / 1024**3:.1f} GB used of "
            f"{usage.total / 1024**3:.1f} GB ({pct:.1f}%)",
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            percent_used=round(pct, 2),
        )

    def _memory(self) -> ToolResult:
        # Parse /proc/meminfo on Linux; fall back gracefully elsewhere.
        meminfo_path = "/proc/meminfo"
        if os.path.exists(meminfo_path):
            info: dict[str, int] = {}
            with open(meminfo_path) as fh:
                for line in fh:
                    parts = line.split(":")
                    if len(parts) != 2:
                        continue
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    try:
                        info[key] = int(val) * 1024  # kB -> bytes
                    except ValueError:
                        continue
            total = info.get("MemTotal", 0)
            free = info.get("MemAvailable", info.get("MemFree", 0))
            used = total - free
            pct = (used / total) * 100 if total else 0
            return self.ok(
                f"Memory: {used / 1024**3:.2f} GB used of "
                f"{total / 1024**3:.2f} GB ({pct:.1f}%)",
                total_bytes=total,
                used_bytes=used,
                free_bytes=free,
                percent_used=round(pct, 2),
                source="/proc/meminfo",
            )
        return ToolResult(
            success=True,
            summary="Memory statistics are not available on this platform "
            "(no /proc/meminfo).",
            data={"source": "unavailable"},
            warnings=["Install psutil for cross-platform memory stats."],
        )


tool_registry.register(SystemTool())
