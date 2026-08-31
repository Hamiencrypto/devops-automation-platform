#!/usr/bin/env python3
import re

# CORRECT PATH: app/safety/guardrails.py (not backend/app/safety/)
with open('app/safety/guardrails.py', 'r') as f:
    content = f.read()

# Add imports after banned_patterns import
content = content.replace(
    'from app.safety.banned_patterns',
    'from app.safety.banned_patterns\nfrom app.safety.structured_validator import SafetyPolicy, StructuredOutputValidator\nfrom app.mcp.registry import tool_registry'
)

# Add __init__ method
if 'def __init__' not in content:
    content = content.replace(
        'class Guardrails:',
        'class Guardrails:\n    """Evaluates whether a natural-language command is safe to execute."""\n\n    def __init__(self) -> None:\n        self._validator = StructuredOutputValidator(tool_registry, SafetyPolicy())'
    )

# Update check method signature
content = re.sub(
    r'def check\(\s*self,\s*command: str,\s*intent: IntentResult,\s*confirm_destructive: bool = False,\s*\) -> SafetyCheck:',
    'def check(\n        self,\n        command: str,\n        intent: IntentResult,\n        confirm_destructive: bool = False,\n        tool_name: str | None = None,\n    ) -> SafetyCheck:',
    content
)

# Add structured validation block after low confidence warning
lines = content.split('\n')
new_lines = []
inserted = False
for line in lines:
    new_lines.append(line)
    if 'low-confidence' in line and not inserted:
        new_lines.append('')
        new_lines.append('        # 3b. Structured parameter validation.')
        new_lines.append('        # This runs on the resolved tool call, not the raw sentence')
        new_lines.append('        if tool_name:')
        new_lines.append('            result = self._validator.validate_tool_call(tool_name, intent.entities or {})')
        new_lines.append('            if not result:')
        new_lines.append('                return SafetyCheck(')
        new_lines.append('                    allowed=False,')
        new_lines.append('                    reason=result.reason,')
        new_lines.append('                    warnings=warnings,')
        new_lines.append('                )')
        new_lines.append('            # Use the normalised params downstream')
        new_lines.append('            intent.entities = result.params')
        inserted = True

content = '\n'.join(new_lines)

with open('app/safety/guardrails.py', 'w') as f:
    f.write(content)

print('✅ guardrails.py updated')
