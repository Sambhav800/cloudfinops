"""
Optimization Engine — Main orchestrator for the classification pipeline.

This is the single entry point called from routes.py after scanners collect evidence.
It coordinates: evidence → classification → pattern analysis → corroboration →
confidence scoring → verdict.

Usage in routes.py:
    from app.optimization.engine import OptimizationEngine

    engine = OptimizationEngine(db=db, user_id=user_id)
    verdicts = await engine.classify(evidence_bundles)
    # verdicts is List[ResourceVerdict] with classification, confidence, evidence chain
"""

import logging
from typing import Any, Dict, List, Optional

from .classification_pipeline import classify_batch, classify_resource
from .confidence_model import ThresholdSet
from .evidence_collector import EvidenceBundle
from .severity import ResourceClassification, ResourceVerdict, Severity

logger = logging.getLogger(__name__)


class OptimizationEngine:
    """
    Main optimization engine orchestrator.

    Coordinates evidence collection, classification, pattern analysis,
    and feedback loop integration.
    """

    def __init__(
        self,
        db: Any = None,
        user_id: Optional[str] = None,
    ):
        self.db = db
        self.user_id = user_id
        self._thresholds: Optional[ThresholdSet] = None
        self._fleet_fp_rate: float = 0.0

    async def initialize(self) -> None:
        """
        Load adaptive thresholds and fleet calibration data.

        Should be called once before classify() to load user-specific
        thresholds from the database.
        """
        if not self.db or not self.user_id:
            self._thresholds = ThresholdSet.default()
            return

        # Load adaptive thresholds if available
        try:
            threshold_doc = await self.db.select(
                "adaptive_thresholds",
                filters={"user_id": self.user_id},
            )
            if threshold_doc:
                self._thresholds = ThresholdSet(
                    thresholds=threshold_doc[0].get("thresholds", {}),
                    source=threshold_doc[0].get("source", "default"),
                    sample_size=threshold_doc[0].get("sample_size", 0),
                )
            else:
                self._thresholds = ThresholdSet.default()
        except Exception:
            self._thresholds = ThresholdSet.default()

        # Load historical false-positive rate
        try:
            feedback_docs = await self.db.select(
                "optimization_feedback",
                filters={"user_id": self.user_id, "action": "dismiss"},
            )
            total_docs = await self.db.select(
                "optimization_feedback",
                filters={"user_id": self.user_id},
            )
            if total_docs:
                self._fleet_fp_rate = len(feedback_docs) / max(len(total_docs), 1)
            else:
                self._fleet_fp_rate = 0.0
        except Exception:
            self._fleet_fp_rate = 0.0

    async def classify(
        self,
        evidence_bundles: List[EvidenceBundle],
        pattern_results: Optional[Dict[str, str]] = None,
    ) -> List[ResourceVerdict]:
        """
        Classify a batch of resources through the full pipeline.

        This is the main entry point called from routes.py after evidence collection.

        Args:
            evidence_bundles: List of EvidenceBundle from provider metrics collectors
            pattern_results: Pre-computed workload patterns (resource_id → pattern_name)

        Returns:
            List of ResourceVerdict with classifications and evidence chains
        """
        if not self._thresholds:
            await self.initialize()

        verdicts = classify_batch(
            evidence_bundles,
            thresholds=self._thresholds,
            fleet_fp_rate=self._fleet_fp_rate,
            pattern_results=pattern_results,
        )

        # Log classification summary
        waste_count = sum(
            1 for v in verdicts
            if v.classification in (
                ResourceClassification.CRITICAL_WASTE,
                ResourceClassification.CONFIRMED_WASTE,
                ResourceClassification.LIKELY_WASTE,
                ResourceClassification.POSSIBLE_WASTE,
            )
        )
        protected_count = sum(
            1 for v in verdicts
            if v.classification == ResourceClassification.PROTECTED
        )
        insufficient_count = sum(
            1 for v in verdicts
            if v.classification == ResourceClassification.INSUFFICIENT_DATA
        )
        ai_review_count = sum(1 for v in verdicts if v.ai_verification_needed)

        logger.info(
            f"Classification complete: {len(verdicts)} resources → "
            f"{waste_count} waste, {protected_count} protected, "
            f"{insufficient_count} insufficient data, "
            f"{ai_review_count} need AI verification"
        )

        return verdicts

    def get_ai_review_candidates(
        self, verdicts: List[ResourceVerdict]
    ) -> List[ResourceVerdict]:
        """
        Filter verdicts to only those that need AI verification.

        These are ambiguous cases (confidence 0.50-0.75) where the deterministic
        engine is uncertain and AI can provide a second opinion.

        This replaces sending ALL resources to AI — reduces Gemini API calls by 60-80%.
        """
        return [v for v in verdicts if v.ai_verification_needed]

    @staticmethod
    def verdicts_to_legacy_updates(
        verdicts: List[ResourceVerdict],
    ) -> List[Dict[str, Any]]:
        """
        Convert ResourceVerdicts to legacy schema updates for MongoDB.

        Maps new graduated classifications back to the existing resource schema
        (status, waste_type, waste_reason, confidence_score) for backward compatibility
        with the current frontend.
        """
        updates = []
        for verdict in verdicts:
            update = {
                "resource_id": verdict.resource_id,
                "status": verdict.legacy_status,
                "confidence_score": verdict.confidence,
                "waste_reason": verdict.waste_reason,
            }

            if verdict.legacy_waste_type:
                update["waste_type"] = verdict.legacy_waste_type

            # Store full verdict data in metadata for new frontend
            update["metadata_updates"] = {
                "optimization": {
                    "classification": verdict.classification.value,
                    "severity": verdict.severity.value,
                    "confidence": verdict.confidence,
                    "corroborating_signals": [
                        {
                            "signal": s.signal_name,
                            "value": s.observed_value,
                            "threshold": s.threshold,
                            "description": s.description,
                        }
                        for s in verdict.corroborating_signals
                    ],
                    "vetoing_signals": [
                        {
                            "reason": v.reason,
                            "type": v.signal_type,
                        }
                        for v in verdict.vetoing_signals
                    ],
                    "pattern_detected": verdict.pattern_detected,
                    "pipeline_version": verdict.pipeline_version,
                    "determined_at": verdict.determined_at.isoformat(),
                }
            }

            if verdict.recommendation:
                rec_data = {
                    "action": verdict.recommendation.action.value,
                    "description": verdict.recommendation.description,
                    "estimated_savings": verdict.recommendation.estimated_monthly_savings,
                    "effort": verdict.recommendation.effort,
                    "risk": verdict.recommendation.risk,
                }
                if verdict.recommendation.target_sku:
                    rec_data["target_sku"] = verdict.recommendation.target_sku
                update["metadata_updates"]["optimization"]["recommendation"] = rec_data

            updates.append(update)

        return updates

    @staticmethod
    def summary(verdicts: List[ResourceVerdict]) -> Dict[str, Any]:
        """Generate a summary of classification results for dashboard stats."""
        total = len(verdicts)
        by_classification = {}
        total_waste = 0.0
        total_savings_potential = 0.0

        for v in verdicts:
            key = v.classification.value
            by_classification[key] = by_classification.get(key, 0) + 1
            if v.classification in (
                ResourceClassification.CRITICAL_WASTE,
                ResourceClassification.CONFIRMED_WASTE,
                ResourceClassification.LIKELY_WASTE,
                ResourceClassification.POSSIBLE_WASTE,
                ResourceClassification.OVERSIZED,
            ):
                total_waste += v.estimated_monthly_waste
                if v.recommendation:
                    total_savings_potential += v.recommendation.estimated_monthly_savings

        avg_confidence = 0.0
        waste_verdicts = [v for v in verdicts if v.confidence > 0]
        if waste_verdicts:
            avg_confidence = sum(v.confidence for v in waste_verdicts) / len(waste_verdicts)

        return {
            "total_resources": total,
            "by_classification": by_classification,
            "total_monthly_waste": round(total_waste, 2),
            "total_savings_potential": round(total_savings_potential, 2),
            "average_confidence": round(avg_confidence, 3),
            "ai_review_needed": sum(1 for v in verdicts if v.ai_verification_needed),
        }
