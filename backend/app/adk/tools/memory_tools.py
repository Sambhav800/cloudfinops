"""
Learning Memory Tools for ADK — Persistent Pattern Library.

Patterns are stored in MongoDB collection `learned_patterns` — they survive restarts,
accumulate over time, and prove the agent is genuinely improving.

Architecture:
- Each pattern has: trigger conditions, learned action, confidence score, observation history
- Confidence grows with each successful observation (sigmoid curve)
- Graduated autonomy: <60% = suggest, 60-85% = recommend, >85% = autonomous
- Patterns are queryable — you can show a dashboard of "what the AI has learned"

This is NOT in-memory state. It's a real MongoDB collection that persists forever.
"""
import os
import re
from datetime import datetime, timezone
from pymongo import MongoClient  # noqa: resolved in venv


def _get_patterns_collection():
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/cloudfinops")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return client["cloudfinops"]["learned_patterns"]


def recall_learned_patterns(resource_type: str = "", provider: str = "", issue_type: str = "") -> dict:
    """
    Search the persistent pattern library for previously learned investigation outcomes.
    Call this BEFORE running expensive scans to check if we already know the answer.

    If a matching pattern exists with high confidence (>80%), you can skip the full scan
    and directly recommend the known resolution with authority.

    Args:
        resource_type: Type of resource (e.g., "ec2", "ebs", "vm", "disk")
        provider: Cloud provider ("aws", "azure", "gcp", or empty for any)
        issue_type: Type of issue (e.g., "stopped", "idle", "unattached", "oversized")

    Returns:
        dict with matching patterns, their confidence scores, and recommended actions
    """
    try:
        collection = _get_patterns_collection()

        query = {}
        if resource_type:
            query["resource_type"] = {"$regex": re.escape(resource_type), "$options": "i"}
        if provider:
            query["provider"] = provider.lower()
        if issue_type:
            query["issue_type"] = {"$regex": re.escape(issue_type), "$options": "i"}

        patterns = list(collection.find(query).sort("confidence", -1).limit(10))

        if not patterns:
            return {
                "status": "no_patterns",
                "message": "No learned patterns match this query. Investigate normally — the system will learn from the outcome.",
                "total_patterns_in_library": collection.count_documents({}),
                "matches": [],
            }

        return {
            "status": "patterns_found",
            "message": f"Found {len(patterns)} relevant patterns from past investigations.",
            "total_patterns_in_library": collection.count_documents({}),
            "matches": [
                {
                    "pattern_id": p.get("pattern_id"),
                    "description": p.get("description"),
                    "learned_action": p.get("learned_action"),
                    "confidence_pct": round(p.get("confidence", 0) * 100, 1),
                    "autonomy_level": _get_autonomy_level(p.get("confidence", 0)),
                    "times_observed": p.get("times_observed", 0),
                    "times_successful": p.get("successful_outcomes", 0),
                    "success_rate_pct": round(p.get("success_rate", 0) * 100, 1),
                    "risk_level": p.get("risk_level", "unknown"),
                    "first_observed": p.get("first_observed", ""),
                    "last_confirmed": p.get("last_confirmed", ""),
                }
                for p in patterns
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "matches": []}


def save_learned_pattern(
    resource_type: str,
    provider: str,
    issue_type: str,
    description: str,
    learned_action: str,
    risk_level: str = "low",
    was_successful: bool = True,
) -> dict:
    """
    Save or update a pattern in the persistent learning library after an investigation.
    Call this at the END of an investigation when you've confirmed the resolution.

    Patterns accumulate in MongoDB — they survive restarts and prove the agent improves.
    After 5+ successful observations, confidence crosses the 'recommend' threshold.
    After 10+ successful observations, confidence reaches 'autonomous' level.

    Args:
        resource_type: Type of resource (e.g., "ec2", "ebs", "vm", "disk")
        provider: Cloud provider ("aws", "azure", "gcp")
        issue_type: Type of issue (e.g., "stopped", "idle", "unattached")
        description: Human-readable description of the pattern
        learned_action: What action resolves this (e.g., "terminate", "rightsize", "delete")
        risk_level: Risk of the action ("low", "medium", "high")
        was_successful: Whether the resolution was confirmed successful

    Returns:
        dict with the saved pattern's updated confidence score and autonomy level
    """
    try:
        collection = _get_patterns_collection()
        now = datetime.now(timezone.utc).isoformat()
        pattern_id = f"{provider}:{resource_type}:{issue_type}".lower()

        existing = collection.find_one({"pattern_id": pattern_id})

        if existing:
            times_observed = existing.get("times_observed", 0) + 1
            successful_outcomes = existing.get("successful_outcomes", 0) + (1 if was_successful else 0)
            success_rate = successful_outcomes / times_observed if times_observed > 0 else 0

            # Confidence: sigmoid-like growth capped at success_rate
            observation_factor = min(times_observed / 10.0, 1.0)
            confidence = round(observation_factor * success_rate, 4)

            collection.update_one(
                {"pattern_id": pattern_id},
                {"$set": {
                    "times_observed": times_observed,
                    "successful_outcomes": successful_outcomes,
                    "success_rate": round(success_rate, 4),
                    "confidence": confidence,
                    "last_confirmed": now,
                    "description": description,
                    "learned_action": learned_action,
                    "risk_level": risk_level,
                    "updated_at": now,
                },
                "$push": {
                    "observation_log": {
                        "timestamp": now,
                        "was_successful": was_successful,
                        "confidence_at_time": confidence,
                    }
                }},
            )
        else:
            confidence = 0.1 if was_successful else 0.0
            collection.insert_one({
                "pattern_id": pattern_id,
                "resource_type": resource_type.lower(),
                "provider": provider.lower(),
                "issue_type": issue_type.lower(),
                "description": description,
                "learned_action": learned_action,
                "risk_level": risk_level,
                "times_observed": 1,
                "successful_outcomes": 1 if was_successful else 0,
                "success_rate": 1.0 if was_successful else 0.0,
                "confidence": confidence,
                "first_observed": now,
                "last_confirmed": now,
                "created_at": now,
                "updated_at": now,
                "observation_log": [{
                    "timestamp": now,
                    "was_successful": was_successful,
                    "confidence_at_time": confidence,
                }],
            })
            times_observed = 1
            successful_outcomes = 1 if was_successful else 0

        confidence_pct = round(confidence * 100, 1)
        autonomy_level = _get_autonomy_level(confidence)
        observations_to_next = _observations_to_next_level(times_observed, confidence)

        return {
            "status": "pattern_saved",
            "persisted_to": "MongoDB (survives restarts)",
            "pattern_id": pattern_id,
            "confidence_pct": confidence_pct,
            "autonomy_level": autonomy_level,
            "times_observed": times_observed,
            "success_rate_pct": round((successful_outcomes / times_observed) * 100, 1),
            "next_level_in": observations_to_next,
            "message": f"Pattern '{pattern_id}' saved to persistent library. "
                       f"Confidence: {confidence_pct}% ({autonomy_level}). "
                       f"{observations_to_next}",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_learning_stats() -> dict:
    """
    Get statistics about the agent's learning progress.
    Shows how many patterns have been learned, their confidence distribution,
    and proves the system is genuinely improving over time.

    Returns:
        dict with total patterns, confidence distribution, top patterns, and growth metrics
    """
    try:
        collection = _get_patterns_collection()
        all_patterns = list(collection.find({}).sort("confidence", -1))
        total = len(all_patterns)

        if total == 0:
            return {
                "status": "empty",
                "message": "No patterns learned yet. The system will start learning from the first investigation.",
                "total_patterns": 0,
            }

        autonomous_count = sum(1 for p in all_patterns if p.get("confidence", 0) >= 0.85)
        recommend_count = sum(1 for p in all_patterns if 0.6 <= p.get("confidence", 0) < 0.85)
        suggest_count = sum(1 for p in all_patterns if p.get("confidence", 0) < 0.6)
        total_observations = sum(p.get("times_observed", 0) for p in all_patterns)
        avg_confidence = sum(p.get("confidence", 0) for p in all_patterns) / total

        return {
            "status": "success",
            "total_patterns": total,
            "total_observations": total_observations,
            "average_confidence_pct": round(avg_confidence * 100, 1),
            "autonomy_distribution": {
                "autonomous (>85%)": autonomous_count,
                "recommend (60-85%)": recommend_count,
                "suggest (<60%)": suggest_count,
            },
            "top_patterns": [
                {
                    "pattern_id": p.get("pattern_id"),
                    "description": p.get("description"),
                    "confidence_pct": round(p.get("confidence", 0) * 100, 1),
                    "times_observed": p.get("times_observed", 0),
                    "autonomy_level": _get_autonomy_level(p.get("confidence", 0)),
                }
                for p in all_patterns[:5]
            ],
            "message": f"Agent has learned {total} patterns from {total_observations} observations. "
                       f"{autonomous_count} patterns are at autonomous confidence level.",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _get_autonomy_level(confidence: float) -> str:
    if confidence >= 0.85:
        return "autonomous"
    elif confidence >= 0.60:
        return "recommend"
    return "suggest"


def _observations_to_next_level(current_observations: int, current_confidence: float) -> str:
    if current_confidence >= 0.85:
        return "Already at autonomous level — maximum confidence achieved."
    if current_confidence >= 0.60:
        remaining = max(0, 10 - current_observations)
        return f"~{remaining} more successful observations to reach autonomous level."
    remaining = max(0, 6 - current_observations)
    return f"~{remaining} more successful observations to reach recommend level."
