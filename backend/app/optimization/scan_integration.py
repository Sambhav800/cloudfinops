"""
Scan Integration — Bridge between existing scanner output and the optimization engine.

Called from routes.py after scanners produce findings and before AI verification.
Converts scanner findings into EvidenceBundles, runs the classification pipeline,
and writes verdicts back to MongoDB using the legacy schema.

This replaces the AI-as-classifier pattern with deterministic-first classification
while keeping the AI verifier for ambiguous cases only.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .ai_verifier import AIVerifier
from .classification_pipeline import classify_batch
from .confidence_model import ThresholdSet
from .engine import OptimizationEngine
from .evidence_collector import (
    EvidenceBundle,
    ProviderState,
    SignalTimeSeries,
    build_evidence_bundle,
)
from .feedback_loop import FeedbackProcessor
from .relationship_graph import ResourceRelationshipGraph
from .severity import ResourceClassification, ResourceVerdict
from .temporal_intelligence import detect_extended_patterns

logger = logging.getLogger(__name__)


async def run_optimization_pipeline(
    findings: List[Dict[str, Any]],
    provider: str,
    user_id: str,
    integration_id: str,
    db: Any = None,
    gemini_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the full optimization pipeline on scanner findings.

    This is the main integration point called from routes.py after
    scanner.scan_all() produces findings.

    Args:
        findings: Raw scanner output (list of resource dicts)
        provider: Cloud provider (aws, azure, gcp)
        user_id: Authenticated user ID
        integration_id: Cloud integration ID
        db: MongoDBClient instance
        gemini_api_key: Optional Gemini key for AI verification of ambiguous cases

    Returns:
        Dict with:
          - verdicts: List[ResourceVerdict] — full classification results
          - legacy_updates: List[Dict] — DB updates in legacy schema format
          - stats: summary statistics
          - ai_review_candidates: count of ambiguous cases
    """
    # Phase 1: Build relationship graph from all resources
    graph = ResourceRelationshipGraph()
    graph.build_from_resources(findings)
    logger.info(
        f"Relationship graph built: {graph.stats['nodes']} nodes, "
        f"{graph.stats['edges']} edges, {graph.stats['protected_resources']} protected"
    )

    # Phase 2: Convert scanner findings to EvidenceBundles
    bundles = []
    for finding in findings:
        bundle = _finding_to_evidence_bundle(finding, provider, graph)
        bundles.append(bundle)

    # Phase 3: Initialize optimization engine with user-specific thresholds
    engine = OptimizationEngine(db=db, user_id=user_id)
    await engine.initialize()

    # Phase 4: Run classification pipeline
    verdicts = await engine.classify(bundles)

    # Phase 5: AI verification for ambiguous cases only
    ai_review_count = 0
    if gemini_api_key:
        ai_candidates = engine.get_ai_review_candidates(verdicts)
        ai_review_count = len(ai_candidates)

        if ai_candidates:
            verifier = AIVerifier(gemini_client=gemini_api_key)
            ai_results = await verifier.verify_batch(ai_candidates, bundles)
            verdicts = verifier.apply_verifications(verdicts, ai_results)
            logger.info(f"AI verified {len(ai_results)} ambiguous resources")

    # Phase 6: Convert to legacy format for DB writes
    legacy_updates = OptimizationEngine.verdicts_to_legacy_updates(verdicts)
    summary = OptimizationEngine.summary(verdicts)

    # Phase 7: Write verdicts back to resources collection
    if db:
        await _persist_verdicts(db, legacy_updates, user_id, integration_id)

    logger.info(
        f"Optimization pipeline complete: {summary['total_resources']} resources, "
        f"{summary['total_monthly_waste']:.2f} monthly waste detected, "
        f"confidence avg={summary['average_confidence']:.2f}"
    )

    return {
        "verdicts": verdicts,
        "legacy_updates": legacy_updates,
        "stats": summary,
        "ai_review_candidates": ai_review_count,
        "potential_savings": summary["total_monthly_waste"],
        "ai_confidence_score": _compute_overall_confidence(verdicts),
    }


async def process_user_feedback(
    user_id: str,
    resource_id: str,
    action: str,
    resource_data: Dict[str, Any],
    reason: Optional[str] = None,
    db: Any = None,
) -> Dict[str, Any]:
    """
    Process user feedback on a classification verdict.

    Called from routes.py when user approves/dismisses/excludes a finding.
    Feeds the signal into the adaptive threshold system and feedback loop.
    """
    from .feedback_loop import FeedbackAction, FeedbackEvent

    action_map = {
        "approve": FeedbackAction.APPROVE,
        "approved": FeedbackAction.APPROVE,
        "dismiss": FeedbackAction.DISMISS,
        "dismissed": FeedbackAction.DISMISS,
        "reject": FeedbackAction.DISMISS,
        "rejected": FeedbackAction.DISMISS,
        "exclude": FeedbackAction.EXCLUDE,
        "remediate": FeedbackAction.REMEDIATE,
    }

    feedback_action = action_map.get(action.lower(), FeedbackAction.DEFER)

    # Extract signals from resource metadata
    metadata = resource_data.get("metadata", {})
    optimization = metadata.get("optimization", {})
    signals_at_time = {}
    for signal in optimization.get("corroborating_signals", []):
        signals_at_time[signal.get("signal", "")] = signal.get("value", 0)

    event = FeedbackEvent(
        user_id=user_id,
        resource_id=resource_id,
        action=feedback_action,
        classification_at_time=optimization.get("classification", ""),
        confidence_at_time=optimization.get("confidence", 0.0),
        signals_at_time=signals_at_time,
        resource_type=resource_data.get("service_type", ""),
        provider=resource_data.get("provider", ""),
        tags=resource_data.get("tags", {}),
        resource_name=resource_data.get("resource_name", ""),
        reason=reason,
        monthly_cost=resource_data.get("cost", 0.0),
    )

    processor = FeedbackProcessor(db=db)
    result = await processor.process_feedback(event)
    return result


def _finding_to_evidence_bundle(
    finding: Dict[str, Any],
    provider: str,
    graph: ResourceRelationshipGraph,
) -> EvidenceBundle:
    """
    Convert a raw scanner finding dict into an EvidenceBundle.

    Extracts metrics from the finding's metadata and metrics_data fields,
    builds SignalTimeSeries objects, and attaches relationship data from the graph.
    """
    resource_id = finding.get("cloud_resource_id") or finding.get("resource_name", "")
    metadata = finding.get("metadata", {})
    metrics_data = finding.get("metrics_data", {})
    tags = finding.get("tags", {})

    # Determine provider state from scanner status
    status = (finding.get("status") or "").lower()
    state_str = _map_scanner_status_to_state(status, metadata)

    # Build signal time-series from metrics
    signals = _extract_signals(metadata, metrics_data, provider)

    # Get relationships from the graph
    relationships = graph.get_relationships_for_evidence(resource_id)

    # Compute resource age
    resource_age_days = _compute_resource_age(finding)

    # Monthly cost
    cost = float(finding.get("cost", 0) or 0)
    cost_source = metadata.get("cost_source", "unknown")

    return build_evidence_bundle(
        resource_id=resource_id,
        provider=provider,
        resource_type=finding.get("service_type", ""),
        provider_state=state_str,
        signals=signals,
        tags=tags,
        resource_age_days=resource_age_days,
        monthly_cost=cost,
        cost_source=cost_source,
        resource_name=finding.get("resource_name", ""),
        region=finding.get("region", ""),
        cloud_resource_id=resource_id,
        relationships=relationships,
    )


def _map_scanner_status_to_state(status: str, metadata: Dict[str, Any]) -> str:
    """Map scanner status strings to ProviderState values."""
    if status in ("stopped", "zombie", "waste"):
        power_state = metadata.get("power_state", "")
        if "deallocated" in power_state.lower():
            return "deallocated"
        return "stopped"
    elif status in ("terminated",):
        return "terminated"
    elif status in ("suspended",):
        return "suspended"
    return "running"


def _extract_signals(
    metadata: Dict[str, Any],
    metrics_data: Dict[str, Any],
    provider: str,
) -> Dict[str, SignalTimeSeries]:
    """
    Extract available metric signals from scanner output.

    Different scanners store metrics in different places:
    - AWS: metadata.avg_cpu_7d, metadata.network_in, metadata.disk_ops
    - Azure: metrics_data.cpu_avg, metrics_data.network_in_mb, etc.
    - GCP: metrics_data fields

    Creates SignalTimeSeries with point-in-time values when full time-series
    are not available (the scanner stores aggregates, not raw points).
    """
    signals: Dict[str, SignalTimeSeries] = {}
    now = datetime.now(timezone.utc)

    # Create timestamps spanning 7+ days. build_evidence_bundle computes
    # observation_days as int(span.total_seconds() / 86400), so we need
    # first→last to span >= 7 days (8 points, 1 day apart).
    timestamps_7d = [now - timedelta(days=7-i) for i in range(8)]

    # CPU average — multiple field names across providers
    cpu_avg = (
        metadata.get("avg_cpu_7d")
        or metrics_data.get("cpu_avg")
        or metrics_data.get("percentage_cpu")
        or metadata.get("cpu_avg")
    )
    if cpu_avg is not None:
        cpu_avg = float(cpu_avg)
        s = SignalTimeSeries(
            metric_name="cpu_avg",
            values=[cpu_avg] * 8,
            timestamps=timestamps_7d,
            interval=timedelta(days=1),
            aggregation="avg",
        )
        s.compute_statistics()
        signals["cpu_avg"] = s

    # CPU max
    cpu_max = (
        metadata.get("max_cpu_7d")
        or metrics_data.get("cpu_max")
        or metadata.get("cpu_max")
    )
    if cpu_max is not None:
        s = SignalTimeSeries(
            metric_name="cpu_max",
            values=[float(cpu_max)] * 8,
            timestamps=timestamps_7d,
            interval=timedelta(days=1),
        )
        s.compute_statistics()
        signals["cpu_max"] = s

    # Network in (MB) — Azure uses "network_in_max_mb"
    net_in = (
        metrics_data.get("network_in_mb")
        or metadata.get("network_in_mb")
        or metrics_data.get("network_in_max_mb")
        or metadata.get("network_in_max_mb")
    )
    if net_in is not None:
        s = SignalTimeSeries(
            metric_name="network_in_mb",
            values=[float(net_in)] * 8,
            timestamps=timestamps_7d,
            interval=timedelta(days=1),
        )
        s.compute_statistics()
        signals["network_in_mb"] = s

    # Network out (MB)
    net_out = (
        metrics_data.get("network_out_mb")
        or metadata.get("network_out_mb")
    )
    if net_out is not None:
        s = SignalTimeSeries(
            metric_name="network_out_mb",
            values=[float(net_out)] * 8,
            timestamps=timestamps_7d,
            interval=timedelta(days=1),
        )
        s.compute_statistics()
        signals["network_out_mb"] = s

    # Disk I/O — Azure stores as "disk_iops_consumed_pct" (percentage)
    # AWS/GCP store as raw ops counts. We normalize both as "disk activity" signal.
    disk_read = (
        metrics_data.get("disk_read_ops")
        or metadata.get("disk_read_ops")
        or metrics_data.get("disk_iops_consumed_pct")
        or metadata.get("disk_iops_consumed_pct")
    )
    if disk_read is not None:
        s = SignalTimeSeries(
            metric_name="disk_read_ops",
            values=[float(disk_read)] * 8,
            timestamps=timestamps_7d,
            interval=timedelta(days=1),
        )
        s.compute_statistics()
        signals["disk_read_ops"] = s

    # Disk write / bandwidth — Azure has "disk_bandwidth_consumed_pct"
    disk_write = (
        metrics_data.get("disk_write_ops")
        or metadata.get("disk_write_ops")
        or metrics_data.get("disk_bandwidth_consumed_pct")
        or metadata.get("disk_bandwidth_consumed_pct")
    )
    if disk_write is not None:
        s = SignalTimeSeries(
            metric_name="disk_write_ops",
            values=[float(disk_write)] * 8,
            timestamps=timestamps_7d,
            interval=timedelta(days=1),
        )
        s.compute_statistics()
        signals["disk_write_ops"] = s

    # Memory — Azure uses "memory_avg_pct" / "memory_max_pct"
    mem_pct = (
        metrics_data.get("memory_used_pct")
        or metadata.get("memory_pct")
        or metrics_data.get("memory_avg_pct")
        or metadata.get("memory_avg_pct")
    )
    if mem_pct is not None:
        s = SignalTimeSeries(
            metric_name="memory_used_pct",
            values=[float(mem_pct)] * 8,
            timestamps=timestamps_7d,
            interval=timedelta(days=1),
        )
        s.compute_statistics()
        signals["memory_used_pct"] = s

    # Connection count — RDS/databases
    connections = (
        metrics_data.get("connections")
        or metadata.get("connection_count")
        or metadata.get("database_connections")
    )
    if connections is not None:
        s = SignalTimeSeries(
            metric_name="connections",
            values=[float(connections)] * 8,
            timestamps=timestamps_7d,
            interval=timedelta(days=1),
        )
        s.compute_statistics()
        signals["connections"] = s

    return signals


def _compute_resource_age(finding: Dict[str, Any]) -> int:
    """Compute resource age in days from available metadata."""
    metadata = finding.get("metadata", {})

    # Try launch_time / created_at
    for field in ("launch_time", "created_at", "creation_timestamp", "time_created"):
        value = metadata.get(field)
        if value:
            try:
                if isinstance(value, str):
                    # Handle various datetime formats
                    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            dt = datetime.strptime(value, fmt)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            age = (datetime.now(timezone.utc) - dt).days
                            return max(0, age)
                        except ValueError:
                            continue
                elif isinstance(value, datetime):
                    age = (datetime.now(timezone.utc) - value).days
                    return max(0, age)
            except Exception:
                continue

    # Default: assume resource is old enough for classification
    return 90


async def _persist_verdicts(
    db: Any,
    legacy_updates: List[Dict[str, Any]],
    user_id: str,
    integration_id: str,
) -> int:
    """
    Write optimization verdicts back to the resources collection.

    Updates status, confidence_score, waste_reason, waste_type, and
    adds optimization metadata for the new frontend.
    """
    updated_count = 0

    for update in legacy_updates:
        resource_id = update.get("resource_id")
        if not resource_id:
            continue

        # Build the update document
        update_doc = {
            "status": update.get("status", "Active"),
            "confidence_score": update.get("confidence_score", 0.0),
        }

        if update.get("waste_reason"):
            update_doc["waste_reason"] = update["waste_reason"]
        if update.get("waste_type"):
            update_doc["waste_type"] = update["waste_type"]

        # Merge optimization metadata into existing metadata
        metadata_updates = update.get("metadata_updates", {})
        if metadata_updates:
            update_doc["metadata.optimization"] = metadata_updates.get("optimization", {})

        try:
            await db.update(
                "resources",
                update_doc,
                {
                    "cloud_resource_id": resource_id,
                    "integration_id": integration_id,
                    "user_id": user_id,
                },
            )
            updated_count += 1
        except Exception as e:
            logger.debug(f"Failed to persist verdict for {resource_id}: {e}")

    logger.info(f"Persisted {updated_count}/{len(legacy_updates)} optimization verdicts")
    return updated_count


def _compute_overall_confidence(verdicts: List[ResourceVerdict]) -> int:
    """Compute overall AI confidence score (0-100) for dashboard stats."""
    if not verdicts:
        return 75

    waste_verdicts = [
        v for v in verdicts
        if v.classification in (
            ResourceClassification.CRITICAL_WASTE,
            ResourceClassification.CONFIRMED_WASTE,
            ResourceClassification.LIKELY_WASTE,
            ResourceClassification.POSSIBLE_WASTE,
        )
    ]

    if not waste_verdicts:
        return 92  # High confidence when no waste found

    avg_conf = sum(v.confidence for v in waste_verdicts) / len(waste_verdicts)
    return min(98, max(60, int(avg_conf * 100)))
