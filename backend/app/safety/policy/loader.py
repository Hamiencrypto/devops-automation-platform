"""
Loads and validates the policy ruleset. This is the boot-time gate: a
malformed file, an unknown predicate name, or a rule that depends on
resolution it can't have yet must all raise here, before the application
starts serving requests. There is no permissive fallback and no fallback to
the old hardcoded Python — see module docstring in `structured_validator.py`
for why.

  Scope note: this makes rule *identity, order, predicate selection, and
  message text* data. The numeric/set values a rule is parametrised with
  (allowed roots, protected containers, replica caps, ...) still come from
  `SafetyPolicy` at evaluation time via `{"from_policy": "field_name"}`
  references — see the ruleset file's own header comment for why, and don't
  describe this loader as making "policy" data without that qualifier.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from app.safety.policy.predicates import NEEDS_RESOLVED, PREDICATE_REGISTRY, REBINDS
from app.safety.policy.schema import NO_DEFAULT, RuleSpec, Ruleset

DEFAULT_RULESET_PATH = Path(__file__).parent / "rules.yaml"

_VALID_MODES = {"single", "alias", "all"}


class RulesetError(Exception):
    """Raised for any malformed, invalid, or unsafe ruleset. Callers must
    let this propagate — it's what turns a bad ruleset into a boot failure
    rather than a silently degraded one."""


def load_ruleset(path: Path | str = DEFAULT_RULESET_PATH) -> Ruleset:
    path = Path(path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise RulesetError(f"could not read ruleset file {path}: {exc}") from exc

    try:
        doc = yaml.safe_load(raw_bytes)
    except yaml.YAMLError as exc:
        raise RulesetError(f"ruleset file {path} is not valid YAML: {exc}") from exc

    if not isinstance(doc, dict):
        raise RulesetError(f"ruleset file {path} must contain a mapping at the top level")

    version = doc.get("version")
    if not isinstance(version, str) or not version.strip():
        raise RulesetError("ruleset must declare a non-empty string 'version'")

    raw_groups = doc.get("groups")
    if not isinstance(raw_groups, dict) or not raw_groups:
        raise RulesetError("ruleset must declare a non-empty 'groups' mapping")

    groups: dict[str, list[RuleSpec]] = {}
    for group_name, raw_rules in raw_groups.items():
        if not isinstance(raw_rules, list) or not raw_rules:
            raise RulesetError(f"group {group_name!r} must be a non-empty list of rules")
        groups[group_name] = [
            _parse_rule(group_name, i, entry) for i, entry in enumerate(raw_rules)
        ]

    # Second pass: `include` targets must exist, and can only be checked
    # once every group has been parsed.
    for group_name, rules in groups.items():
        for rule in rules:
            if rule.is_include and rule.include not in groups:
                raise RulesetError(
                    f"group {group_name!r} includes unknown group {rule.include!r}"
                )

    for group_name, rules in groups.items():
        _check_resolution_order(group_name, rules, groups)

    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    return Ruleset(version=version.strip(), content_hash=content_hash, groups=groups)


def _parse_rule(group_name: str, index: int, entry: Any) -> RuleSpec:
    where = f"group {group_name!r} rule #{index + 1}"
    if not isinstance(entry, dict):
        raise RulesetError(f"{where}: expected a mapping, got {type(entry).__name__}")

    include = entry.get("include")
    if include is not None:
        if not isinstance(include, str):
            raise RulesetError(f"{where}: 'include' must be a string")
        field_raw = entry.get("field")
        return RuleSpec(
            id=None,
            predicate=None,
            include=include,
            fields=_normalise_field(where, field_raw, mode="single"),
            mode="single",
            optional=bool(entry.get("optional", False)),
        )

    rule_id = entry.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise RulesetError(f"{where}: every rule needs a non-empty string 'id'")
    where = f"rule {rule_id!r}"

    predicate_name = entry.get("predicate")
    if not isinstance(predicate_name, str) or not predicate_name.strip():
        raise RulesetError(f"{where}: needs a 'predicate'")
    if predicate_name not in PREDICATE_REGISTRY:
        known = ", ".join(sorted(PREDICATE_REGISTRY))
        raise RulesetError(
            f"{where}: unknown predicate {predicate_name!r}. Registered predicates: {known}"
        )

    field_raw = entry.get("field")
    mode = entry.get("mode", "single")
    if mode not in _VALID_MODES:
        raise RulesetError(f"{where}: 'mode' must be one of {sorted(_VALID_MODES)}, got {mode!r}")
    if isinstance(field_raw, list) and len(field_raw) > 1 and "mode" not in entry:
        raise RulesetError(
            f"{where}: 'field' has multiple entries ({field_raw!r}) but no 'mode' — "
            "specify 'alias' (first one present wins) or 'all' (check every one present)"
        )

    message = entry.get("message", "")
    if not isinstance(message, str) or not message.strip():
        raise RulesetError(f"{where}: needs a non-empty 'message'")

    params = entry.get("params", {})
    if not isinstance(params, dict):
        raise RulesetError(f"{where}: 'params' must be a mapping")

    default = entry.get("default", NO_DEFAULT)

    when = entry.get("when")
    when_action_in = None
    if when is not None:
        if not isinstance(when, dict) or "action_in" not in when:
            raise RulesetError(f"{where}: 'when' currently only supports 'action_in: [...]'")
        when_action_in = list(when["action_in"])

    return RuleSpec(
        id=rule_id,
        predicate=predicate_name,
        fields=_normalise_field(where, field_raw, mode=mode),
        mode=mode,
        optional=bool(entry.get("optional", False)),
        default=default,
        params=params,
        message=message,
        when_action_in=when_action_in,
    )


def _normalise_field(where: str, field_raw: Any, *, mode: str) -> list[str]:
    if field_raw is None:
        return []
    if isinstance(field_raw, str):
        return [field_raw]
    if isinstance(field_raw, list):
        if not all(isinstance(f, str) for f in field_raw):
            raise RulesetError(f"{where}: 'field' list must contain only strings")
        if len(field_raw) > 1 and mode == "single":
            raise RulesetError(
                f"{where}: multiple 'field' entries need mode 'alias' or 'all', not 'single'"
            )
        return field_raw
    raise RulesetError(f"{where}: 'field' must be a string or list of strings")


def _check_resolution_order(
    group_name: str, rules: list[RuleSpec], all_groups: dict[str, list[RuleSpec]]
) -> None:
    """
    A NEEDS_RESOLVED predicate for field X is only correct if a REBINDS
    predicate for field X already ran earlier in the same evaluation
    sequence. `include` is expanded inline for this check — an included
    group's rules run exactly where the include sits.
    """
    resolved_fields: set[str] = set()

    def walk(rule_list: list[RuleSpec], seen_groups: frozenset[str]) -> None:
        for rule in rule_list:
            if rule.is_include:
                if rule.include in seen_groups:
                    raise RulesetError(
                        f"group {group_name!r}: circular include via {rule.include!r}"
                    )
                walk(all_groups[rule.include], seen_groups | {rule.include})
                continue

            for f in rule.fields:
                if rule.predicate in NEEDS_RESOLVED and f not in resolved_fields:
                    raise RulesetError(
                        f"rule {rule.id!r} in group {group_name!r} uses {rule.predicate!r} "
                        f"on field {f!r}, which needs a resolving rule (e.g. path_within_root) "
                        f"earlier in the same group — reorder so the resolving rule runs first"
                    )
                if rule.predicate in REBINDS:
                    resolved_fields.add(f)

    walk(rules, frozenset({group_name}))
