"""
Mermaid syntax sanitization.

Prevents injection attacks and ensures valid Mermaid node IDs and labels.
"""

import hashlib
import re


def sanitize_node_id(raw_id: str, prefix: str = "n") -> str:
    """
    Convert any string to a safe Mermaid node ID.

    Rules:
    1. Replace non-alphanumeric chars with underscore.
    2. Collapse consecutive underscores.
    3. Prefix with type abbreviation to avoid collisions.
    4. If result > 40 chars, truncate and append 6-char hash.
    5. Ensure starts with a letter (Mermaid requirement).
    """
    if not raw_id:
        h = hashlib.md5(b"empty").hexdigest()[:8]
        return f"{prefix}_{h}"

    safe = re.sub(r"[^a-zA-Z0-9]", "_", raw_id)
    safe = re.sub(r"_+", "_", safe).strip("_")
    safe = f"{prefix}_{safe}"

    if len(safe) > 40:
        hash_suffix = hashlib.md5(raw_id.encode()).hexdigest()[:6]
        safe = f"{safe[:33]}_{hash_suffix}"

    return safe


# Characters and sequences that can break Mermaid rendering or inject SVG/HTML.
_DANGEROUS_CHARS = re.compile(r'[<>{}`"]')
_MERMAID_SEQUENCES = ["-->", "---|", "-.->", "==>", "~~~"]
_MERMAID_KEYWORDS = ["subgraph", "end", "click", "style", "classDef", "linkStyle", "direction"]


def sanitize_label(raw: str) -> str:
    """
    Sanitize text for use inside Mermaid node labels.

    Prevents:
    - Mermaid syntax injection (-->, subgraph, end, etc.)
    - HTML/SVG injection (<script>, <img onerror>)
    - Quote escaping
    """
    if not raw:
        return "(unnamed)"

    label = _DANGEROUS_CHARS.sub("", raw)

    for seq in _MERMAID_SEQUENCES:
        label = label.replace(seq, " ")

    for kw in _MERMAID_KEYWORDS:
        # Case-insensitive keyword replacement
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        label = pattern.sub(kw.upper(), label)

    if len(label) > 60:
        label = label[:57] + "..."

    return label.strip() or "(unnamed)"
