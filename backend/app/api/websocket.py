"""WebSocket endpoints for real-time log streaming.

Clients connect to /ws/logs/{container_name} and receive live log lines as
JSON frames:  {"line": "...", "timestamp": "..."}.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/logs/{container_name}")
async def stream_container_logs(websocket: WebSocket, container_name: str) -> None:
    """Stream Docker container logs line-by-line over WebSocket."""
    await websocket.accept()
    try:
        import docker  # local import avoids crashing if SDK unavailable
    except ImportError:
        await websocket.send_json({"error": "docker SDK not installed"})
        await websocket.close()
        return

    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"error": f"Container '{container_name}' error: {exc}"})
        await websocket.close()
        return

    await websocket.send_json({
        "event": "connected",
        "container": container_name,
        "timestamp": datetime.utcnow().isoformat(),
    })

    try:
        # `stream=True, follow=True` yields bytes as they arrive.
        log_stream = container.logs(stream=True, follow=True, tail=20)
        loop = asyncio.get_event_loop()

        def next_line():
            try:
                return next(log_stream)
            except StopIteration:
                return None

        while True:
            line = await loop.run_in_executor(None, next_line)
            if line is None:
                break
            decoded = line.decode("utf-8", errors="replace").rstrip()
            if not decoded:
                continue
            await websocket.send_json({
                "line": decoded,
                "timestamp": datetime.utcnow().isoformat(),
            })
    except WebSocketDisconnect:
        logger.info("WS client disconnected for %s", container_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("WS log stream failed")
        try:
            await websocket.send_json({"error": str(exc)})
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass


@router.websocket("/ws/events")
async def stream_events(websocket: WebSocket) -> None:
    """Placeholder event-stream for future real-time task updates."""
    await websocket.accept()
    try:
        await websocket.send_json({"event": "connected"})
        while True:
            msg = await websocket.receive_text()
            await websocket.send_json({"echo": msg, "timestamp": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        return
