"""
"No rule in the shipped ruleset is dead."

The parity suite (test_structured_validator.py) proves the policy denies
known attacks — but it goes through the wrapper functions (policy_docker,
check_path, ...), so a rule that never actually fires because of a plumbing
bug would still let those tests pass: the wrapper still returns ok(), the
test still asserted ok(), nobody notices. That's exactly the shape of a bug
found during this refactor — two same-named `object()` sentinels in
different modules compared unequal, so `has_default` silently answered
"yes" for every rule without an explicit default, and an absent optional
field got a garbage sentinel passed to its predicate instead of being
skipped. Not a crash for most rules — a false permissive, or a right answer
reached the wrong way. It only surfaced by accident, by exercising
realistic input directly against the engine.

This file is the systematic version of that check: it discovers every real
rule ID in the actual, shipped `rules.yaml` (not a hand-maintained list —
if someone adds a rule and forgets to add a case here, the discovery
assertion fails, not silently passes) and, for each one, runs a crafted
input through the *whole* group — not just the one predicate in isolation
— and asserts that exact rule ID is what denies it. Running the whole group
matters: a rule earlier in the sequence crashing (as `docker.volumes.no_
socket_mount` did) surfaces here as a rule_id mismatch, because the crash
attributes to the wrong rule.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from app.safety.structured_validator import ENGINE, RULESET, SafetyPolicy

# --------------------------------------------------------------------------
# Rule count — a raw, hand-maintained pin. If a hand-edit to rules.yaml
# silently drops a rule, this fails before anything smarter gets a chance
# to notice. Deliberately dumb and easy to verify by eye against the file.
# --------------------------------------------------------------------------

EXPECTED_RULE_COUNTS = {
    "file_containment": 7,
    "port_check": 3,
    "docker_policy": 9,  # 8 rules + 1 include
    "kubernetes_policy": 6,
}


def test_group_rule_counts_match_expected():
    actual = {name: len(rules) for name, rules in RULESET.groups.items()}
    assert actual == EXPECTED_RULE_COUNTS, (
        "rules.yaml's rule counts changed. If this was deliberate (added/"
        "removed a rule), update EXPECTED_RULE_COUNTS here *and* make sure "
        "RULE_FIRING_CASES below still covers every real rule ID — that's "
        "the check that actually matters; this one just catches an "
        "accidental drop."
    )


# --------------------------------------------------------------------------
# Fixtures shared by the firing cases below
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def safe_root():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "safe_data"
        root.mkdir()
        (root / "app.log").write_text("hello\n")
        (root / "big.log").write_text("x" * 5000)
        yield root


@pytest.fixture(scope="module")
def base_policy(safe_root):
    return SafetyPolicy(allowed_file_roots=(str(safe_root),), max_file_bytes=1024)


def test_every_real_rule_can_fire(safe_root, base_policy):
    """
    For every real rule ID (skipping `include` directives, which aren't
    rules themselves), a crafted input that makes every earlier rule in its
    group pass and that specific rule's predicate fail — run against the
    real, shipped ruleset through the real engine, no wrapper functions.
    """
    policy_denied_image = replace(base_policy, denied_image_names=frozenset({"nginx"}))

    # Baselines: pass every rule in the group by default.
    docker_baseline = {"action": "deploy", "image": "nginx:1.25"}
    k8s_baseline = {"deployment": "web"}

    # rule_id -> (group, params, policy)
    cases: dict[str, tuple[str, dict, SafetyPolicy]] = {
        # -- file_containment ------------------------------------------
        "file.path.required": ("file_containment", {"path": ""}, base_policy),
        "file.path.no_null_byte": (
            "file_containment", {"path": f"{safe_root}/app.log\x00"}, base_policy,
        ),
        "file.path.within_root": ("file_containment", {"path": "/etc/shadow"}, base_policy),
        "file.path.not_protected_name": (
            "file_containment", {"path": str(safe_root / "shadow")}, base_policy,
        ),
        "file.path.not_denied_suffix": (
            "file_containment", {"path": str(safe_root / "server.pem")}, base_policy,
        ),
        "file.path.not_directory": ("file_containment", {"path": str(safe_root)}, base_policy),
        "file.path.under_size_limit": (
            "file_containment", {"path": str(safe_root / "big.log")}, base_policy,
        ),
        # -- port_check ---------------------------------------------------
        "port.type": ("port_check", {"port": True}, base_policy),
        "port.range": ("port_check", {"port": 22}, base_policy),
        "port.not_reserved": ("port_check", {"port": 5432}, base_policy),
        # -- docker_policy --------------------------------------------------
        "docker.flags.no_escape": (
            "docker_policy", {**docker_baseline, "privileged": True}, base_policy,
        ),
        "docker.network.no_host_mode": (
            "docker_policy", {**docker_baseline, "network_mode": "host"}, base_policy,
        ),
        "docker.volumes.no_socket_mount": (
            "docker_policy",
            {**docker_baseline, "volumes": ["/var/run/docker.sock:/var/run/docker.sock"]},
            base_policy,
        ),
        "docker.name.valid_format": (
            "docker_policy", {**docker_baseline, "name": "bad name!"}, base_policy,
        ),
        "docker.name.not_protected": (
            "docker_policy", {**docker_baseline, "name": "mcp-postgres"}, base_policy,
        ),
        "docker.image.valid_format": (
            "docker_policy", {**docker_baseline, "image": "not a valid ref!!"}, base_policy,
        ),
        # image_name_not_denied checks image.split("/")[0] against the
        # denylist — inherited unchanged from the original policy_docker.
        # For a bare reference with no "/", that includes the tag, so a
        # denylist of "nginx" does NOT match "nginx:1.25", only "nginx"
        # untagged. Not a bug introduced here (verified against the
        # pre-refactor code) and out of scope to change — noted so the next
        # reader isn't surprised, and so this test exercises what the rule
        # actually does rather than what it looks like it should do.
        "docker.image.not_denied_name": (
            "docker_policy", {"action": "deploy", "image": "nginx"}, policy_denied_image,
        ),
        "docker.image.registry_allowed": (
            "docker_policy",
            {**docker_baseline, "image": "evil.example.com/backdoor:latest"},
            base_policy,
        ),
        # -- kubernetes_policy ----------------------------------------------
        "k8s.namespace.valid_format": (
            "kubernetes_policy", {**k8s_baseline, "namespace": "BAD_NS!"}, base_policy,
        ),
        "k8s.namespace.not_protected": (
            "kubernetes_policy", {**k8s_baseline, "namespace": "kube-system"}, base_policy,
        ),
        "k8s.names.valid_format": (
            "kubernetes_policy", {"deployment": "Bad_Name!"}, base_policy,
        ),
        "k8s.replicas.type": (
            "kubernetes_policy", {**k8s_baseline, "replicas": True}, base_policy,
        ),
        "k8s.replicas.not_negative": (
            "kubernetes_policy", {**k8s_baseline, "replicas": -5}, base_policy,
        ),
        "k8s.replicas.cap": (
            "kubernetes_policy", {**k8s_baseline, "replicas": 99999}, base_policy,
        ),
    }

    real_ids = {
        rule.id
        for rules in RULESET.groups.values()
        for rule in rules
        if rule.id is not None
    }

    missing = real_ids - set(cases)
    extra = set(cases) - real_ids
    assert not missing, f"no firing case registered for rule(s): {sorted(missing)}"
    assert not extra, f"firing case(s) registered for rule(s) that no longer exist: {sorted(extra)}"

    failures = []
    for rule_id, (group, params, policy) in cases.items():
        outcome = ENGINE.evaluate_group(group, params, policy)
        if outcome.ok:
            failures.append(f"{rule_id}: expected a denial, got an allow")
        elif outcome.rule_id != rule_id:
            failures.append(
                f"{rule_id}: expected this rule to fire, but {outcome.rule_id!r} fired "
                f"instead (reason: {outcome.reason!r}) — a rule earlier in the sequence "
                f"is wrong, or this rule is unreachable"
            )

    assert not failures, "dead or misattributed rule(s):\n" + "\n".join(failures)


def test_baseline_params_pass_every_group_cleanly(safe_root, base_policy):
    """
    Sanity check on the coverage test's own baselines: if the "everything
    passes" baseline for a group doesn't actually pass, every firing case
    built on top of it is testing nothing meaningful.
    """
    out = ENGINE.evaluate_group("file_containment", {"path": str(safe_root / "app.log")}, base_policy)
    assert out.ok, out.reason

    out = ENGINE.evaluate_group("port_check", {"port": 8080}, base_policy)
    assert out.ok, out.reason

    out = ENGINE.evaluate_group("docker_policy", {"action": "deploy", "image": "nginx:1.25"}, base_policy)
    assert out.ok, out.reason

    out = ENGINE.evaluate_group("kubernetes_policy", {"deployment": "web"}, base_policy)
    assert out.ok, out.reason
