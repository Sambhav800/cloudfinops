import asyncio
import json
from pathlib import Path

from app.bill_parser import parse_bill
from app.bill_parser.analyzer import (
    _AI_MODEL_CANDIDATES,
    analyze_arbitrage,
    generate_full_intelligence_report,
    normalize_full_intelligence_report,
)
from app.config import DEFAULT_GEMINI_FAST_MODEL, DEFAULT_GEMINI_FLASH_MODEL


def test_gemini_defaults_use_current_flash_model_ids():
    assert DEFAULT_GEMINI_FLASH_MODEL == "gemini-3.7-flash"
    assert DEFAULT_GEMINI_FAST_MODEL == "gemini-3.7-flash"
    deprecated_candidates = {
        "gemini-" + "3.1-flash-lite-preview",
        "gemini-3-" + "flash-lite-preview",
        "gemini-3-flash-preview",
    }
    assert deprecated_candidates.isdisjoint(_AI_MODEL_CANDIDATES)


def test_analyze_arbitrage_falls_back_when_gemini_times_out(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def _no_gemini_response(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.bill_parser.analyzer._generate_with_gemini", _no_gemini_response)

    result = asyncio.run(
        analyze_arbitrage(
            parsed_bill={"provider": "aws", "total_spend": 120.5},
            opportunities=[
                {
                    "category": "Compute",
                    "current_cloud": "AWS",
                    "current_cost": 120.5,
                    "recommended_cloud": "GCP",
                    "recommended_cost": 92.0,
                    "savings": 28.5,
                    "savings_pct": 23.6,
                }
            ],
        )
    )

    assert len(result) == 1
    assert result[0]["category"] == "Compute"
    assert result[0]["migration_risk"] in {"Low", "Medium", "High"}
    assert "reasoning" in result[0]
    assert result[0]["reasoning"]


def test_generate_full_intelligence_report_falls_back_when_gemini_times_out(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def _no_gemini_response(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.bill_parser.analyzer._generate_with_gemini", _no_gemini_response)

    report = asyncio.run(
        generate_full_intelligence_report(
            parsed_bill={
                "provider": "aws",
                "total_spend": 180.0,
                "currency": "USD",
                "by_category": {"Compute": 120.5, "Storage": 59.5},
                "raw_services": [{"service": "Amazon EC2", "cost": 120.5}],
            },
            opportunities=[
                {
                    "category": "Compute",
                    "current_cloud": "AWS",
                    "current_cost": 120.5,
                    "recommended_cloud": "GCP",
                    "recommended_cost": 92.0,
                    "savings": 28.5,
                    "savings_pct": 23.6,
                }
            ],
        )
    )

    assert report["headline"]
    assert report["waste_grade"] in {"A", "B", "C", "D", "F"}
    assert len(report["findings"]) >= 1
    assert report["quick_wins"] == []
    assert report["additional_savings_max"] == 0
    assert report["verification_status"] == "source_grounded_unverified_savings"
    assert report["roadmap"] == []


def test_generate_full_intelligence_report_retries_once_on_invalid_json(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    responses = [
        "not valid json",
        json.dumps(
            {
                "headline": "Retry worked",
                "waste_grade": "B",
                "waste_score": 18,
                "additional_savings_min": 20.0,
                "additional_savings_max": 35.0,
                "findings": [
                    {
                        "rank": 1,
                        "service": "Elastic Load Balancing",
                        "monthly_cost": 90.0,
                        "pct_of_bill": 50.0,
                        "severity": "high",
                        "title": "Load balancer footprint is oversized",
                        "what_we_found": "ELB is the top line item on the bill.",
                        "why_inefficient": "Too many edges are left running.",
                        "how_to_fix": ["Step 1", "Step 2", "Step 3"],
                        "actions": [
                            {
                                "name": "Consolidate ALBs",
                                "difficulty": "Easy",
                                "time_required": "1 day",
                                "monthly_saving_min": 20.0,
                                "monthly_saving_max": 35.0,
                                "risk": "Low",
                            }
                        ],
                        "keep": False,
                    }
                ],
                "quick_wins": [
                    {"action": "Consolidate ALBs", "time": "1 day", "saving": 35.0, "risk": "Low"}
                ],
                "roadmap": [
                    {
                        "phase": "Phase 1: Quick Wins",
                        "timeframe": "Week 1",
                        "actions": ["Consolidate ALBs"],
                        "expected_saving_min": 20.0,
                        "expected_saving_max": 35.0,
                    }
                ],
                "cross_cloud_comparison": [
                    {
                        "service": "Load Balancing",
                        "aws_current": 90.0,
                        "aws_optimised": 55.0,
                        "gcp": 57.0,
                        "azure": 60.0,
                    }
                ],
                "executive_summary": "Summary",
                "client_scripts": {
                    "opening": "Opening",
                    "explain_biggest_issue": "Explain",
                    "handle_objection": "Objection",
                    "closing": "Closing",
                },
                "implementation_timeline_days": 12,
                "confidence": "high",
                "benchmark_context": "Benchmark",
            }
        ),
    ]
    calls = []

    async def _sequence_gemini_response(*_args, **_kwargs):
        calls.append(_args[0])
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr("app.bill_parser.analyzer._generate_with_gemini", _sequence_gemini_response)

    report = asyncio.run(
        generate_full_intelligence_report(
            parsed_bill={
                "provider": "aws",
                "total_spend": 180.0,
                "currency": "USD",
                "by_category": {"Load Balancing": 90.0, "Database": 45.0},
                "raw_services": [
                    {"service": "Elastic Load Balancing", "cost": 90.0},
                    {"service": "Amazon RDS", "cost": 45.0},
                ],
            },
            opportunities=[],
        )
    )

    assert len(calls) == 2
    assert report["headline"] == "Retry worked"
    assert report["findings"][0]["service"] == "Elastic Load Balancing"


def _aws_pdf_bill_rows():
    return [
        {
            "service": "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux - $0.303 On Demand RHEL c5a.2xlarge 744 Hrs",
            "cost": 225.43,
            "source_line": "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux - $0.303 On Demand RHEL c5a.2xlarge 744 Hrs USD 225.43",
            "page": 2,
            "line_number": 10,
        },
        {
            "service": "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux - $0.635 On Demand RHEL r5.2xlarge 744 Hrs",
            "cost": 472.44,
            "source_line": "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux - $0.635 On Demand RHEL r5.2xlarge 744 Hrs USD 472.44",
            "page": 2,
            "line_number": 11,
        },
        {
            "service": "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux - $0.6352 On Demand RHEL r6i.2xlarge 744 Hrs",
            "cost": 472.59,
            "source_line": "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux - $0.6352 On Demand RHEL r6i.2xlarge 744 Hrs USD 472.59",
            "page": 2,
            "line_number": 12,
        },
        {
            "service": "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux - $1.098 On Demand RHEL c5a.8xlarge 744 Hrs",
            "cost": 816.91,
            "source_line": "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux - $1.098 On Demand RHEL c5a.8xlarge 744 Hrs USD 816.91",
            "page": 2,
            "line_number": 13,
        },
        {
            "service": "EBS - $0.114 GB-month of General Purpose SSD (gp2) provisioned storage - Asia Pacific 6,672 GB-Mo",
            "cost": 760.61,
            "source_line": "EBS - $0.114 GB-month of General Purpose SSD (gp2) provisioned storage - Asia Pacific 6,672 GB-Mo USD 760.61",
            "page": 3,
            "line_number": 7,
        },
        {
            "service": "EBS - $0.0912 GB-month of General Purpose (gp3) provisioned storage - Asia Pacific (Mumbai) 100 GB-Mo",
            "cost": 9.12,
            "source_line": "EBS - $0.0912 GB-month of General Purpose (gp3) provisioned storage - Asia Pacific (Mumbai) 100 GB-Mo USD 9.12",
            "page": 3,
            "line_number": 8,
        },
        {
            "service": "EBS - $0.051 GB-month of Throughput Optimized HDD (st1) provisioned storage - Asia Pacific 10,000 GB-Mo",
            "cost": 510.0,
            "source_line": "EBS - $0.051 GB-month of Throughput Optimized HDD (st1) provisioned storage - Asia Pacific 10,000 GB-Mo USD 510.00",
            "page": 3,
            "line_number": 9,
        },
        {
            "service": "EBS - $0.08 GB-month of Magnetic provisioned storage - Asia Pacific (Mumbai) 1,000 GB-Mo",
            "cost": 80.0,
            "source_line": "EBS - $0.08 GB-month of Magnetic provisioned storage - Asia Pacific (Mumbai) 1,000 GB-Mo USD 80.00",
            "page": 3,
            "line_number": 10,
        },
        {
            "service": "Amazon Virtual Private Cloud Public IPv4 Addresses - $0.005 Idle public IPv4 address 3,720 Hrs",
            "cost": 18.60,
            "source_line": "Amazon Virtual Private Cloud Public IPv4 Addresses - $0.005 Idle public IPv4 address 3,720 Hrs USD 18.60",
            "page": 4,
            "line_number": 4,
        },
    ]


def test_pdf_bill_report_builds_bill_line_rule_estimates_without_gemini(monkeypatch):
    calls = []

    async def _unexpected_gemini_call(*args, **kwargs):
        calls.append((args, kwargs))
        return json.dumps({"headline": "Fake savings", "findings": [], "quick_wins": []})

    monkeypatch.setattr("app.bill_parser.analyzer._generate_with_gemini", _unexpected_gemini_call)

    report = asyncio.run(
        generate_full_intelligence_report(
            parsed_bill={
                "provider": "aws",
                "total_spend": 4246.66,
                "currency": "USD",
                "source_format": "pdf",
                "source_parser": "pdf_invoice_parser",
                "source_metadata": {"bill_line_items": _aws_pdf_bill_rows()},
                "raw_services": _aws_pdf_bill_rows(),
                "by_category": {"Compute": 1987.37, "Storage": 1359.73, "Networking": 18.60},
            },
            opportunities=[],
        )
    )

    assert calls == []
    assert report["verification_status"] == "bill_line_rule_estimate"
    assert report["analysis_source"] == "deterministic_bill_line_rules"
    assert report["additional_savings_min"] == 1098.43
    assert report["additional_savings_max"] == 1197.80
    assert report["waste_grade"] != "A"
    assert report["implementation_timeline_days"] < 7

    findings_by_service = {finding["service"]: finding for finding in report["findings"]}
    rhel = findings_by_service["Always-on RHEL EC2 commitment coverage"]
    assert rhel["monthly_cost"] == 1987.37
    assert rhel["actions"][0]["monthly_saving_min"] == 596.21
    assert rhel["actions"][0]["monthly_saving_max"] == 695.58
    assert rhel["actions"][0]["savings_source"] == "market_estimate_requires_cost_explorer_validation"
    assert rhel["actions"][0]["validation_required"] is True
    assert len(rhel["actions"][0]["evidence_lines"]) == 4

    gp2 = findings_by_service["EBS gp2 to gp3 migration"]
    assert gp2["actions"][0]["monthly_saving_max"] == 152.12
    assert "6,672 GB-Mo x ($0.114 - $0.0912)" == gp2["actions"][0]["calculation"]

    idle_ipv4 = findings_by_service["Idle public IPv4 address release"]
    assert idle_ipv4["actions"][0]["monthly_saving_max"] == 18.60

    st1 = findings_by_service["EBS st1 to sc1 cold-HDD candidate"]
    assert st1["actions"][0]["monthly_saving_max"] == 331.50
    assert st1["actions"][0]["validation_required"] is True

    magnetic = findings_by_service["Legacy Magnetic EBS technical-debt risk"]
    assert magnetic["actions"][0]["monthly_saving_max"] == 0.0
    assert magnetic["actions"][0]["savings_source"] == "risk_flag_no_savings_claimed"


def test_uploaded_large_aws_pdf_gets_broad_bill_line_findings(monkeypatch):
    bill_path = Path("/Users/nishantjain/Downloads/aws_20260310_124907_69b0134393309.pdf")
    if not bill_path.exists():
        return

    calls = []

    async def _unexpected_gemini_call(*args, **kwargs):
        calls.append((args, kwargs))
        return json.dumps({"headline": "Fake savings", "findings": [], "quick_wins": []})

    monkeypatch.setattr("app.bill_parser.analyzer._generate_with_gemini", _unexpected_gemini_call)

    parsed = parse_bill(bill_path.read_bytes(), bill_path.name)
    report = asyncio.run(generate_full_intelligence_report(parsed, []))

    assert calls == []
    assert parsed["rows_parsed"] == 383
    assert parsed["total_spend"] == 13623.29
    assert report["verification_status"] == "bill_line_rule_estimate"
    assert report["waste_grade"] != "A"
    assert report["additional_savings_max"] > 3000
    assert report["implementation_timeline_days"] <= 3

    findings_by_service = {finding["service"]: finding for finding in report["findings"]}
    assert "Idle public IPv4 address release" in findings_by_service
    assert "S3 storage lifecycle and tiering review" in findings_by_service
    assert "RDS MySQL rightsize and reservation review" in findings_by_service
    assert "EC2 On-Demand compute coverage review" in findings_by_service
    assert "Data transfer and bandwidth routing review" in findings_by_service
    assert "EBS gp2 to gp3 migration" in findings_by_service
    assert findings_by_service["EBS gp2 to gp3 migration"]["actions"][0]["monthly_saving_max"] == 36.71


def test_pdf_without_bill_line_optimization_signals_stays_source_grounded(monkeypatch):
    calls = []

    async def _unexpected_gemini_call(*args, **kwargs):
        calls.append((args, kwargs))
        return json.dumps({"headline": "Fake savings", "findings": [], "quick_wins": []})

    monkeypatch.setattr("app.bill_parser.analyzer._generate_with_gemini", _unexpected_gemini_call)

    report = asyncio.run(
        generate_full_intelligence_report(
            parsed_bill={
                "provider": "aws",
                "total_spend": 120.5,
                "currency": "USD",
                "source_format": "pdf",
                "source_parser": "pdf_invoice_parser",
                "source_metadata": {"bill_line_items": [{"service": "Amazon EC2 data transfer", "cost": 120.5}]},
                "raw_services": [{"service": "Amazon EC2 data transfer", "cost": 120.5}],
                "by_category": {"Networking": 120.5},
            },
            opportunities=[],
        )
    )

    assert calls == []
    assert report["verification_status"] == "source_grounded_unverified_savings"
    assert report["additional_savings_max"] == 0
    assert report["quick_wins"] == []
    assert report["roadmap"] == []


def test_normalize_full_intelligence_report_recomputes_summary_and_backfills_missing_fields():
    parsed_bill = {
        "provider": "aws",
        "currency": "USD",
        "total_spend": 200.0,
        "existing_credits_and_savings": 25.0,
        "by_category": {
            "Compute": 120.0,
            "Database": 80.0,
        },
        "raw_services": [
            {"service": "Compute Engine Instance", "cost": 120.0},
            {"service": "SQL Database", "cost": 80.0},
        ],
    }

    normalized = asyncio.run(normalize_full_intelligence_report(
        {
            "headline": "Wrong headline but usable payload",
            "waste_grade": "A",
            "waste_score": 61,
            "existing_savings_active": -10.0,
            "additional_savings_min": 1.0,
            "additional_savings_max": 2.0,
            "findings": [
                {
                    "rank": 1,
                    "service": "Compute Engine Instance",
                    "monthly_cost": 120.0,
                    "pct_of_bill": 60.0,
                    "severity": "high",
                    "title": "Compute needs review",
                    "what_we_found": "Compute Engine Instance costs USD 120.00 on this bill.",
                    "why_inefficient": "It remains the biggest concentration in the bill.",
                    "how_to_fix": ["Step 1", "Step 2"],
                    "actions": [
                        {
                            "name": "Optimize Compute Engine Instance",
                            "difficulty": "Medium",
                            "time_required": "3 days",
                            "monthly_saving_min": 5.0,
                            "monthly_saving_max": 10.0,
                            "risk": "Low",
                            "validation_required": "false",
                        }
                    ],
                    "validation_required": "false",
                    "keep": False,
                }
            ],
            "quick_wins": [],
            "roadmap": [],
            "cross_cloud_comparison": [
                {
                    "service": "Compute",
                    "aws_current": 120.0,
                    "aws_optimised": 90.0,
                    "gcp": 90.0,
                    "azure": 90.0,
                }
            ],
            "executive_summary": "Summary",
            "client_scripts": {
                "opening": "Short",
                "explain_biggest_issue": "",
                "handle_objection": "No numbers here",
                "closing": "Tiny",
            },
            "implementation_timeline_days": 0,
            "confidence": "high",
            "benchmark_context": "",
        },
        parsed_bill,
        [],
    ))

    computed_min = round(
        sum(
            min(action["monthly_saving_min"] for action in finding["actions"])
            for finding in normalized["findings"]
            if not finding.get("keep") and finding["actions"]
        ),
        2,
    )
    computed_max = round(
        sum(
            max(action["monthly_saving_max"] for action in finding["actions"])
            for finding in normalized["findings"]
            if not finding.get("keep") and finding["actions"]
        ),
        2,
    )

    assert normalized["additional_savings_min"] == computed_min
    assert normalized["additional_savings_max"] == computed_max
    assert normalized["waste_grade"] == "D"
    assert normalized["existing_savings_active"] == 25.0
    assert any(finding["service"] == "SQL Database" for finding in normalized["findings"])
    assert any(finding["keep"] and finding["monthly_cost"] == 25.0 for finding in normalized["findings"])
    assert normalized["findings"][0]["validation_required"] is False
    assert normalized["findings"][0]["actions"][0]["validation_required"] is False
    assert all(len(script.strip()) > 50 for script in normalized["client_scripts"].values())
    assert all(any(char.isdigit() for char in script) for script in normalized["client_scripts"].values())
    for row in normalized["cross_cloud_comparison"]:
        values = [row["aws_current"], row["aws_optimised"], row["gcp"], row["azure"]]
        non_null = [value for value in values if value is not None]
        assert len(set(non_null)) > 1 or len(non_null) <= 1
