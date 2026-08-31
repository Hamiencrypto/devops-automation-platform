"""File MCP tool — describe, read, count, and validate files.

Performs safe, read-only operations on files passed as paths. Validates
JSON/YAML/XML syntax where possible.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.mcp.registry import tool_registry
from app.tools.base import MCPTool, ToolResult

logger = logging.getLogger(__name__)


class FileTool(MCPTool):
    name = "file_processor"
    description = (
        "Inspect a single file at a given path. Use this to show file "
        "metadata (size, type, modified time), to count lines, words or "
        "characters, to read or display the contents, and to check that a "
        "JSON, YAML or XML file is well formed. For log analysis prefer the "
        "logs tool."
    )
    category = "file"
    destructive = False
    intents = ("file.info", "file.count", "file.read", "file.validate")
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["info", "count", "read", "validate"]},
            "path": {"type": "string"},
            "what": {"type": "string", "enum": ["lines", "words", "characters", "chars"]},
            "max_preview_bytes": {"type": "integer", "default": 8192},
        },
        "required": ["action"],
    }

    # -----------------------------------------------------------------
    def execute(self, params: dict[str, Any], dry_run: bool = False) -> ToolResult:
        action = params.get("action")
        raw_path = params.get("path")
        if not raw_path:
            return self.fail("No file path provided.")

        path = Path(raw_path).expanduser()
        if not path.exists():
            return self.fail(f"File not found: {path}")
        if not path.is_file():
            return self.fail(f"Path is not a file: {path}")

        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            return self.fail(
                f"File is {size_mb:.1f}MB, exceeding limit of {settings.MAX_FILE_SIZE_MB}MB"
            )

        if dry_run:
            return ToolResult(
                success=True,
                summary=f"[DRY RUN] Would {action} file {path}",
                data={"action": action, "path": str(path)},
            )

        try:
            if action == "info":
                return self._info(path)
            if action == "count":
                return self._count(path, params.get("what", "lines"))
            if action == "read":
                return self._read(path, int(params.get("max_preview_bytes") or 8192))
            if action == "validate":
                return self._validate(path)
            return self.fail(f"Unknown file action: {action}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("File tool failed")
            return self.fail(f"File error: {exc}", stderr=str(exc))

    # -----------------------------------------------------------------
    def _info(self, path: Path) -> ToolResult:
        stat = path.stat()
        mime, _ = mimetypes.guess_type(path.name)
        return self.ok(
            f"{path.name} — {stat.st_size} bytes",
            path=str(path),
            name=path.name,
            extension=path.suffix.lstrip(".") or None,
            size_bytes=stat.st_size,
            size_human=self._human_size(stat.st_size),
            mime_type=mime or "application/octet-stream",
            modified_epoch=int(stat.st_mtime),
        )

    def _count(self, path: Path, what: str) -> ToolResult:
        text = path.read_text(encoding="utf-8", errors="replace")
        if what in ("lines",):
            value = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        elif what in ("words", "word"):
            value = len(re.findall(r"\S+", text))
        elif what in ("characters", "chars", "character", "char"):
            value = len(text)
        else:
            return self.fail(f"Unknown count target: {what}")
        return self.ok(
            f"{path.name} has {value} {what}",
            file=str(path), what=what, count=value,
        )

    def _read(self, path: Path, max_bytes: int) -> ToolResult:
        data = path.read_bytes()[:max_bytes]
        try:
            text = data.decode("utf-8")
            binary = False
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
            binary = True
        truncated = path.stat().st_size > max_bytes
        return ToolResult(
            success=True,
            summary=f"Read {len(data)} byte(s) from {path.name}"
            + (" (truncated)" if truncated else ""),
            data={
                "file": str(path),
                "bytes_read": len(data),
                "binary": binary,
                "truncated": truncated,
                "total_size": path.stat().st_size,
            },
            stdout=text,
        )

    def _validate(self, path: Path) -> ToolResult:
        ext = path.suffix.lower().lstrip(".")
        text = path.read_text(encoding="utf-8", errors="replace")

        if ext == "json":
            try:
                json.loads(text)
                return self.ok(f"{path.name} is valid JSON", format="json")
            except json.JSONDecodeError as exc:
                return self.fail(
                    f"Invalid JSON: {exc.msg} at line {exc.lineno}, col {exc.colno}",
                    stderr=str(exc),
                    format="json",
                )
        if ext in ("yaml", "yml"):
            try:
                import yaml  # noqa: F401
            except ImportError:
                # Fall back to a light-weight format heuristic
                return self.ok(
                    f"{path.name} appears to be YAML (yaml module not installed "
                    "for full validation)",
                    format="yaml",
                )
            else:  # pragma: no cover - exercised only when pyyaml is present
                import yaml
                try:
                    yaml.safe_load(text)
                    return self.ok(f"{path.name} is valid YAML", format="yaml")
                except yaml.YAMLError as exc:
                    return self.fail(f"Invalid YAML: {exc}", stderr=str(exc), format="yaml")
        if ext == "xml":
            try:
                from xml.etree import ElementTree as ET
                ET.fromstring(text)
                return self.ok(f"{path.name} is valid XML", format="xml")
            except Exception as exc:  # noqa: BLE001
                return self.fail(f"Invalid XML: {exc}", stderr=str(exc), format="xml")

        return self.ok(
            f"No validator for .{ext} files — returning basic info",
            format=ext,
            size=path.stat().st_size,
        )

    @staticmethod
    def _human_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024  # type: ignore
        return f"{n:.1f} TB"


tool_registry.register(FileTool())
