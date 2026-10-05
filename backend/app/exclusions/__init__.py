"""Resource Exclusion Shield — protects seasonal/DR resources from false zombie detection."""

from .rule_engine import evaluate_rule, matches_any_exclusion
from .shield import apply_exclusion_shields, generate_exclusion_suggestions

__all__ = [
    "evaluate_rule",
    "matches_any_exclusion",
    "apply_exclusion_shields",
    "generate_exclusion_suggestions",
]
