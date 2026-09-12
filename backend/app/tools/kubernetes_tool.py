"""Kubernetes MCP tool (advanced feature).

Provides a graceful degradation model: if kubectl isn't available or a
cluster isn't reachable, the tool returns informative messages but still
demonstrates the MCP routing layer correctly.

For the FYP demo, this is enough to showcase multi-platform extensibility.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any

from app.mcp.registry import tool_registry
from app.tools.base import MCPTool, ToolResult

logger = logging.getLogger(__name__)


class KubernetesTool(MCPTool):
    name = "kubernetes_manager"
    description = (
        "Operate on a Kubernetes cluster: list pods, deploy an image as a "
        "deployment, and scale a deployment to a number of replicas. Only use "
        "this when the request explicitly mentions Kubernetes, k8s, pods, "
        "nodes, namespaces or replicas. For plain containers on this host, "
        "use the Docker tool instead. Requires kubectl and a reachable "
        "cluster context."
    )
    category = "kubernetes"
    destructive = False
    intents = ("k8s.list_pods", "k8s.deploy", "k8s.scale")
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list_pods", "deploy", "scale"]},
            "namespace": {"type": "string", "default": "default"},
            "image": {"type": "string"},
            "original_image": {
                "type": "string",
                "description": "User's original wording before typo/alias resolution, "
                "when it differs from the resolved `image`. Not currently used by this "
                "tool; declared so a deploy through the alias table isn't rejected as "
                "an unrecognised parameter.",
            },
            "resource": {"type": "string"},
            "replicas": {"type": "integer"},
        },
        "required": ["action"],
    }

    # -----------------------------------------------------------------
    def _have_kubectl(self) -> bool:
        return shutil.which("kubectl") is not None

    def _run(self, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["kubectl", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    # -----------------------------------------------------------------
    def execute(self, params: dict[str, Any], dry_run: bool = False) -> ToolResult:
        action = params.get("action")

        if not self._have_kubectl():
            return ToolResult(
                success=False,
                summary="kubectl is not installed on this host. Install it to "
                "enable Kubernetes operations.",
                data={"action": action, "kubectl_available": False},
                warnings=["Kubernetes tool is registered but kubectl is missing."],
            )

        try:
            if action == "list_pods":
                return self._list_pods(params)
            if action == "deploy":
                return self._deploy(params, dry_run)
            if action == "scale":
                return self._scale(params, dry_run)
            return self.fail(f"Unknown k8s action: {action}")
        except subprocess.TimeoutExpired:
            return self.fail("kubectl command timed out")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Kubernetes tool failed")
            return self.fail(f"Kubernetes error: {exc}", stderr=str(exc))

    # -----------------------------------------------------------------
    def _list_pods(self, params: dict[str, Any]) -> ToolResult:
        ns = params.get("namespace") or "default"
        proc = self._run(["get", "pods", "-n", ns, "-o", "wide"])
        if proc.returncode != 0:
            return self.fail(f"kubectl failed: {proc.stderr.strip()}", stderr=proc.stderr)
        lines = [l for l in proc.stdout.strip().split("\n") if l]
        count = max(0, len(lines) - 1)  # subtract header
        return ToolResult(
            success=True,
            summary=f"Found {count} pod(s) in namespace '{ns}'",
            data={"namespace": ns, "count": count},
            stdout=proc.stdout,
        )

    def _deploy(self, params: dict[str, Any], dry_run: bool) -> ToolResult:
        image = params.get("image")
        if not image:
            return self.fail("No image specified for deployment.")
        ns = params.get("namespace") or "default"
        name = f"mcp-{image.split('/')[-1].split(':')[0]}"
        args = ["create", "deployment", name, f"--image={image}", "-n", ns]
        if dry_run:
            args += ["--dry-run=client", "-o", "yaml"]
        proc = self._run(args)
        if proc.returncode != 0:
            return self.fail(f"kubectl failed: {proc.stderr.strip()}", stderr=proc.stderr)
        return ToolResult(
            success=True,
            summary=(
                f"[DRY RUN] Would create deployment '{name}' with {image} in {ns}"
                if dry_run
                else f"Created deployment '{name}' with {image} in namespace {ns}"
            ),
            data={"deployment": name, "image": image, "namespace": ns, "dry_run": dry_run},
            stdout=proc.stdout,
        )

    def _scale(self, params: dict[str, Any], dry_run: bool) -> ToolResult:
        resource = params.get("resource")
        replicas = params.get("replicas")
        ns = params.get("namespace") or "default"
        if not resource or replicas is None:
            return self.fail("Need both a resource name and replica count.")
        if dry_run:
            return ToolResult(
                success=True,
                summary=f"[DRY RUN] Would scale {resource} to {replicas} replicas in {ns}",
                data={"resource": resource, "replicas": replicas, "namespace": ns},
            )
        proc = self._run(
            ["scale", f"deployment/{resource}", f"--replicas={replicas}", "-n", ns]
        )
        if proc.returncode != 0:
            return self.fail(f"kubectl failed: {proc.stderr.strip()}", stderr=proc.stderr)
        return self.ok(
            f"Scaled {resource} to {replicas} replicas in {ns}",
            resource=resource, replicas=int(replicas), namespace=ns,
        )


tool_registry.register(KubernetesTool())
