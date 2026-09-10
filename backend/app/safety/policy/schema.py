"""Typed shape of a parsed ruleset. The loader builds these; the engine
evaluates them. Neither trusts data it didn't get through the loader's
validation — these classes are just structure, not enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any

# Distinguishes "no default was configured" from "the default is None" —
# a rule can legitimately want None as a fallback. Shared with loader.py
# (imported, not redefined) — two separate `object()` sentinels compare
# unequal to each other even with the same name, which silently makes
# every rule look like it has a default.
NO_DEFAULT = object()
_NO_DEFAULT = NO_DEFAULT


@dataclass
class RuleSpec:
    id: str | None
    predicate: str | None          # None only for an `include` directive
    include: str | None = None     # name of another group to inline here
    # Field name(s) this rule reads/checks — "fields" (not "field") to avoid
    # shadowing dataclasses.field within this class body.
    fields: list[str] = dataclass_field(default_factory=list)
    mode: str = "single"           # single | alias | all
    optional: bool = False
    default: Any = _NO_DEFAULT
    params: dict[str, Any] = dataclass_field(default_factory=dict)
    message: str = ""
    when_action_in: list[str] | None = None

    @property
    def has_default(self) -> bool:
        return self.default is not _NO_DEFAULT

    @property
    def is_include(self) -> bool:
        return self.include is not None


@dataclass
class Ruleset:
    version: str
    content_hash: str
    groups: dict[str, list[RuleSpec]]

    def group(self, name: str) -> list[RuleSpec]:
        try:
            return self.groups[name]
        except KeyError:
            raise KeyError(f"no such policy group: {name!r}") from None
