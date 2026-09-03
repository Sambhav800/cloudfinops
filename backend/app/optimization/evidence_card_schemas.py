"""
Evidence Card Schemas — Data structures for recommendation explainability & safety clearance.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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


class ResourceSummary(BaseModel):
    """Core resource & action identification summary."""

    resource_name: str
    cloud_resource_id: str
    provider: str  # aws | azure | gcp
    resource_type: str  # e.g., "AWS EC2 Instance", "Azure VM"
    monthly_cost: float
    recommended_action: str  # rightsize | stop | terminate | schedule | tiering
    estimated_monthly_savings: float = 0.0
    region: str = ""


class CorroboratingSignalDetail(BaseModel):
    """Individual corroborating signal metric detail."""

    key: str  # cpu | network | disk | memory | state | connections
    name: str  # Display title, e.g. "CPU Utilization"
    status: SignalStatus
    observed_value: Any = None
    observed_display: str  # e.g. "Avg 3.2% / P95 7.8%"
    threshold_display: str  # e.g. "< 10.0%"
    description: str  # e.g. "Average CPU 3.2% is below 10.0% threshold"
    is_missing: bool = False


class SafetyClearanceItem(BaseModel):
    """Individual safety clearance (veto check) item."""

    check_key: str  # dr_tag | asg_fleet | blue_green | recent_state_change | backup_replication
    title: str  # e.g., "DR / Standby / Failover Tag"
    status: VetoCheckStatus  # cleared | vetoed | unassessed
    description: str  # e.g. "No DR or failover tags detected (Passed)"
    details: Optional[str] = None


class EvidenceCardData(BaseModel):
    """
    Authoritative Evidence Card & Safety Clearance Checklist structure for UI and APIs.
    Satisfies all 6 core explainability & safety clearance requirements.
    """

    recommendation_id: str
    resource_summary: ResourceSummary
    corroborating_signals: Dict[str, CorroboratingSignalDetail] = Field(default_factory=dict)
    safety_clearance: List[SafetyClearanceItem] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    risk_explanation: str = ""
    why_flagged_explanation: str = ""  # "Why we flagged this" human-readable explanation
    missing_data_warnings: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
