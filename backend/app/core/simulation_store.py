"""
Persistence helpers for shift-left simulator runs.

Raw Terraform plans are not stored. Every read is scoped by user_id and uses
the repository MongoDB adapter methods instead of direct Motor collection calls.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


SIMULATION_RUNS_COLLECTION = "simulation_runs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lightweight_run(row: Dict[str, Any]) -> Dict[str, Any]:
    run_id = str(row.get("id") or row.get("_id") or "")
    return {
        "_id": run_id,
        "id": run_id,
        "user_id": row.get("user_id"),
        "source_type": row.get("source_type"),
        "source_hash": row.get("source_hash"),
        "filename": row.get("filename"),
        "summary": row.get("summary") or {},
        "monthly": row.get("monthly") or {},
        "annual": row.get("annual") or {},
        "findings_count": len(row.get("findings") or []),
        "policy": row.get("policy"),
        "created_at": row.get("created_at"),
    }


async def save_simulation_run(
    db: Any,
    user_id: str,
    source_type: str,
    source_hash: str,
    filename: Optional[str],
    monthly: Dict[str, float],
    annual: Dict[str, float],
    summary: Dict[str, int],
    resources: List[Dict[str, Any]],
    unestimated_resources: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
    policy: Optional[Dict[str, Any]] = None,
) -> str:
    """Save one simulator run without storing the raw Terraform plan."""
    run_id = str(uuid4())
    document = {
        "id": run_id,
        "user_id": user_id,
        "source_type": source_type,
        "source_hash": source_hash,
        "filename": filename,
        "monthly": monthly,
        "annual": annual,
        "summary": summary,
        "resources": resources,
        "unestimated_resources": unestimated_resources,
        "findings": findings,
        "policy": policy,
        "created_at": _now_iso(),
    }
    await db.insert(SIMULATION_RUNS_COLLECTION, document)
    return run_id


async def get_simulation_history(db: Any, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent simulation run summaries for the authenticated user only."""
    rows = await db.select(SIMULATION_RUNS_COLLECTION, filters={"user_id": user_id})
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return [_lightweight_run(row) for row in rows[: max(limit, 0)]]


async def get_simulation_run(db: Any, user_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    """Return a full simulator run only when it belongs to the authenticated user."""
    rows = await db.select(
        SIMULATION_RUNS_COLLECTION,
        filters={"id": run_id, "user_id": user_id},
    )
    if not rows:
        return None

    row = dict(rows[0])
    row["_id"] = str(row.get("id") or run_id)
    return row
