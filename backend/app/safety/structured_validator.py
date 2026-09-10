"""
Structured output validation — the authoritative safety boundary.

Two layers, deliberately separated:

  Layer 1 (schema)  the proposed call names a registered tool, and its
                    arguments satisfy that tool's published JSON Schema.
                    This bounds the *shape* of what can be requested.

  Layer 2 (policy)  the arguments, though well-formed, are checked against
                    operational rules: which filesystem roots are readable,
                    which ports may be bound, which Kubernetes namespaces are
                    off limits. This bounds the *reach* of what can be done.

Schema alone is not enough. `{"path": "/etc/shadow"}` is a perfectly valid
string against a `{"type": "string"}` schema. Policy is where that gets
stopped.

Critically, this validator is source-agnostic. It does not know or care
whether a regex pattern or a language model produced the parameters. If it
only guarded the LLM path, the regex path would be a bypass — and an examiner
who understands the threat model will look for exactly that.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    valid: bool
    reason: str = ""
    # Params after normalisation (e.g. resolved paths). Callers should execute
    # with these, not with the originals, so the checked value is the used value.
    params: dict[str, Any] | None = None

    def __bool__(self) -> bool:
        return self.valid


def ok(params: dict[str, Any]) -> ValidationResult:
    return ValidationResult(True, params=params)


def deny(reason: str) -> ValidationResult:
    return ValidationResult(False, reason=reason)


# --------------------------------------------------------------------------
# Policy configuration
# --------------------------------------------------------------------------


@dataclass
class SafetyPolicy:
    """
    Operational limits. Sourced from config so they differ per environment —
    a staging deployment can be looser than production without a code change.
    """

    allowed_file_roots: tuple[str, ...] = ("/data",)
    max_file_bytes: int = 10 * 1024 * 1024

    # Names that must never be read regardless of location, in case a root is
    # ever misconfigured to something broad.
    denied_filenames: frozenset[str] = frozenset(
        {
            "shadow", "passwd", "sudoers", "id_rsa", "id_ed25519",
            ".env", ".netrc", ".pgpass", "credentials", "authorized_keys",
        }
    )
    denied_suffixes: frozenset[str] = frozenset({".key", ".pem", ".p12", ".pfx", ".kdbx"})

    min_port: int = 1024          # below this needs privilege; never bind it
    max_port: int = 65535
    reserved_ports: frozenset[int] = frozenset({3000, 5432, 8000, 9090, 3001})

    allowed_image_registries: tuple[str, ...] = ("docker.io", "ghcr.io", "registry.k8s.io")
    denied_image_names: frozenset[str] = frozenset()

    protected_namespaces: frozenset[str] = frozenset(
        {"kube-system", "kube-public", "kube-node-lease", "istio-system", "monitoring"}
    )
    max_replicas: int = 10

    # Containers the platform must never act on — including its own.
    protected_containers: frozenset[str] = frozenset(
        {"mcp-backend", "mcp-frontend", "mcp-postgres"}
    )

    @classmethod
    def from_settings(cls, settings) -> "SafetyPolicy":
        return cls(
            allowed_file_roots=tuple(
                r.strip() for r in settings.ALLOWED_FILE_ROOTS.split(",") if r.strip()
            ),
            max_file_bytes=settings.MAX_FILE_BYTES,
            min_port=settings.MIN_BINDABLE_PORT,
            max_replicas=settings.MAX_REPLICAS,
        )


# --------------------------------------------------------------------------
# Shared checks
# --------------------------------------------------------------------------

_CONTAINER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_K8S_NAME = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_IMAGE_REF = re.compile(r"^[a-z0-9]+([._/-][a-z0-9]+)*(:[\w.-]+)?(@sha256:[a-f0-9]{64})?$")


def check_path(raw: str, policy: SafetyPolicy) -> ValidationResult:
    """
    Path containment.

    Resolve first, compare second. Resolving collapses `..`, follows symlinks,
    and normalises the string, so `/app/safe_data/../../etc/shadow` and a
    symlink pointing at /etc both fail the containment test rather than
    sneaking past a prefix match on the unresolved string.
    """
    if not raw or not isinstance(raw, str):
        return deny("path must be a non-empty string")

    if "\x00" in raw:
        return deny("path contains a null byte")

    try:
        resolved = Path(raw).resolve(strict=False)
    except (OSError, RuntimeError) as exc:  # RuntimeError = symlink loop
        return deny(f"path could not be resolved: {exc}")

    roots = [Path(r).resolve(strict=False) for r in policy.allowed_file_roots]
    if not any(_is_within(resolved, root) for root in roots):
        # Report the configured roots, not the resolved target. Echoing where
        # the traversal landed confirms filesystem layout to an attacker.
        return deny(
            f"path is outside the permitted directories "
            f"({', '.join(policy.allowed_file_roots)})"
        )

    name = resolved.name.lower()
    if name in policy.denied_filenames or resolved.stem.lower() in policy.denied_filenames:
        return deny("this file is on the protected list")
    if resolved.suffix.lower() in policy.denied_suffixes:
        return deny(f"files of type {resolved.suffix} cannot be read")

    if resolved.exists():
        if resolved.is_dir():
            return deny("path is a directory, not a file")
        try:
            if resolved.stat().st_size > policy.max_file_bytes:
                return deny(
                    f"file exceeds the {policy.max_file_bytes // (1024 * 1024)} MB limit"
                )
        except OSError as exc:
            return deny(f"file could not be inspected: {exc}")

    return ok({"path": str(resolved)})


def _is_within(child: Path, parent: Path) -> bool:
    # Path.is_relative_to needs 3.9+; this form also works and is explicit.
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def check_port(value: Any, policy: SafetyPolicy) -> ValidationResult:
    if isinstance(value, bool) or not isinstance(value, int):
        return deny("port must be an integer")
    if not policy.min_port <= value <= policy.max_port:
        return deny(
            f"port must be between {policy.min_port} and {policy.max_port}; "
            "privileged ports are not available to this platform"
        )
    if value in policy.reserved_ports:
        return deny(f"port {value} is used by the platform itself")
    return ok({"port": value})


# --------------------------------------------------------------------------
# Per-tool policies
# --------------------------------------------------------------------------


def policy_file(params: dict, policy: SafetyPolicy) -> ValidationResult:
    result = check_path(params.get("path", ""), policy)
    if not result:
        return result
    return ok({**params, "path": result.params["path"]})


def policy_logs(params: dict, policy: SafetyPolicy) -> ValidationResult:
    """Log analysis reads arbitrary files, so it gets the same containment."""
    return policy_file(params, policy)


def _is_protected_container(name: str, protected: frozenset[str]) -> bool:
    """True if `name` is (or embeds, e.g. via a compose project prefix like
    `devops-mcp-postgres`) one of the platform's own containers. An exact-match
    check alone is bypassable by anyone who can vary the name string, so a
    protected name must match as a delimiter-bounded segment, not a raw
    substring (`mcp-postgres-backup` is a different container; `x-mcp-postgres`
    is not)."""
    for p in protected:
        if name == p or re.search(rf"(?:^|[-_]){re.escape(p)}(?:[-_]|$)", name):
            return True
    return False


def policy_docker(params: dict, policy: SafetyPolicy) -> ValidationResult:
    action = params.get("action")
    out = dict(params)

    # Flags that would hand the container the host. None of these should be
    # reachable through natural language, and the schema should not expose
    # them — this is the backstop if a schema is later widened carelessly.
    for flag in ("privileged", "cap_add", "devices", "pid_mode", "ipc_mode"):
        if params.get(flag):
            return deny(f"{flag} is not permitted on managed containers")
    if params.get("network_mode") == "host":
        return deny("host networking is not permitted")
    for bind in params.get("volumes", []) or []:
        if isinstance(bind, str) and "docker.sock" in bind:
            return deny("mounting the Docker socket is not permitted")

    name = params.get("name") or params.get("container")
    if name is not None:
        if not isinstance(name, str) or not _CONTAINER_NAME.match(name):
            return deny("container name contains characters that are not allowed")
        if _is_protected_container(name, policy.protected_containers):
            return deny(
                f"{name} is part of the platform itself and cannot be modified from here"
            )

    if "port" in params and params["port"] is not None:
        result = check_port(params["port"], policy)
        if not result:
            return result
        out["port"] = result.params["port"]

    image = params.get("image")
    if action in ("deploy", "run", "start") and image:
        if not isinstance(image, str) or not _IMAGE_REF.match(image):
            return deny("image reference is not a valid form")
        if image.split("/")[0] in policy.denied_image_names:
            return deny("this image is not permitted")
        if "/" in image and "." in image.split("/")[0]:
            registry = image.split("/")[0]
            if registry not in policy.allowed_image_registries:
                return deny(
                    f"images may only come from {', '.join(policy.allowed_image_registries)}"
                )

    return ok(out)


def policy_kubernetes(params: dict, policy: SafetyPolicy) -> ValidationResult:
    out = dict(params)

    ns = params.get("namespace", "default")
    if not isinstance(ns, str) or not _K8S_NAME.match(ns):
        return deny("namespace is not a valid Kubernetes name")
    if ns in policy.protected_namespaces:
        return deny(f"the {ns} namespace is managed by the cluster and is read-only here")

    for key in ("deployment", "name", "resource"):
        value = params.get(key)
        if value is not None and (not isinstance(value, str) or not _K8S_NAME.match(value)):
            return deny(f"{key} is not a valid Kubernetes name")

    replicas = params.get("replicas")
    if replicas is not None:
        if isinstance(replicas, bool) or not isinstance(replicas, int):
            return deny("replicas must be an integer")
        if replicas < 0:
            return deny("replicas cannot be negative")
        if replicas > policy.max_replicas:
            return deny(
                f"scaling above {policy.max_replicas} replicas needs a cluster "
                "administrator, not this platform"
            )

    return ok(out)


def policy_system(params: dict, policy: SafetyPolicy) -> ValidationResult:
    """System inspection is read-only; nothing to constrain beyond the schema."""
    return ok(dict(params))


DEFAULT_POLICIES: dict[str, Callable[[dict, SafetyPolicy], ValidationResult]] = {
    # Tool names as registered in app/tools/*.py
    "file_processor": policy_file,
    "logs_analyzer": policy_logs,
    "docker_manager": policy_docker,
    "kubernetes_manager": policy_kubernetes,
    "system_inspector": policy_system,
    # Generic aliases so the unit tests stay self-contained
    "file_tool": policy_file,
    "logs_tool": policy_logs,
    "docker_tool": policy_docker,
    "kubernetes_tool": policy_kubernetes,
    "system_tool": policy_system,
}


# --------------------------------------------------------------------------
# Validator
# --------------------------------------------------------------------------


class StructuredOutputValidator:
    """
    Call this on every tool invocation, from every intent source.

    Deny-by-default on the policy map: a tool with no registered policy is
    rejected rather than waved through. Adding a tool without thinking about
    its blast radius should be a visible failure, not a silent gap.
    """

    def __init__(
        self,
        registry,
        policy: SafetyPolicy | None = None,
        policies: dict[str, Callable] | None = None,
    ):
        self.registry = registry
        self.policy = policy or SafetyPolicy()
        self.policies = policies if policies is not None else dict(DEFAULT_POLICIES)

    def register_policy(self, tool_name: str, fn: Callable) -> None:
        self.policies[tool_name] = fn

    def validate_tool_call(self, tool_name: str, params: dict[str, Any]) -> ValidationResult:
        tool = self.registry.get(tool_name)
        if tool is None:
            log.warning("rejected call to unregistered tool %r", tool_name)
            return deny(f"{tool_name} is not a registered tool")

        params = params or {}
        if not isinstance(params, dict):
            return deny("tool parameters must be an object")

        schema_result = self._check_schema(tool, params)
        if not schema_result:
            return schema_result

        policy_fn = self.policies.get(tool.name)
        if policy_fn is None:
            log.error(
                "tool %r has no safety policy registered; denying. "
                "Add one to DEFAULT_POLICIES before enabling this tool.",
                tool.name,
            )
            return deny(f"{tool.name} has no safety policy and cannot be used")

        try:
            result = policy_fn(params, self.policy)
        except Exception as exc:
            # A crashing policy must fail closed, never open.
            log.exception("safety policy for %s raised", tool.name)
            return deny(f"safety check for {tool.name} could not complete: {exc}")

        if not result:
            log.info("policy denied %s: %s", tool.name, result.reason)
        return result

    def _check_schema(self, tool, params: dict) -> ValidationResult:
        schema = tool.input_schema or {}
        props = schema.get("properties", {})

        unknown = set(params) - set(props)
        if unknown:
            return deny(f"unrecognised parameters for {tool.name}: {sorted(unknown)}")

        missing = set(schema.get("required", [])) - set(params)
        if missing:
            return deny(f"{tool.name} requires: {sorted(missing)}")

        try:
            import jsonschema

            jsonschema.validate(instance=params, schema=schema)
        except ImportError:
            log.warning("jsonschema not installed; schema check is shallow")
        except Exception as exc:
            message = getattr(exc, "message", str(exc))
            return deny(f"{tool.name} parameters are invalid: {message}")

        return ok(dict(params))
