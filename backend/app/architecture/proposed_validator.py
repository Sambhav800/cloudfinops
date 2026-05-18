"""
Proposed architecture Mermaid output validator.

Validates AI-generated Mermaid strings before they reach the frontend.
Catches injection, oversized output, and broken syntax.
"""

import re
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_MERMAID_LENGTH = 50_000        # 50 KB max for a single diagram
MAX_LINE_COUNT = 2000              # max lines in output

# Mermaid must start with one of these directives
VALID_STARTS = ("flowchart", "graph", "flowchart TD", "flowchart LR",
                "graph TD", "graph LR", "graph TB", "graph BT")

# Directives that could inject behavior or break rendering
FORBIDDEN_PATTERNS = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"<\s*iframe", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),       # onclick=, onerror=, etc.
    re.compile(r"click\s+\S+\s+\"", re.IGNORECASE), # Mermaid click callback
    re.compile(r"%%\{init:", re.IGNORECASE),         # Mermaid init directive (can inject config)
]


# ---------------------------------------------------------------------------
# Public: validate
# ---------------------------------------------------------------------------

def validate_proposed_mermaid(mermaid: str) -> Tuple[bool, List[str]]:
    """
    Validate AI-generated Mermaid code.

    Returns:
        (is_valid, errors): Tuple of validity flag and list of error messages.
    """
    errors: List[str] = []

    if not mermaid or not mermaid.strip():
        errors.append("Mermaid output is empty")
        return False, errors

    stripped = mermaid.strip()

    # 1. Length check
    if len(stripped) > MAX_MERMAID_LENGTH:
        errors.append(
            f"Mermaid output exceeds max length: {len(stripped)} > {MAX_MERMAID_LENGTH}"
        )

    # 2. Line count check
    lines = stripped.split("\n")
    if len(lines) > MAX_LINE_COUNT:
        errors.append(
            f"Mermaid output exceeds max line count: {len(lines)} > {MAX_LINE_COUNT}"
        )

    # 3. Must start with valid Mermaid directive
    first_line = lines[0].strip().lower()
    if not any(first_line.startswith(s.lower()) for s in VALID_STARTS):
        errors.append(
            f"Mermaid must start with one of: {', '.join(VALID_STARTS)}. "
            f"Got: '{lines[0][:60]}'"
        )

    # 4. Forbidden patterns check
    for pattern in FORBIDDEN_PATTERNS:
        matches = pattern.findall(stripped)
        if matches:
            errors.append(
                f"Forbidden pattern detected: {pattern.pattern} → '{matches[0]}'"
            )

    # 5. Basic bracket balance (subgraph/end)
    subgraph_count = stripped.lower().count("subgraph ")
    end_count = len(re.findall(r"^\s*end\s*$", stripped, re.MULTILINE))
    if subgraph_count != end_count:
        errors.append(
            f"Unbalanced subgraph/end: {subgraph_count} subgraphs, {end_count} ends"
        )

    return len(errors) == 0, errors
