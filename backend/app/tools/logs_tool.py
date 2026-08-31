"""Logs MCP tool — analyze, summarize, tail, and count errors in log files.

Accepts a file path and performs structural analysis using compiled regex
patterns that recognise common log severity keywords.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

from app.config import settings
from app.mcp.registry import tool_registry
from app.tools.base import MCPTool, ToolResult

logger = logging.getLogger(__name__)


ERROR_RE = re.compile(r"\b(error|fatal|exception|critical|traceback|failed)\b", re.IGNORECASE)
WARN_RE = re.compile(r"\b(warn(?:ing)?|deprecated|retry|timeout)\b", re.IGNORECASE)
INFO_RE = re.compile(r"\b(info|success|ok|started|listening)\b", re.IGNORECASE)

# Rough timestamp detector (ISO-ish formats)
TS_RE = re.compile(
    r"\b(?:\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}|\d{2}:\d{2}:\d{2})\b"
)


class LogsTool(MCPTool):
    name = "logs_analyzer"
    description = (
        "Read and analyse a log file at a given path. Use this to check, "
        "review, examine or look through logs, to count or find errors, "
        "warnings and failures, to summarise what went wrong, to show the "
        "last N lines (tail), and to extract timestamps. Use this whenever "
        "the request is about what a log file contains."
    )
    category = "logs"
    destructive = False
    intents = ("logs.analyze", "logs.errors", "logs.summary", "logs.tail")
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["analyze", "errors", "summary", "tail"],
            },
            "path": {"type": "string", "description": "Path to log file"},
            "lines": {"type": "integer", "default": 50},
        },
        "required": ["action"],
    }

    # -----------------------------------------------------------------
    def execute(self, params: dict[str, Any], dry_run: bool = False) -> ToolResult:
        action = params.get("action")
        path = params.get("path")
        if not path:
            return self.fail(
                "No log file path provided. Example: 'analyze logs at /var/log/app.log'"
            )

        file_path = Path(path).expanduser()
        if not file_path.exists():
            return self.fail(f"Log file not found: {file_path}")
        if not file_path.is_file():
            return self.fail(f"Path is not a file: {file_path}")

        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            return self.fail(
                f"File is {size_mb:.1f}MB, exceeding limit of {settings.MAX_FILE_SIZE_MB}MB"
            )

        if dry_run:
            return ToolResult(
                success=True,
                summary=f"[DRY RUN] Would {action} log file {file_path}",
                data={"action": action, "path": str(file_path)},
            )

        try:
            if action == "analyze":
                return self._analyze(file_path)
            if action == "errors":
                return self._errors(file_path)
            if action == "summary":
                return self._summary(file_path)
            if action == "tail":
                return self._tail(file_path, int(params.get("lines") or 50))
            return self.fail(f"Unknown logs action: {action}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Logs tool failed")
            return self.fail(f"Log analysis error: {exc}", stderr=str(exc))

    # -----------------------------------------------------------------
    def _read_lines(self, path: Path) -> list[str]:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()

    def _analyze(self, path: Path) -> ToolResult:
        lines = self._read_lines(path)
        error_lines = [l for l in lines if ERROR_RE.search(l)]
        warn_lines = [l for l in lines if WARN_RE.search(l)]
        info_lines = [l for l in lines if INFO_RE.search(l)]

        # Top error messages
        top_errors = Counter(
            l.strip()[:160] for l in error_lines
        ).most_common(5)

        return self.ok(
            f"Analyzed {len(lines)} line(s): {len(error_lines)} errors, "
            f"{len(warn_lines)} warnings, {len(info_lines)} info",
            total_lines=len(lines),
            errors=len(error_lines),
            warnings=len(warn_lines),
            info=len(info_lines),
            size_bytes=path.stat().st_size,
            top_errors=[{"message": m, "count": c} for m, c in top_errors],
            sample_errors=[l.strip() for l in error_lines[:5]],
        )

    def _errors(self, path: Path) -> ToolResult:
        lines = self._read_lines(path)
        errors = [l.strip() for l in lines if ERROR_RE.search(l)]
        return ToolResult(
            success=True,
            summary=f"Found {len(errors)} error line(s) in {path.name}",
            data={"count": len(errors), "errors": errors[:100]},
            stdout="\n".join(errors[:100]),
        )

    def _summary(self, path: Path) -> ToolResult:
        lines = self._read_lines(path)
        timestamps = [m.group(0) for l in lines for m in [TS_RE.search(l)] if m]
        first_ts = timestamps[0] if timestamps else None
        last_ts = timestamps[-1] if timestamps else None
        return self.ok(
            f"Summary of {path.name}: {len(lines)} lines",
            file=str(path),
            total_lines=len(lines),
            timestamp_coverage=len(timestamps),
            first_timestamp=first_ts,
            last_timestamp=last_ts,
            errors=sum(1 for l in lines if ERROR_RE.search(l)),
            warnings=sum(1 for l in lines if WARN_RE.search(l)),
        )

    def _tail(self, path: Path, n: int) -> ToolResult:
        lines = self._read_lines(path)
        tail = lines[-n:]
        return ToolResult(
            success=True,
            summary=f"Last {len(tail)} line(s) of {path.name}",
            data={"count": len(tail)},
            stdout="".join(tail),
        )


tool_registry.register(LogsTool())
