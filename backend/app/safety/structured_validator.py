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

Layer 2 used to be hand-written Python per tool (`policy_docker`,
`policy_kubernetes`, ...). It's now a declarative ruleset
(`app/safety/policy/rules.yaml`) walked by a fixed interpreter
(`app/safety/policy/engine.py`) — see that file's header comment for exactly
what "declarative" does and doesn't mean here before assuming every number
in this module moved into the YAML; it didn't, deliberately.

The ruleset is loaded once, at import time, below. A malformed file, an
unknown predicate name, or a rule ordered before the resolving rule it
depends on all raise here — which means the application fails to start
rather than serving requests against a broken or absent policy. There is no
permissive fallback, and no fallback to the old hardcoded Python.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from app.safety.policy import EvaluationOutcome, PolicyEngine, load_ruleset

log = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    valid: bool
    reason: str = ""
    # Params after normalisation (e.g. resolved paths). Callers should execute
    # with these, not with the originals, so the checked value is the used value.
    params: dict[str, Any] | None = None
    # Attribution — populated only for a Layer-2 (ruleset) decision, never for
    # a Layer-1 schema failure or a "tool not registered" denial, since those
    # aren't rule evaluations. `rule_id` is set only on a denial: no single
    # rule "approves" an allow, so it stays None there.
    rule_id: str | None = None
    ruleset_version: str | None = None
    ruleset_hash: str | None = None

    def __bool__(self) -> bool:
        return self.valid


def ok(params: dict[str, Any]) -> ValidationResult:
    return ValidationResult(True, params=params)


def deny(reason: str) -> ValidationResult:
    return ValidationResult(False, reason=reason)


def _from_outcome(outcome: EvaluationOutcome) -> ValidationResult:
    if outcome.ok:
        return ValidationResult(
            True,
            params=dict(outcome.context),
            ruleset_version=outcome.ruleset_version,
            ruleset_hash=outcome.ruleset_hash,
        )
    return ValidationResult(
        False,
        reason=outcome.reason,
        rule_id=outcome.rule_id,
        ruleset_version=outcome.ruleset_version,
        ruleset_hash=outcome.ruleset_hash,
    )


# --------------------------------------------------------------------------
# Policy configuration
# --------------------------------------------------------------------------


@dataclass
class SafetyPolicy:
    """
    Operational limits. Sourced from config so they differ per environment —
    a staging deployment can be looser than production without a code change.

    Unchanged by the move to a declarative ruleset: this remains the runtime
    *parameter* object. Rules reference these fields by name
    (`{from_policy: field_name}` in rules.yaml); the ruleset governs which
    checks run, in what order, and with what message — not these values.
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
# Ruleset — loaded once, at import time. A bad ruleset must fail the boot.
# --------------------------------------------------------------------------

RULESET = load_ruleset()
ENGINE = PolicyEngine(RULESET)

log.info(
    "loaded safety policy ruleset version=%s hash=%s groups=%s",
    RULESET.version, RULESET.content_hash[:12], sorted(RULESET.groups),
)


# --------------------------------------------------------------------------
# Shared checks — thin wrappers over the engine, kept as standalone
# functions because tests (and, for check_path, other tool code) call them
# directly with just a raw value and a SafetyPolicy.
# --------------------------------------------------------------------------


def check_path(raw: str, policy: SafetyPolicy) -> ValidationResult:
    """Path containment: resolve first, compare second — see rules.yaml's
    `file_containment` group and `path_within_root` in policy/predicates.py
    for what that actually does and why order matters there."""
    outcome = ENGINE.evaluate_group("file_containment", {"path": raw}, policy)
    return _from_outcome(outcome)


def check_port(value: Any, policy: SafetyPolicy) -> ValidationResult:
    outcome = ENGINE.evaluate_group("port_check", {"port": value}, policy)
    return _from_outcome(outcome)


# --------------------------------------------------------------------------
# Per-tool policies — thin wrappers, same signature and behaviour as before
# --------------------------------------------------------------------------


def policy_file(params: dict, policy: SafetyPolicy) -> ValidationResult:
    result = check_path(params.get("path", ""), policy)
    if not result:
        return result
    return ValidationResult(
        True,
        params={**params, "path": result.params["path"]},
        ruleset_version=result.ruleset_version,
        ruleset_hash=result.ruleset_hash,
    )


def policy_logs(params: dict, policy: SafetyPolicy) -> ValidationResult:
    """Log analysis reads arbitrary files, so it gets the same containment."""
    return policy_file(params, policy)


def policy_docker(params: dict, policy: SafetyPolicy) -> ValidationResult:
    outcome = ENGINE.evaluate_group("docker_policy", params, policy)
    return _from_outcome(outcome)


def policy_kubernetes(params: dict, policy: SafetyPolicy) -> ValidationResult:
    outcome = ENGINE.evaluate_group("kubernetes_policy", params, policy)
    return _from_outcome(outcome)


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
            log.info("policy denied %s: %s (rule=%s)", tool.name, result.reason, result.rule_id)
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
