"""
Tests for the structured output validator.

These are the tests to run live in a viva. Each one names a concrete attack
and shows it terminating at the policy layer.
"""

import os
import tempfile
from pathlib import Path

import pytest

from app.safety.structured_validator import (
    SafetyPolicy,
    StructuredOutputValidator,
    check_path,
    check_port,
    policy_docker,
    policy_kubernetes,
)


class FakeTool:
    def __init__(self, name, schema):
        self.name = name
        self.description = f"fake {name}"
        self.intents = (f"{name}.act",)
        self.input_schema = schema


class FakeRegistry:
    def __init__(self, tools):
        self._tools = {t.name: t for t in tools}

    def get(self, name):
        return self._tools.get(name)

    def all(self):
        return list(self._tools.values())


@pytest.fixture
def safe_root():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "safe_data"
        root.mkdir()
        (root / "app.log").write_text("error: something\nwarning: else\n")
        yield root


@pytest.fixture
def policy(safe_root):
    return SafetyPolicy(allowed_file_roots=(str(safe_root),), max_file_bytes=1024)


@pytest.fixture
def registry():
    return FakeRegistry(
        [
            FakeTool(
                "file_tool",
                {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            ),
            FakeTool(
                "docker_tool",
                {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["deploy", "list", "stop"]},
                        "image": {"type": "string"},
                        "name": {"type": "string"},
                        "port": {"type": "integer"},
                        "privileged": {"type": "boolean"},
                        "network_mode": {"type": "string"},
                        "volumes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["action"],
                },
            ),
            FakeTool(
                "kubernetes_tool",
                {
                    "type": "object",
                    "properties": {
                        "deployment": {"type": "string"},
                        "namespace": {"type": "string"},
                        "replicas": {"type": "integer"},
                    },
                    "required": ["deployment"],
                },
            ),
            FakeTool("orphan_tool", {"type": "object", "properties": {}}),
        ]
    )


@pytest.fixture
def validator(registry, policy):
    return StructuredOutputValidator(registry, policy)


# --------------------------------------------------------------------------
# Registry and schema
# --------------------------------------------------------------------------


def test_unregistered_tool_denied(validator):
    result = validator.validate_tool_call("shell_tool", {"cmd": "id"})
    assert not result
    assert "not a registered tool" in result.reason


def test_unknown_parameter_denied(validator, safe_root):
    result = validator.validate_tool_call(
        "file_tool", {"path": str(safe_root / "app.log"), "sudo": True}
    )
    assert not result
    assert "unrecognised parameters" in result.reason


def test_missing_required_denied(validator):
    result = validator.validate_tool_call("docker_tool", {"image": "nginx"})
    assert not result
    assert "requires" in result.reason


def test_enum_violation_denied(validator):
    assert not validator.validate_tool_call("docker_tool", {"action": "nuke"})


def test_tool_without_policy_is_denied_not_allowed(validator):
    """Deny by default. A new tool must opt in to a policy explicitly."""
    result = validator.validate_tool_call("orphan_tool", {})
    assert not result
    assert "no safety policy" in result.reason


# --------------------------------------------------------------------------
# Path containment
# --------------------------------------------------------------------------


def test_file_inside_root_allowed(validator, safe_root):
    target = safe_root / "app.log"
    result = validator.validate_tool_call("file_tool", {"path": str(target)})
    assert result
    # Compare against the resolved form: on macOS /var is a symlink to
    # /private/var, so the validator's resolved path differs from the literal
    # string it was given. That normalisation is the point of the check.
    assert result.params["path"] == str(target.resolve())


@pytest.mark.parametrize(
    "attack",
    [
        "/etc/shadow",
        "/etc/passwd",
        "/root/.ssh/id_rsa",
        "/proc/self/environ",
        "../../../../etc/shadow",
    ],
)
def test_paths_outside_root_denied(validator, safe_root, attack):
    path = attack if attack.startswith("/") else str(safe_root / attack)
    result = validator.validate_tool_call("file_tool", {"path": path})
    assert not result
    assert "outside the permitted directories" in result.reason


def test_traversal_through_the_allowed_root_denied(validator, safe_root):
    """The classic: start legitimately, then climb out with `..`."""
    result = validator.validate_tool_call(
        "file_tool", {"path": f"{safe_root}/../../../../etc/shadow"}
    )
    assert not result


def test_symlink_escape_denied(validator, safe_root):
    """
    A prefix check on the raw string would pass this, because the string does
    start with the allowed root. Resolving first is what catches it.
    """
    link = safe_root / "innocent.log"
    try:
        os.symlink("/etc/passwd", link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    result = validator.validate_tool_call("file_tool", {"path": str(link)})
    assert not result


def test_null_byte_denied(validator, safe_root):
    result = validator.validate_tool_call(
        "file_tool", {"path": f"{safe_root}/app.log\x00.txt"}
    )
    assert not result


def test_protected_filename_denied_even_inside_root(policy, safe_root):
    (safe_root / ".env").write_text("LLM_API_KEY=sk-real-key")
    result = check_path(str(safe_root / ".env"), policy)
    assert not result
    assert "protected list" in result.reason


def test_private_key_suffix_denied(policy, safe_root):
    (safe_root / "server.pem").write_text("-----BEGIN PRIVATE KEY-----")
    assert not check_path(str(safe_root / "server.pem"), policy)


def test_oversized_file_denied(policy, safe_root):
    (safe_root / "big.log").write_text("x" * 5000)  # policy cap is 1024
    result = check_path(str(safe_root / "big.log"), policy)
    assert not result
    assert "exceeds" in result.reason


def test_directory_denied(policy, safe_root):
    assert not check_path(str(safe_root), policy)


def test_denial_does_not_leak_resolved_path(validator, safe_root):
    """Error messages must not confirm filesystem layout to a prober."""
    result = validator.validate_tool_call("file_tool", {"path": "/etc/shadow"})
    assert "/etc/shadow" not in result.reason


# --------------------------------------------------------------------------
# Docker policy
# --------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["privileged", "cap_add", "devices", "pid_mode"])
def test_container_escape_flags_denied(policy, flag):
    result = policy_docker({"action": "deploy", "image": "nginx", flag: True}, policy)
    assert not result
    assert flag in result.reason


def test_host_networking_denied(policy):
    result = policy_docker(
        {"action": "deploy", "image": "nginx", "network_mode": "host"}, policy
    )
    assert not result


def test_docker_socket_mount_denied(policy):
    result = policy_docker(
        {
            "action": "deploy",
            "image": "nginx",
            "volumes": ["/var/run/docker.sock:/var/run/docker.sock"],
        },
        policy,
    )
    assert not result
    assert "Docker socket" in result.reason


def test_platform_container_is_protected(policy):
    result = policy_docker({"action": "stop", "name": "devops-mcp-postgres"}, policy)
    assert not result
    assert "platform itself" in result.reason


def test_container_name_injection_denied(policy):
    result = policy_docker({"action": "stop", "name": "nginx; rm -rf /"}, policy)
    assert not result


def test_privileged_port_denied(policy):
    result = check_port(22, policy)
    assert not result
    assert "privileged ports" in result.reason


def test_platform_port_denied(policy):
    assert not check_port(5432, policy)


def test_valid_port_allowed(policy):
    assert check_port(8080, policy)


def test_boolean_is_not_a_valid_port(policy):
    """`True` is an int in Python. Without the bool guard this would pass."""
    assert not check_port(True, policy)


def test_untrusted_registry_denied(policy):
    result = policy_docker(
        {"action": "deploy", "image": "evil.example.com/backdoor:latest"}, policy
    )
    assert not result
    assert "may only come from" in result.reason


def test_plain_image_name_allowed(policy):
    assert policy_docker({"action": "deploy", "image": "nginx:1.25"}, policy)


# --------------------------------------------------------------------------
# Kubernetes policy
# --------------------------------------------------------------------------


@pytest.mark.parametrize("ns", ["kube-system", "kube-public", "istio-system"])
def test_protected_namespace_denied(policy, ns):
    result = policy_kubernetes({"deployment": "web", "namespace": ns}, policy)
    assert not result
    assert "read-only here" in result.reason


def test_replica_cap_enforced(policy):
    result = policy_kubernetes({"deployment": "web", "replicas": 5000}, policy)
    assert not result
    assert "cluster" in result.reason


def test_negative_replicas_denied(policy):
    assert not policy_kubernetes({"deployment": "web", "replicas": -1}, policy)


def test_scale_to_zero_allowed(policy):
    """Zero is a legitimate scale target and must not be confused with negative."""
    assert policy_kubernetes({"deployment": "web", "replicas": 0}, policy)


def test_invalid_k8s_name_denied(policy):
    assert not policy_kubernetes({"deployment": "Web_Service!"}, policy)


# --------------------------------------------------------------------------
# Fail-closed behaviour
# --------------------------------------------------------------------------


def test_crashing_policy_fails_closed(registry, policy):
    def exploding(params, pol):
        raise RuntimeError("policy bug")

    validator = StructuredOutputValidator(
        registry, policy, policies={"file_tool": exploding}
    )
    result = validator.validate_tool_call("file_tool", {"path": "/tmp/x"})
    assert not result, "a policy that raises must deny, never allow"


def test_non_dict_params_denied(validator):
    assert not validator.validate_tool_call("file_tool", "path=/etc/shadow")
