"""
Tests for the declarative policy ruleset loader.

These are the tests that back requirement #2 ("fail closed, everywhere")
and #3 ("rules must not be arbitrary code") at the loader level: a bad
ruleset must never quietly degrade to a permissive default or to the old
hardcoded Python — it must prevent the application from booting.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from app.safety.policy.loader import RulesetError, load_ruleset
from app.safety.policy.predicates import PREDICATE_REGISTRY


def write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "rules.yaml"
    path.write_text(content)
    return path


# --------------------------------------------------------------------------
# Malformed rulesets
# --------------------------------------------------------------------------


def test_missing_file_rejected(tmp_path):
    with pytest.raises(RulesetError, match="could not read"):
        load_ruleset(tmp_path / "does_not_exist.yaml")


def test_not_valid_yaml_rejected(tmp_path):
    path = write(tmp_path, "groups: [this is: not: valid: yaml")
    with pytest.raises(RulesetError, match="not valid YAML"):
        load_ruleset(path)


def test_top_level_must_be_a_mapping(tmp_path):
    path = write(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(RulesetError, match="mapping"):
        load_ruleset(path)


def test_missing_version_rejected(tmp_path):
    path = write(tmp_path, "groups:\n  g:\n    - id: x\n      predicate: value_type\n      field: a\n      params: {type: string}\n      message: m\n")
    with pytest.raises(RulesetError, match="version"):
        load_ruleset(path)


def test_empty_groups_rejected(tmp_path):
    path = write(tmp_path, 'version: "1.0.0"\ngroups: {}\n')
    with pytest.raises(RulesetError, match="groups"):
        load_ruleset(path)


def test_rule_missing_id_rejected(tmp_path):
    path = write(
        tmp_path,
        textwrap.dedent(
            """
            version: "1.0.0"
            groups:
              g:
                - predicate: value_type
                  field: a
                  params: {type: string}
                  message: m
            """
        ),
    )
    with pytest.raises(RulesetError, match="'id'"):
        load_ruleset(path)


def test_rule_missing_message_rejected(tmp_path):
    path = write(
        tmp_path,
        textwrap.dedent(
            """
            version: "1.0.0"
            groups:
              g:
                - id: x.y
                  predicate: value_type
                  field: a
                  params: {type: string}
            """
        ),
    )
    with pytest.raises(RulesetError, match="'message'"):
        load_ruleset(path)


def test_multi_field_without_mode_rejected(tmp_path):
    """A rule with more than one field has to say how they combine —
    'alias' or 'all' — rather than silently picking one."""
    path = write(
        tmp_path,
        textwrap.dedent(
            """
            version: "1.0.0"
            groups:
              g:
                - id: x.y
                  predicate: regex_match
                  field: [a, b]
                  params: {pattern: ".*"}
                  message: m
            """
        ),
    )
    with pytest.raises(RulesetError, match="mode"):
        load_ruleset(path)


def test_include_of_unknown_group_rejected(tmp_path):
    path = write(
        tmp_path,
        textwrap.dedent(
            """
            version: "1.0.0"
            groups:
              g:
                - include: does_not_exist
                  field: a
                  optional: true
            """
        ),
    )
    with pytest.raises(RulesetError, match="unknown group"):
        load_ruleset(path)


# --------------------------------------------------------------------------
# Deliverable: unknown predicate rejected at LOAD time, not evaluation time
# --------------------------------------------------------------------------


def test_unknown_predicate_rejected_at_load_time(tmp_path):
    path = write(
        tmp_path,
        textwrap.dedent(
            """
            version: "1.0.0"
            groups:
              g:
                - id: x.y
                  predicate: this_predicate_does_not_exist
                  field: a
                  message: m
            """
        ),
    )
    # It must not even be possible to construct a Ruleset — load_ruleset
    # itself raises, before anything could be evaluated against a request.
    with pytest.raises(RulesetError, match="unknown predicate"):
        load_ruleset(path)


def test_every_registered_predicate_name_is_stable():
    """Sanity check that the registry isn't accidentally empty (which would
    make the previous test meaningless — anything would look 'unknown')."""
    assert "path_within_root" in PREDICATE_REGISTRY
    assert "value_type" in PREDICATE_REGISTRY
    assert len(PREDICATE_REGISTRY) >= 10


# --------------------------------------------------------------------------
# Ordering: a rule needing a resolved value must come after the rule that
# resolves it, within the same group (including through an include).
# --------------------------------------------------------------------------


def test_resolution_order_violation_rejected(tmp_path):
    path = write(
        tmp_path,
        textwrap.dedent(
            """
            version: "1.0.0"
            groups:
              file_containment:
                - id: file.path.under_size_limit
                  predicate: path_under_size_limit
                  field: path
                  params: {max_bytes: 10}
                  message: too big
                - id: file.path.within_root
                  predicate: path_within_root
                  field: path
                  params: {roots: ["/tmp"]}
                  message: outside
            """
        ),
    )
    with pytest.raises(RulesetError, match="needs a resolving rule"):
        load_ruleset(path)


def test_resolution_order_correct_is_accepted(tmp_path):
    path = write(
        tmp_path,
        textwrap.dedent(
            """
            version: "1.0.0"
            groups:
              file_containment:
                - id: file.path.within_root
                  predicate: path_within_root
                  field: path
                  params: {roots: ["/tmp"]}
                  message: outside
                - id: file.path.under_size_limit
                  predicate: path_under_size_limit
                  field: path
                  params: {max_bytes: 10}
                  message: too big
            """
        ),
    )
    rs = load_ruleset(path)
    assert len(rs.group("file_containment")) == 2


def test_resolution_order_checked_through_include(tmp_path):
    """The dependency also has to hold when the resolving rule is reached
    via `include`, not written directly in the same group."""
    path = write(
        tmp_path,
        textwrap.dedent(
            """
            version: "1.0.0"
            groups:
              resolver:
                - id: r.within_root
                  predicate: path_within_root
                  field: path
                  params: {roots: ["/tmp"]}
                  message: outside
              consumer:
                - id: c.under_size_limit
                  predicate: path_under_size_limit
                  field: path
                  params: {max_bytes: 10}
                  message: too big
                - include: resolver
            """
        ),
    )
    with pytest.raises(RulesetError, match="needs a resolving rule"):
        load_ruleset(path)


# --------------------------------------------------------------------------
# Content hash / version
# --------------------------------------------------------------------------


def test_content_hash_changes_when_the_file_changes(tmp_path):
    base = textwrap.dedent(
        """
        version: "1.0.0"
        groups:
          g:
            - id: x.y
              predicate: no_null_byte
              field: a
              message: m
        """
    )
    path = write(tmp_path, base)
    rs1 = load_ruleset(path)

    path.write_text(base + "\n# a comment changes the bytes, not the logic\n")
    rs2 = load_ruleset(path)

    assert rs1.content_hash != rs2.content_hash
    assert rs1.version == rs2.version == "1.0.0"


# --------------------------------------------------------------------------
# Boot failure: importing structured_validator against a broken ruleset
# must fail the whole import, not degrade quietly. Run in a subprocess so
# it doesn't poison this test session's already-imported module.
# --------------------------------------------------------------------------


def test_broken_ruleset_prevents_the_application_from_booting():
    """
    The real end-to-end claim: a broken `rules.yaml` on disk must prevent
    `import app.safety.structured_validator` from succeeding, in a fresh
    process — exactly what happens when the application starts.

    This has to run against the *real* file at its *real* path: merely
    importing anything under `app.safety.policy` first imports the
    `app.safety` package, whose `__init__.py` imports `guardrails`, which
    imports `structured_validator`, which calls `load_ruleset()` with its
    bound default — so patching the default *after* an import statement
    already runs too late to affect it. The only way to prove the real boot
    path fails on a bad file is to put a bad file at the real path, in a
    fresh subprocess, and restore the original afterward no matter what.
    """
    backend_dir = Path(__file__).resolve().parents[1]
    real_ruleset = backend_dir / "app" / "safety" / "policy" / "rules.yaml"
    original = real_ruleset.read_text()
    try:
        real_ruleset.write_text(
            "version: \"1.0.0\"\ngroups:\n  g:\n    - id: x\n      predicate: nope\n      field: a\n      message: m\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", "import app.safety.structured_validator; print('IMPORTED SUCCESSFULLY -- THIS IS THE BUG')"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(backend_dir),
        )
    finally:
        real_ruleset.write_text(original)

    assert result.returncode != 0, (
        "importing structured_validator against a broken ruleset must fail "
        f"the process, not succeed. stdout={result.stdout!r} stderr={result.stderr[-500:]!r}"
    )
    assert "IMPORTED SUCCESSFULLY" not in result.stdout
    assert "RulesetError" in result.stderr
