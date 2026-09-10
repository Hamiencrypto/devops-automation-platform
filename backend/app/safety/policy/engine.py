"""
Evaluates a ruleset group against a set of field values.

This is the interpreter requirement #3 talks about: the ruleset selects and
parametrises predicates from `predicates.py`, and this module is the only
thing that actually calls them. Nothing here executes ruleset content as
code — every rule is data walked by a fixed loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.safety.policy.predicates import PREDICATE_REGISTRY
from app.safety.policy.schema import Ruleset, RuleSpec

log = logging.getLogger(__name__)

_NO_VALUE = object()


class _RuleCrashed(Exception):
    """Internal only — carries which rule raised so evaluate_group can
    attribute the resulting denial, then gets converted to a plain
    fail-closed EvaluationOutcome. Never escapes this module."""

    def __init__(self, rule_id: str):
        self.rule_id = rule_id
        super().__init__(rule_id)


@dataclass
class EvaluationOutcome:
    ok: bool
    context: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    rule_id: str | None = None       # only set on denial — no single rule "approves"
    ruleset_version: str | None = None
    ruleset_hash: str | None = None


class PolicyEngine:
    def __init__(self, ruleset: Ruleset):
        self.ruleset = ruleset

    def evaluate_group(self, group_name: str, context: dict[str, Any], policy: Any) -> EvaluationOutcome:
        working = dict(context)
        try:
            failure = self._run(self.ruleset.group(group_name), working, policy)
        except _RuleCrashed as exc:
            # A rule that crashes while evaluating must deny, never allow —
            # same fail-closed contract StructuredOutputValidator already
            # applies one level up for an entire policy function raising.
            # Still attributed: we know exactly which rule blew up.
            log.exception("policy rule %r crashed while evaluating group %r", exc.rule_id, group_name)
            return EvaluationOutcome(
                ok=False,
                reason="safety check for this request could not complete",
                rule_id=exc.rule_id,
                ruleset_version=self.ruleset.version,
                ruleset_hash=self.ruleset.content_hash,
            )
        except Exception:
            # Anything else — a bug in the engine itself, not a predicate —
            # still fails closed, just without a specific rule to blame.
            log.exception("policy engine crashed while evaluating group %r", group_name)
            return EvaluationOutcome(
                ok=False,
                reason="safety check for this request could not complete",
                ruleset_version=self.ruleset.version,
                ruleset_hash=self.ruleset.content_hash,
            )

        if failure is not None:
            rule_id, message = failure
            return EvaluationOutcome(
                ok=False,
                reason=message,
                rule_id=rule_id,
                ruleset_version=self.ruleset.version,
                ruleset_hash=self.ruleset.content_hash,
            )

        return EvaluationOutcome(
            ok=True,
            context=working,
            ruleset_version=self.ruleset.version,
            ruleset_hash=self.ruleset.content_hash,
        )

    # -- internals -----------------------------------------------------

    def _run(
        self, rules: list[RuleSpec], context: dict[str, Any], policy: Any
    ) -> tuple[str, str] | None:
        """Returns (rule_id, message) on the first denial, else None."""
        for rule in rules:
            if rule.is_include:
                sub_value = self._resolve_single(rule, context)
                if sub_value is _NO_VALUE:
                    continue  # optional and absent — skip the whole included group
                failure = self._run(self.ruleset.group(rule.include), context, policy)
                if failure is not None:
                    return failure
                continue

            if rule.when_action_in is not None and context.get("action") not in rule.when_action_in:
                continue

            fn = PREDICATE_REGISTRY[rule.predicate]
            params = self._resolve_params(rule.params, policy)

            if not rule.fields:
                # Whole-params predicate (e.g. fields_not_truthy) — no single
                # field to resolve or rebind.
                outcome = self._call(fn, rule, context, params, policy)
                if not outcome.passed:
                    return rule.id, self._render(rule, outcome.format_kwargs)
                continue

            if rule.mode == "all":
                for f in rule.fields:
                    value = self._resolve_single_field(rule, context, f)
                    if value is _NO_VALUE:
                        continue
                    outcome = self._call(fn, rule, value, params, policy)
                    if not outcome.passed:
                        kwargs = {"field": f, "value": value, **outcome.format_kwargs}
                        return rule.id, self._render(rule, kwargs)
                continue

            # single or alias: resolve to at most one (field, value) pair
            resolved = self._resolve(rule, context)
            if resolved is None:
                continue  # optional and absent
            f, value = resolved
            outcome = self._call(fn, rule, value, params, policy)
            if not outcome.passed:
                kwargs = {"field": f, "value": value, **outcome.format_kwargs}
                return rule.id, self._render(rule, kwargs)
            if outcome.rebind is not None:
                context[f] = outcome.rebind

        return None

    @staticmethod
    def _call(fn, rule: RuleSpec, value: Any, params: dict[str, Any], policy: Any):
        try:
            return fn(value, params, policy)
        except _RuleCrashed:
            raise
        except Exception as exc:
            raise _RuleCrashed(rule.id) from exc

    def _resolve(self, rule: RuleSpec, context: dict[str, Any]) -> tuple[str, Any] | None:
        """single/alias resolution: the first field in `rule.fields` that's
        present (or the rule's default) — None means 'skip, optional'."""
        for f in rule.fields:
            value = self._resolve_single_field(rule, context, f)
            if value is not _NO_VALUE:
                return f, value
        if rule.has_default:
            return rule.fields[0], rule.default
        if rule.optional:
            return None
        # Not optional, no default, absent: a ruleset-authoring bug rather
        # than a real request shape. Fail closed rather than skip.
        raise ValueError(f"rule {rule.id!r}: required field(s) {rule.fields} are absent")

    def _resolve_single(self, rule: RuleSpec, context: dict[str, Any]) -> Any:
        """Presence gate for an `include` directive. Returns `_NO_VALUE` to
        mean 'skip the included group'; any other return means 'run it'."""
        if not rule.fields:
            return None  # no gate configured; always run
        for f in rule.fields:
            if context.get(f) is not None:
                return None  # present -> run
        if rule.optional:
            return _NO_VALUE
        raise ValueError(f"include {rule.include!r}: required field(s) {rule.fields} are absent")

    def _resolve_single_field(self, rule: RuleSpec, context: dict[str, Any], f: str) -> Any:
        value = context.get(f)
        if value is not None:
            return value
        if rule.has_default:
            return rule.default
        return _NO_VALUE

    @staticmethod
    def _resolve_params(params: dict[str, Any], policy: Any) -> dict[str, Any]:
        """Replaces every `{"from_policy": "field_name"}` marker with
        `getattr(policy, field_name)`, evaluated fresh on every call since
        `policy` varies per request (and per test)."""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, dict) and set(v) == {"from_policy"}:
                resolved[k] = getattr(policy, v["from_policy"])
            else:
                resolved[k] = v
        return resolved

    @staticmethod
    def _render(rule: RuleSpec, kwargs: dict[str, Any]) -> str:
        try:
            return rule.message.format(**kwargs)
        except (KeyError, IndexError) as exc:
            # A template referencing a value the predicate never supplied is
            # a ruleset-authoring bug — fail closed with a generic message
            # rather than leak a Python format-error string to the user.
            log.error("rule %r message template is broken: %s", rule.id, exc)
            raise
