"""Docker MCP tool — deploy, list, stop, remove, inspect containers, read logs.

Uses the official `docker` Python SDK (docker-py) to talk to the Docker daemon
via the mounted socket. In `dry_run` mode, no side effects are performed; the
tool returns a plan describing what it would have done.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import docker
    from docker.errors import APIError, NotFound
except ImportError:  # pragma: no cover
    docker = None  # type: ignore
    APIError = NotFound = Exception  # type: ignore

from app.config import settings
from app.mcp.registry import tool_registry
from app.tools.base import MCPTool, ToolResult

logger = logging.getLogger(__name__)


class DockerTool(MCPTool):
    name = "docker_manager"
    description = (
        "Run and manage Docker containers. Use this to start, launch, deploy, "
        "set up, spin up, install or create any service, application, database "
        "or server (nginx, redis, mongodb, postgres, rabbitmq, and so on), "
        "optionally on a given port. Also use it to list, show or find running "
        "containers, to stop, kill, remove or delete a container, to inspect "
        "its status, and to read its logs. This is the right tool for any "
        "request about running software on this host."
    )
    category = "docker"
    destructive = False  # Individual actions (stop/remove) are flagged separately
    intents = (
        "docker.deploy",
        "docker.list",
        "docker.stop",
        "docker.remove",
        "docker.status",
        "docker.logs",
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["deploy", "list", "stop", "remove", "status", "logs"],
            },
            "image": {"type": "string", "description": "Docker image name"},
            "container": {"type": "string", "description": "Container name or ID"},
            "port": {"type": "integer", "description": "Host port to publish"},
            "tail": {"type": "integer", "default": 100},
        },
        "required": ["action"],
    }

    # Default container ports for popular images (to avoid requiring users
    # to know them). Keys are matched against the image's short name
    # (everything after the last '/' and before ':').
    DEFAULT_INTERNAL_PORTS: dict[str, int] = {
        "nginx": 80, "httpd": 80, "apache": 80, "caddy": 80, "traefik": 80,
        "redis": 6379, "memcached": 11211,
        "postgres": 5432, "mysql": 3306, "mariadb": 3306,
        "mongo": 27017, "mongodb": 27017,
        "rabbitmq": 5672, "kafka": 9092,
        "elasticsearch": 9200, "kibana": 5601, "logstash": 5044,
        "grafana": 3000, "prometheus": 9090, "influxdb": 8086,
        "node": 3000, "python": 8000, "golang": 8080,
        "jenkins": 8080, "gitea": 3000, "gitlab-ce": 80,
        "portainer-ce": 9000, "vault": 8200, "consul": 8500,
        "minio": 9000,
    }

    # -----------------------------------------------------------------
    # Client
    # -----------------------------------------------------------------
    def _client(self):
        if docker is None:
            raise RuntimeError("docker SDK is not installed on this host")
        return docker.from_env()

    # -----------------------------------------------------------------
    # execute() dispatcher
    # -----------------------------------------------------------------
    def execute(self, params: dict[str, Any], dry_run: bool = False) -> ToolResult:
        action = params.get("action")
        try:
            if action == "deploy":
                return self._deploy(params, dry_run)
            if action == "list":
                return self._list()
            if action == "stop":
                return self._stop(params, dry_run)
            if action == "remove":
                return self._remove(params, dry_run)
            if action == "status":
                return self._status(params)
            if action == "logs":
                return self._logs(params)
            return self.fail(f"Unknown docker action: {action}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Docker tool failed")
            return self.fail(f"Docker error: {exc}", stderr=str(exc))

    # -----------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------
    def _deploy(self, params: dict[str, Any], dry_run: bool) -> ToolResult:
        image = params.get("image")
        if not image:
            return self.fail("No image specified. Try: 'deploy nginx on port 8080'")

        # Clean the image reference defensively — remove any trailing clauses
        # that may have slipped in from loose regex matching.
        image = str(image).strip()
        if ":" in image and image.count(":") == 1 and image.endswith(":"):
            image = image[:-1]

        host_port = int(params.get("port") or 0)

        # Determine the container's internal port:
        # 1. Pull the short image name ("mongo" out of "library/mongo:6").
        # 2. Look it up in the defaults table.
        # 3. Fall back to 80 for generic web images.
        short_name = image.rsplit("/", 1)[-1].split(":")[0].lower()
        internal_port = self.DEFAULT_INTERNAL_PORTS.get(short_name, 80)
        name = f"{settings.CONTAINER_PREFIX}{image.replace(':', '-').replace('/', '-')}"
        # Ensure the host port is set to something reasonable for deploy
        if not host_port:
            host_port = internal_port

        warnings: list[str] = []
        if "original_image" in params and params["original_image"]:
            warnings.append(
                f"Interpreted '{params['original_image']}' as the Docker image '{image}'."
            )

        plan = {
            "action": "deploy",
            "image": image,
            "container_name": name,
            "host_port": host_port,
            "internal_port": internal_port,
        }

        if dry_run:
            return ToolResult(
                success=True,
                summary=f"[DRY RUN] Would deploy {image} as '{name}' on port {host_port}",
                data=plan,
                warnings=warnings,
            )

        client = self._client()
        # Pull image if missing — surface a helpful error if pull fails.
        try:
            client.images.get(image)
        except NotFound:
            logger.info("Pulling image %s", image)
            try:
                client.images.pull(image)
            except Exception as pull_exc:  # noqa: BLE001
                return self.fail(
                    f"Could not pull image '{image}': {pull_exc}. "
                    "Check the name or that the image exists on Docker Hub.",
                    stderr=str(pull_exc),
                )

        # If a container with the same name exists, remove it first
        try:
            existing = client.containers.get(name)
            existing.remove(force=True)
            logger.info("Removed existing container %s", name)
        except NotFound:
            pass

        try:
            container = client.containers.run(
                image=image,
                name=name,
                detach=True,
                ports={f"{internal_port}/tcp": host_port},
                labels={"managed-by": "devops-mcp-platform"},
            )
        except APIError as run_exc:
            return self.fail(
                f"Docker refused to start '{image}': {run_exc.explanation or run_exc}",
                stderr=str(run_exc),
            )

        plan["container_id"] = container.short_id
        plan["status"] = container.status
        return ToolResult(
            success=True,
            summary=(
                f"Deployed {image} as '{name}' — accessible on "
                f"http://localhost:{host_port}"
            ),
            data=plan,
            warnings=warnings,
        )

    def _list(self) -> ToolResult:
        client = self._client()
        containers = client.containers.list(all=True)
        items = [
            {
                "id": c.short_id,
                "name": c.name,
                "image": (c.image.tags[0] if c.image.tags else c.image.short_id),
                "status": c.status,
                "ports": c.ports,
            }
            for c in containers
        ]
        return self.ok(f"Found {len(items)} container(s)", containers=items, count=len(items))

    def _stop(self, params: dict[str, Any], dry_run: bool) -> ToolResult:
        container_name = params.get("container")
        if not container_name:
            return self.fail("No container name provided.")
        if dry_run:
            return ToolResult(
                success=True,
                summary=f"[DRY RUN] Would stop container '{container_name}'",
                data={"container": container_name},
            )
        client = self._client()
        try:
            container = client.containers.get(container_name)
            container.stop(timeout=10)
            return self.ok(f"Stopped container '{container_name}'", container=container_name)
        except NotFound:
            return self.fail(f"Container '{container_name}' not found")

    def _remove(self, params: dict[str, Any], dry_run: bool) -> ToolResult:
        container_name = params.get("container")
        if not container_name:
            return self.fail("No container name provided.")
        if dry_run:
            return ToolResult(
                success=True,
                summary=f"[DRY RUN] Would remove container '{container_name}'",
                data={"container": container_name},
            )
        client = self._client()
        try:
            container = client.containers.get(container_name)
            container.remove(force=True)
            return self.ok(f"Removed container '{container_name}'", container=container_name)
        except NotFound:
            return self.fail(f"Container '{container_name}' not found")

    def _status(self, params: dict[str, Any]) -> ToolResult:
        container_name = params.get("container")
        if not container_name:
            return self.fail("No container name provided.")
        client = self._client()
        try:
            c = client.containers.get(container_name)
            return self.ok(
                f"Container '{c.name}' is {c.status}",
                id=c.short_id,
                name=c.name,
                image=(c.image.tags[0] if c.image.tags else c.image.short_id),
                status=c.status,
                ports=c.ports,
                created=c.attrs.get("Created"),
                started_at=c.attrs.get("State", {}).get("StartedAt"),
            )
        except NotFound:
            return self.fail(f"Container '{container_name}' not found")

    def _logs(self, params: dict[str, Any]) -> ToolResult:
        container_name = params.get("container")
        tail = int(params.get("tail") or 100)
        if not container_name:
            return self.fail("No container name provided.")
        client = self._client()
        try:
            c = client.containers.get(container_name)
            logs = c.logs(tail=tail).decode("utf-8", errors="replace")
            return ToolResult(
                success=True,
                summary=f"Retrieved last {tail} log lines from '{container_name}'",
                data={"container": container_name, "tail": tail, "line_count": logs.count('\n')},
                stdout=logs,
            )
        except NotFound:
            return self.fail(f"Container '{container_name}' not found")


# Self-register
tool_registry.register(DockerTool())
