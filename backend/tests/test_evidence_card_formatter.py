"""
Unit tests for Evidence Card Formatter & Safety Clearance Logic.
"""

import unittest
from datetime import datetime, timedelta, timezone
from app.optimization.evidence_collector import EvidenceBundle, ProviderState, SignalName, SignalTimeSeries
from app.optimization.evidence_card_formatter import build_evidence_card
from app.optimization.evidence_card_schemas import RiskLevel, SignalStatus, VetoCheckStatus


class TestEvidenceCardFormatter(unittest.TestCase):

    def test_build_evidence_card_full_corroboration(self):
        rec_dict = {
            "id": "rec_test12345678901234567890",
            "resource_name": "prod-api-worker-01",
            "cloud_resource_id": "i-08a9f3b12c4",
            "provider": "aws",
            "resource_type": "AWS EC2 Instance",
            "action": "rightsize",
            "estimated_monthly_waste": 245.28,
            "estimated_monthly_savings": 122.64,
            "region": "us-east-1",
            "tags": {"environment": "production"},
        }

        cpu_ts = SignalTimeSeries(metric_name="cpu_avg", values=[2.1, 3.5, 4.0], mean=3.2, p95=7.8, max=12.0)
        cpu_ts.compute_statistics()

        evidence = EvidenceBundle(
            resource_id="i-08a9f3b12c4",
            cloud_resource_id="i-08a9f3b12c4",
            resource_name="prod-api-worker-01",
            provider="aws",
            resource_type="AWS EC2 Instance",
            signals={"cpu_avg": cpu_ts},
            tags={"environment": "production"},
            resource_age_days=114,
            provider_state=ProviderState.RUNNING,
            monthly_cost=245.28,
        )

        card = build_evidence_card(rec_dict, evidence)

        # 1. Summary
        self.assertEqual(card.recommendation_id, "rec_test12345678901234567890")
        self.assertEqual(card.resource_summary.resource_name, "prod-api-worker-01")
        self.assertEqual(card.resource_summary.provider, "aws")
        self.assertEqual(card.resource_summary.recommended_action, "rightsize")
        self.assertEqual(card.resource_summary.estimated_monthly_savings, 122.64)

        # 2. Corroborating signals
        self.assertIn("cpu", card.corroborating_signals)
        self.assertEqual(card.corroborating_signals["cpu"].status, SignalStatus.PASSED)
        self.assertIn("Avg 3.2%", card.corroborating_signals["cpu"].observed_display)

        # 3. Missing data warning for memory
        self.assertIn("memory", card.corroborating_signals)
        self.assertTrue(card.corroborating_signals["memory"].is_missing)
        self.assertGreater(len(card.missing_data_warnings), 0)
        self.assertTrue(any("Memory telemetry agent data unavailable" in w for w in card.missing_data_warnings))

        # 4. Safety clearance checks
        self.assertEqual(len(card.safety_clearance), 5)
        for item in card.safety_clearance:
            self.assertEqual(item.status, VetoCheckStatus.CLEARED)

        # 5. Risk level & why flagged
        self.assertEqual(card.risk_level, RiskLevel.LOW)
        self.assertTrue(
            "Why we flagged this" in card.why_flagged_explanation
            or "Flagged for rightsizing" in card.why_flagged_explanation
        )

    def test_build_evidence_card_dr_tag_veto(self):
        rec_dict = {
            "id": "rec_dr_test_123456789012345",
            "resource_name": "prod-db-disaster-recovery",
            "provider": "azure",
            "action": "stop",
            "tags": {"type": "disaster-recovery"},
        }

        evidence = EvidenceBundle(
            resource_id="vm-dr-01",
            provider="azure",
            resource_type="Azure Virtual Machine",
            resource_name="prod-db-disaster-recovery",
            tags={"type": "disaster-recovery"},
            resource_age_days=90,
        )

        card = build_evidence_card(rec_dict, evidence)

        dr_item = next(item for item in card.safety_clearance if item.check_key == "dr_tag")
        self.assertEqual(dr_item.status, VetoCheckStatus.VETOED)
        self.assertEqual(card.risk_level, RiskLevel.HIGH)
        self.assertIn("High Risk", card.risk_explanation)

    def test_build_evidence_card_asg_membership_veto(self):
        rec_dict = {
            "id": "rec_asg_test_123456789012345",
            "resource_name": "k8s-node-worker-abc",
            "provider": "aws",
            "action": "terminate",
            "tags": {"aws:autoscaling:groupName": "eks-worker-group-1"},
        }

        card = build_evidence_card(rec_dict)

        asg_item = next(item for item in card.safety_clearance if item.check_key == "asg_fleet")
        self.assertEqual(asg_item.status, VetoCheckStatus.VETOED)
        self.assertEqual(card.risk_level, RiskLevel.HIGH)

    def test_build_evidence_card_blue_green_veto(self):
        rec_dict = {
            "id": "rec_bg_test_1234567890123456",
            "resource_name": "app-server-green-v2",
            "provider": "aws",
            "action": "rightsize",
        }

        card = build_evidence_card(rec_dict)

        bg_item = next(item for item in card.safety_clearance if item.check_key == "blue_green")
        self.assertEqual(bg_item.status, VetoCheckStatus.VETOED)
        self.assertEqual(card.risk_level, RiskLevel.HIGH)

    def test_build_evidence_card_recent_state_change_veto(self):
        rec_dict = {
            "id": "rec_state_test_123456789012",
            "resource_name": "recently-rebooted-vm",
            "provider": "gcp",
            "action": "stop",
        }

        recent_change = datetime.now(timezone.utc) - timedelta(days=2)
        evidence = EvidenceBundle(
            resource_id="vm-recent-01",
            provider="gcp",
            resource_type="GCP Compute Engine",
            resource_name="recently-rebooted-vm",
            last_state_change=recent_change,
        )

        card = build_evidence_card(rec_dict, evidence)

        rec_item = next(item for item in card.safety_clearance if item.check_key == "recent_state_change")
        self.assertEqual(rec_item.status, VetoCheckStatus.VETOED)
        self.assertEqual(card.risk_level, RiskLevel.HIGH)

    def test_build_evidence_card_backup_tag_veto(self):
        rec_dict = {
            "id": "rec_backup_test_12345678901",
            "resource_name": "backup-replica-node",
            "provider": "aws",
            "action": "rightsize",
            "tags": {"backup-rotation": "daily-snapshot-src"},
        }

        card = build_evidence_card(rec_dict)

        backup_item = next(item for item in card.safety_clearance if item.check_key == "backup_replication")
        self.assertEqual(backup_item.status, VetoCheckStatus.VETOED)
        self.assertEqual(card.risk_level, RiskLevel.HIGH)

    def test_to_dict_serialization(self):
        rec_dict = {
            "id": "rec_dict_test_1234567890123",
            "resource_name": "simple-instance",
            "provider": "gcp",
            "action": "rightsize",
            "estimated_monthly_savings": 50.0,
        }

        card = build_evidence_card(rec_dict)
        serialized = card.to_dict()

        self.assertEqual(serialized["recommendation_id"], "rec_dict_test_1234567890123")
        self.assertEqual(serialized["resource_summary"]["provider"], "gcp")
        self.assertIsInstance(serialized["safety_clearance"], list)
        self.assertIsInstance(serialized["corroborating_signals"], dict)
        self.assertIn("risk_level", serialized)
        self.assertIn("why_flagged_explanation", serialized)


if __name__ == "__main__":
    unittest.main()
