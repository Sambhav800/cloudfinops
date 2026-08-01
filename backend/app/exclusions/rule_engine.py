"""Rule engine for evaluating exclusion rules against resources."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def evaluate_rule(rule_match: dict, resource: dict) -> bool:
    """Check if a resource matches an exclusion rule's match criteria."""
    if not rule_match:
        return False

    match_type = rule_match.get("match_type", "")

    if match_type == "tag":
        return _match_tag(rule_match, resource)
    if match_type == "name_pattern":
        return _match_name_pattern(rule_match, resource)
    if match_type == "service_type":
        return _match_service_type(rule_match, resource)
    if match_type == "region":
        return _match_region(rule_match, resource)

    return False


def _match_tag(rule_match: dict, resource: dict) -> bool:
    tags = resource.get("tags") or {}
    if isinstance(tags, str):
        return False
    key = rule_match.get("tag_key", "")
    value = rule_match.get("tag_value")
    if not key:
        return False
    resource_value = tags.get(key)
    if resource_value is None:
        return False
    if value is None:
        return True
    return str(resource_value).lower() == str(value).lower()


def _match_name_pattern(rule_match: dict, resource: dict) -> bool:
    pattern = rule_match.get("pattern", "")
    if not pattern:
        return False
    resource_name = resource.get("resource_name", "")
    try:
        return bool(re.search(pattern, resource_name, re.IGNORECASE))
    except re.error:
        logger.warning("Invalid regex pattern in exclusion rule: %s", pattern)
        return False


def _match_service_type(rule_match: dict, resource: dict) -> bool:
    target = (rule_match.get("service_type") or "").lower()
    actual = (resource.get("service_type") or "").lower()
    return target != "" and target == actual


def _match_region(rule_match: dict, resource: dict) -> bool:
    target = (rule_match.get("region") or "").lower()
    actual = (resource.get("region") or "").lower()
    return target != "" and target == actual


def matches_any_exclusion(resource: dict, exclusions: list[dict]) -> dict | None:
    """
    Check if a resource matches any active exclusion.
    Returns the matching exclusion dict, or None.
    """
    cloud_resource_id = resource.get("cloud_resource_id", "")
    integration_id = resource.get("integration_id", "")

    for exc in exclusions:
        if exc.get("type") == "individual":
            if (
                exc.get("cloud_resource_id") == cloud_resource_id
                and exc.get("integration_id") == integration_id
            ):
                return exc
        elif exc.get("type") == "rule":
            rule_match = exc.get("rule_match")
            if rule_match and evaluate_rule(rule_match, resource):
                return exc

    return None
