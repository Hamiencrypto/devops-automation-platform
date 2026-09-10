"""
Architecture test: a tool must never be executed without being validated
first, in the same function that executes it.

This exists because that invariant was broken once already:
`app/api/containers.py` called `tool.execute(params)` directly, with no
`guardrails.validate_params()` (or the `resolve_and_validate()` chokepoint
that wraps it) anywhere in the same function — silently bypassing the
protected-container policy. A code review or a convention doesn't stop that
from happening again the next time someone adds a new call site by copying
an old pattern; this test does; it fails the moment a `tool.execute(...)`
call appears in a function that never validated anything.

Deliberately narrow and heuristic rather than a full dataflow analysis: it
only looks at calls shaped like `<name>.execute(...)` where `<name>` is the
`tool` variable name this codebase actually uses everywhere a resolved
MCPTool is executed (see app/services/tool_execution.py,
app/services/executor.py, app/api/containers.py). That keeps it simple
enough to read and trust, at the cost of not catching a call site that binds
the tool to some other variable name — an acceptable trade for an FYP-scale
codebase where the convention is consistent today.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"

# A call counts as "this function validated before executing" if its name
# contains "validate" — substring, not an exact set, on purpose: it covers
# `guardrails.validate_params`, `resolve_and_validate`, `validate_tool_call`,
# and any future wrapper (e.g. containers.py's `_resolve_and_validate`)
# without this test needing to be updated every time one is added. The
# trade-off is a false negative if someone names an unrelated call
# `...validate...` in the same function — acceptable; the failure mode this
# test exists for is a call site with *no* validation call at all.
VALIDATING_MARKER = "validate"

# The tool base class defines `execute` itself — not a call site.
EXEMPT_FILES = {APP_DIR / "tools" / "base.py"}


def _iter_tool_files():
    for path in APP_DIR.rglob("*.py"):
        if path in EXEMPT_FILES:
            continue
        yield path


def _call_name(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def _is_tool_execute_call(node: ast.Call) -> bool:
    f = node.func
    return (
        isinstance(f, ast.Attribute)
        and f.attr == "execute"
        and isinstance(f.value, ast.Name)
        and f.value.id == "tool"
    )


def _functions_in(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def test_every_tool_execute_call_is_validated_in_the_same_function():
    offenders = []

    for path in _iter_tool_files():
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue

        for func in _functions_in(tree):
            calls = [n for n in ast.walk(func) if isinstance(n, ast.Call)]
            execute_calls = [n for n in calls if _is_tool_execute_call(n)]
            if not execute_calls:
                continue
            validated = any(
                name and VALIDATING_MARKER in name for name in (_call_name(c) for c in calls)
            )
            if not validated:
                offenders.append(f"{path.relative_to(APP_DIR.parent)}:{func.lineno} ({func.name})")

    assert not offenders, (
        "tool.execute() called without a validate_params/resolve_and_validate/"
        "validate_tool_call call in the same function — this is exactly the "
        "bypass that shipped in app/api/containers.py once already:\n"
        + "\n".join(offenders)
    )
