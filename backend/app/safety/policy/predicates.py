"""
The fixed predicate vocabulary Layer-2 rules are allowed to reference.

A rule in the ruleset names one of these by string and supplies parameters;
it cannot supply code. Everything that actually touches the filesystem or
does anything non-trivial lives here, in Python, reviewed the normal way —
the ruleset can only select and parametrise it.

Two small pieces of per-predicate metadata matter to the loader
(`loader.py`), not just the evaluator:

  REBINDS       predicates whose successful result replaces the field's
                value for every later rule in the same group (today, only
                path resolution: `..`-collapsing and symlink-following mean
                every check after it must see the resolved path, not the
                raw string).
  NEEDS_RESOLVED  predicates that are only correct if the field has already
                been through a REBINDS predicate in this group — e.g.
                checking a file's size assumes the path has been resolved;
                stat-ing a traversal string is meaningless.

A ruleset that orders a NEEDS_RESOLVED rule before the REBINDS rule it
depends on is wrong in a way that's easy to introduce (drag one line above
another) and easy to miss in review. The loader rejects it at boot instead
of trusting rule order to be checked by eye every time — see
`loader.py::_check_resolution_order`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class PredicateOutcome:
    passed: bool
    # If this predicate rebinds its field (see REBINDS below), the new value
    # for the shared evaluation context. Ignored unless passed and the
    # predicate is registered as a rebinder.
    rebind: Any = None
    # Values available to the rule's message template, e.g. {"field": "privileged"}
    # for "{field} is not permitted...". Deliberately never includes anything
    # filesystem- or policy-internal by default — a predicate has to put a
    # value here on purpose for it to reach the user-facing message.
    format_kwargs: dict[str, Any] = field(default_factory=dict)


PredicateFn = Callable[[Any, dict[str, Any], Any], PredicateOutcome]

PREDICATE_REGISTRY: dict[str, PredicateFn] = {}
REBINDS: set[str] = set()
NEEDS_RESOLVED: set[str] = set()


def predicate(name: str, *, rebinds: bool = False, needs_resolved: bool = False):
    """Registers a function under `name` and records its resolution-order
    metadata for the loader's ordering check."""

    def decorator(fn: PredicateFn) -> PredicateFn:
        if name in PREDICATE_REGISTRY:
            raise ValueError(f"duplicate predicate registration: {name!r}")
        PREDICATE_REGISTRY[name] = fn
        if rebinds:
            REBINDS.add(name)
        if needs_resolved:
            NEEDS_RESOLVED.add(name)
        return fn

    return decorator


# --------------------------------------------------------------------------
# Generic predicates — no filesystem access, no non-trivial state
# --------------------------------------------------------------------------


@predicate("value_type")
def _value_type(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    expected = params["type"]
    if expected == "integer":
        # bool is a subclass of int in Python; both existing bool-guards
        # (ports, replicas) exist because of exactly this trap.
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "string":
        ok = isinstance(value, str)
        if ok and "min_length" in params:
            ok = len(value) >= params["min_length"]
    else:
        raise ValueError(f"value_type: unsupported type {expected!r}")
    return PredicateOutcome(ok)


@predicate("no_null_byte")
def _no_null_byte(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    return PredicateOutcome(isinstance(value, str) and "\x00" not in value)


@predicate("regex_match")
def _regex_match(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    if not isinstance(value, str):
        return PredicateOutcome(False)
    return PredicateOutcome(bool(re.match(params["pattern"], value)))


@predicate("value_not_in_set")
def _value_not_in_set(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    return PredicateOutcome(value not in set(params["set"]))


@predicate("integer_range")
def _integer_range(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    ok = params["min"] <= value <= params["max"]
    return PredicateOutcome(ok, format_kwargs={"min": params["min"], "max": params["max"]})


@predicate("integer_min")
def _integer_min(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    return PredicateOutcome(value >= params["min"], format_kwargs={"min": params["min"]})


@predicate("integer_max")
def _integer_max(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    return PredicateOutcome(value <= params["max"], format_kwargs={"max": params["max"]})


@predicate("field_not_equal")
def _field_not_equal(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    return PredicateOutcome(value != params["value"])


@predicate("fields_not_truthy")
def _fields_not_truthy(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    """Operates on the whole params dict (no single target field) — `value`
    here is the tool call's full params, not one field's value."""
    for f in params["fields"]:
        if value.get(f):
            return PredicateOutcome(False, format_kwargs={"field": f})
    return PredicateOutcome(True)


@predicate("list_field_not_containing_substring")
def _list_field_not_containing_substring(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    substring = params["substring"]
    items = value or []
    for item in items:
        if isinstance(item, str) and substring in item:
            return PredicateOutcome(False)
    return PredicateOutcome(True)


# --------------------------------------------------------------------------
# Path predicates — genuinely procedural (filesystem access)
# --------------------------------------------------------------------------


@predicate("path_within_root", rebinds=True)
def _path_within_root(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    """
    Resolve first, compare second. Resolving collapses `..`, follows
    symlinks, and normalises the string, so `../../etc/shadow` and a
    symlink pointing at /etc both fail containment rather than sneaking
    past a prefix match on the unresolved string. This is the one rule in
    the vocabulary that rebinds its field: everything checked after it
    (protected filename, suffix, size) must see the resolved path.
    """
    try:
        resolved = Path(value).resolve(strict=False)
    except (OSError, RuntimeError):
        return PredicateOutcome(False)

    roots = [Path(r).resolve(strict=False) for r in params["roots"]]
    for root in roots:
        try:
            resolved.relative_to(root)
            return PredicateOutcome(True, rebind=str(resolved))
        except ValueError:
            continue
    return PredicateOutcome(False)


@predicate("path_not_directory", needs_resolved=True)
def _path_not_directory(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    p = Path(value)
    return PredicateOutcome(not (p.exists() and p.is_dir()))


@predicate("path_under_size_limit", needs_resolved=True)
def _path_under_size_limit(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    p = Path(value)
    if not p.exists():
        return PredicateOutcome(True)
    max_bytes = params["max_bytes"]
    try:
        size = p.stat().st_size
    except OSError:
        return PredicateOutcome(False)
    return PredicateOutcome(size <= max_bytes, format_kwargs={"max_mb": max_bytes // (1024 * 1024)})


@predicate("path_stem_or_name_not_in_set", needs_resolved=True)
def _path_stem_or_name_not_in_set(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    p = Path(value)
    denied = set(params["names"])
    return PredicateOutcome(p.name.lower() not in denied and p.stem.lower() not in denied)


@predicate("path_suffix_not_in_set", needs_resolved=True)
def _path_suffix_not_in_set(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    p = Path(value)
    return PredicateOutcome(p.suffix.lower() not in set(params["suffixes"]))


# --------------------------------------------------------------------------
# Named, non-generic predicates — the logic is specific enough that forcing
# it through a generic primitive would obscure more than it'd share.
# --------------------------------------------------------------------------


@predicate("container_name_not_protected")
def _container_name_not_protected(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    """
    True if `value` is not (and doesn't embed, e.g. via a compose project
    prefix like `devops-mcp-postgres`) one of the platform's own containers.
    An exact-match check alone is bypassable by varying the name string, so
    a protected name must match as a delimiter-bounded segment, not a raw
    substring (`mcp-postgres-backup` is a different container; `x-mcp-postgres`
    is not).
    """
    for p in params["protected"]:
        if value == p or re.search(rf"(?:^|[-_]){re.escape(p)}(?:[-_]|$)", value):
            return PredicateOutcome(False)
    return PredicateOutcome(True)


@predicate("image_name_not_denied")
def _image_name_not_denied(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    registry_or_name = value.split("/")[0]
    return PredicateOutcome(registry_or_name not in set(params["denied_names"]))


@predicate("image_registry_in_allowlist")
def _image_registry_in_allowlist(value: Any, params: dict, policy: Any) -> PredicateOutcome:
    """
    Only check the registry if the image reference actually names one — a
    bare `nginx:1.25` has no registry to check, and `image.split("/")[0]`
    containing a `.` (as in `evil.example.com/backdoor`) is what
    distinguishes "this first segment is a hostname" from "this is a
    namespace on the default registry".
    """
    if "/" not in value:
        return PredicateOutcome(True)
    first_segment = value.split("/")[0]
    if "." not in first_segment:
        return PredicateOutcome(True)
    allowed = set(params["allowed_registries"])
    return PredicateOutcome(
        first_segment in allowed, format_kwargs={"registries": ", ".join(sorted(allowed))}
    )
