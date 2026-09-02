"""
Evidence Card Schemas — Data structures for recommendation explainability & safety clearance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalStatus(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    MISSING = "missing"


class VetoCheckStatus(str, Enum):
    CLEARED = "cleared"
    VETOED = "vetoed"
    UNASSESSED = "unassessed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ResourceSummary:
    """Core resource & action identification summary."""

    resource_name: str
    cloud_resource_id: str
    provider: str  # aws | azure | gcp
    resource_type: str  # e.g., "AWS EC2 Instance", "Azure VM"
    monthly_cost: float
    recommended_action: str  # rightsize | stop | terminate | schedule | tiering
    estimated_monthly_savings: float = 0.0
    region: str = ""


@dataclass
class CorroboratingSignalDetail:
    """Individual corroborating signal metric detail."""

    key: str  # cpu | network | disk | memory | state | connections
    name: str  # Display title, e.g. "CPU Utilization"
    status: SignalStatus
    observed_value: Any
    observed_display: str  # e.g. "Avg 3.2% / P95 7.8%"
    threshold_display: str  # e.g. "< 10.0%"
    description: str  # e.g. "Average CPU 3.2% is below 10.0% threshold"
    is_missing: bool = False


@dataclass
class SafetyClearanceItem:
    """Individual safety clearance (veto check) item."""

    check_key: str  # dr_tag | asg_fleet | blue_green | recent_state_change | backup_replication
    title: str  # e.g., "DR / Standby / Failover Tag"
    status: VetoCheckStatus  # cleared | vetoed | unassessed
    description: str  # e.g. "No DR or failover tags detected (Passed)"
    details: Optional[str] = None


@dataclass
class EvidenceCardData:
    """
    Authoritative Evidence Card & Safety Clearance Checklist structure for UI and APIs.
    Satisfies all 6 core explainability & safety clearance requirements.
    """

    recommendation_id: str
    resource_summary: ResourceSummary
    corroborating_signals: Dict[str, CorroboratingSignalDetail] = field(default_factory=dict)
    safety_clearance: List[SafetyClearanceItem] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    risk_explanation: str = ""
    why_flagged_explanation: str = ""  # "Why we flagged this" human-readable explanation
    missing_data_warnings: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to standard JSON-serializable dictionary."""
        return {
            "recommendation_id": self.recommendation_id,
            "resource_summary": {
                "resource_name": self.resource_summary.resource_name,
                "cloud_resource_id": self.resource_summary.cloud_resource_id,
                "provider": self.resource_summary.provider,
                "resource_type": self.resource_summary.resource_type,
                "monthly_cost": round(self.resource_summary.monthly_cost, 2),
                "recommended_action": self.resource_summary.recommended_action,
                "estimated_monthly_savings": round(self.resource_summary.estimated_monthly_savings, 2),
                "region": self.resource_summary.region,
            },
            "corroborating_signals": {
                k: {
                    "key": v.key,
                    "name": v.name,
                    "status": v.status.value if isinstance(v.status, Enum) else v.status,
                    "observed_value": v.observed_value,
                    "observed_display": v.observed_display,
                    "threshold_display": v.threshold_display,
                    "description": v.description,
                    "is_missing": v.is_missing,
                }
                for k, v in self.corroborating_signals.items()
            },
            "safety_clearance": [
                {
                    "check_key": item.check_key,
                    "title": item.title,
                    "status": item.status.value if isinstance(item.status, Enum) else item.status,
                    "description": item.description,
                    "details": item.details,
                }
                for item in self.safety_clearance
            ],
            "risk_level": self.risk_level.value if isinstance(self.risk_level, Enum) else self.risk_level,
            "risk_explanation": self.risk_explanation,
            "why_flagged_explanation": self.why_flagged_explanation,
            "missing_data_warnings": self.missing_data_warnings,
            "created_at": self.created_at,
        }
