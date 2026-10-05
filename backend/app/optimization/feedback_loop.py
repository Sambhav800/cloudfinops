"""
Feedback Loop — User actions improve future classification accuracy.

Every time a user approves, dismisses, excludes, or remediates a finding,
that signal is captured and used to:
1. Adjust adaptive thresholds (immediate)
2. Learn protection patterns (accumulated)
3. Track true/false positive rates (fleet calibration)

This is what makes the system self-improving — each false positive permanently
improves future accuracy for that user's fleet.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeedbackAction(str, Enum):
    APPROVE = "approve"
    DISMISS = "dismiss"
    EXCLUDE = "exclude"
    REMEDIATE = "remediate"
    DEFER = "defer"


@dataclass
class FeedbackEvent:
    """A user action on a classification verdict."""

    user_id: str
    resource_id: str
    action: FeedbackAction
    classification_at_time: str
    confidence_at_time: float
    signals_at_time: Dict[str, float]
    resource_type: str
    provider: str
    tags: Dict[str, str] = field(default_factory=dict)
    resource_name: str = ""
    reason: Optional[str] = None
    monthly_cost: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Minimum dismissals before a pattern becomes auto-protection
AUTO_PROTECTION_THRESHOLD = 5
# Minimum distinct users before a pattern becomes globally suggested
GLOBAL_PATTERN_THRESHOLD = 3


class FeedbackProcessor:
    """
    Processes user feedback to improve classification accuracy.

    Three improvement mechanisms:
    1. Threshold adjustment: single-resource-type threshold shift (immediate)
    2. Pattern learning: identify common false-positive patterns (batch)
    3. Fleet calibration: track FP rate per resource type (aggregated)
    """

    def __init__(self, db: Any = None):
        self.db = db

    async def process_feedback(self, event: FeedbackEvent) -> Dict[str, Any]:
        """
        Process a single feedback event and apply improvements.

        Returns a summary of what was learned/adjusted.
        """
        result = {
            "action": event.action.value,
            "adjustments_made": [],
        }

        # Always store the raw feedback event
        await self._store_event(event)

        if event.action == FeedbackAction.DISMISS:
            adjustments = await self._handle_false_positive(event)
            result["adjustments_made"] = adjustments
        elif event.action == FeedbackAction.EXCLUDE:
            adjustments = await self._handle_exclusion(event)
            result["adjustments_made"] = adjustments
        elif event.action in (FeedbackAction.APPROVE, FeedbackAction.REMEDIATE):
            await self._handle_true_positive(event)
            result["adjustments_made"] = ["reinforced_thresholds"]

        return result

    async def _store_event(self, event: FeedbackEvent) -> None:
        """Persist the raw feedback event."""
        if not self.db:
            return

        try:
            await self.db.insert("optimization_feedback", {
                "user_id": event.user_id,
                "resource_id": event.resource_id,
                "action": event.action.value,
                "classification_at_time": event.classification_at_time,
                "confidence_at_time": event.confidence_at_time,
                "signals_at_time": event.signals_at_time,
                "resource_type": event.resource_type,
                "provider": event.provider,
                "tags": event.tags,
                "resource_name": event.resource_name,
                "reason": event.reason,
                "monthly_cost": event.monthly_cost,
                "timestamp": event.timestamp,
            })
        except Exception as e:
            logger.warning(f"Failed to store feedback event: {e}")

    async def _handle_false_positive(self, event: FeedbackEvent) -> List[str]:
        """
        Handle a dismissed finding (false positive).

        Actions:
        1. Adjust threshold for this resource type upward
        2. Record the tag/name pattern that caused the FP
        3. Check if any pattern has accumulated enough dismissals for auto-protection
        """
        adjustments = []

        # 1. Threshold adjustment
        from .adaptive_thresholds import AdaptiveThresholdEngine
        threshold_engine = AdaptiveThresholdEngine(db=self.db)

        for signal_name, value in event.signals_at_time.items():
            if value > 0:
                await threshold_engine.adjust_from_feedback(
                    user_id=event.user_id,
                    provider=event.provider,
                    resource_type=event.resource_type,
                    signal_name=signal_name,
                    observed_value=value,
                    action="dismiss",
                )
                adjustments.append(f"threshold_adjusted:{signal_name}")

        # 2. Learn protection patterns from tags
        await self._learn_protection_patterns(event)
        adjustments.append("pattern_recorded")

        return adjustments

    async def _handle_exclusion(self, event: FeedbackEvent) -> List[str]:
        """
        Handle a user-created exclusion (shield).

        Exclusions are stronger signals than dismissals — the user is saying
        "this will ALWAYS be a false positive, stop flagging it."
        """
        adjustments = []

        # Record the pattern with extra weight
        await self._learn_protection_patterns(event, weight=3)
        adjustments.append("protection_pattern_learned_3x")

        # Also adjust thresholds
        from .adaptive_thresholds import AdaptiveThresholdEngine
        threshold_engine = AdaptiveThresholdEngine(db=self.db)

        for signal_name, value in event.signals_at_time.items():
            if value > 0:
                await threshold_engine.adjust_from_feedback(
                    user_id=event.user_id,
                    provider=event.provider,
                    resource_type=event.resource_type,
                    signal_name=signal_name,
                    observed_value=value,
                    action="exclude",
                )

        return adjustments

    async def _handle_true_positive(self, event: FeedbackEvent) -> None:
        """
        Handle a confirmed finding (true positive).

        Reinforces current thresholds — the system was correct.
        No threshold adjustment needed, but we track for FP rate calculation.
        """
        pass  # The stored event itself contributes to FP rate calculation

    async def _learn_protection_patterns(
        self, event: FeedbackEvent, weight: int = 1
    ) -> None:
        """
        Learn which tag/name patterns indicate legitimate resources.

        If multiple users dismiss resources with tag 'purpose:dr', we learn
        that 'purpose:dr' is a protection signal.
        """
        if not self.db:
            return

        # Extract patterns from tags
        patterns_to_record = []

        for key, value in event.tags.items():
            patterns_to_record.append(f"tag:{key.lower()}:{value.lower()}")

        # Extract patterns from resource name
        name = event.resource_name.lower()
        name_parts = set()
        for separator in ["-", "_", "."]:
            name_parts.update(name.split(separator))

        # Only learn from meaningful name parts (> 2 chars, not just numbers)
        for part in name_parts:
            if len(part) > 2 and not part.isdigit():
                patterns_to_record.append(f"name_part:{part}")

        # Record each pattern
        for pattern_key in patterns_to_record:
            try:
                # Upsert the pattern counter
                existing = await self.db.select(
                    "learned_protections",
                    filters={"pattern_key": pattern_key, "provider": event.provider},
                )

                if existing:
                    doc = existing[0]
                    distinct_users = set(doc.get("user_ids", []))
                    distinct_users.add(event.user_id)

                    await self.db.update(
                        "learned_protections",
                        {
                            "dismiss_count": doc.get("dismiss_count", 0) + weight,
                            "distinct_users": len(distinct_users),
                            "user_ids": list(distinct_users),
                            "auto_protect": (
                                doc.get("dismiss_count", 0) + weight >= AUTO_PROTECTION_THRESHOLD
                            ),
                            "last_updated": datetime.now(timezone.utc),
                        },
                        filters={"pattern_key": pattern_key, "provider": event.provider},
                    )
                else:
                    await self.db.insert("learned_protections", {
                        "pattern_key": pattern_key,
                        "provider": event.provider,
                        "dismiss_count": weight,
                        "distinct_users": 1,
                        "user_ids": [event.user_id],
                        "auto_protect": weight >= AUTO_PROTECTION_THRESHOLD,
                        "last_updated": datetime.now(timezone.utc),
                    })

            except Exception as e:
                logger.debug(f"Failed to record protection pattern {pattern_key}: {e}")

    async def get_learned_protections(
        self, provider: str
    ) -> List[Dict[str, Any]]:
        """
        Get all learned protection patterns that have reached auto-protect threshold.

        These are tag/name patterns that have been dismissed enough times
        to become automatic veto signals in the classification pipeline.
        """
        if not self.db:
            return []

        try:
            protections = await self.db.select(
                "learned_protections",
                filters={"provider": provider, "auto_protect": True},
            )
            return protections or []
        except Exception:
            return []

    async def get_fp_rate(
        self,
        user_id: str,
        provider: str = "",
        resource_type: str = "",
    ) -> float:
        """
        Compute the historical false-positive rate for fleet calibration.

        FP rate = dismiss_count / total_feedback_count
        """
        if not self.db:
            return 0.0

        try:
            filters: Dict[str, Any] = {"user_id": user_id}
            if provider:
                filters["provider"] = provider
            if resource_type:
                filters["resource_type"] = resource_type

            all_feedback = await self.db.select("optimization_feedback", filters=filters)
            if not all_feedback:
                return 0.0

            dismiss_count = sum(
                1 for f in all_feedback if f.get("action") == "dismiss"
            )
            total_count = len(all_feedback)

            return dismiss_count / total_count if total_count > 0 else 0.0

        except Exception:
            return 0.0
