from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import time

from app.api.routes import _build_bill_analysis_record, router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


class FakeBillAnalysisDB:
    def __init__(self):
        self.analyses = []
        self.user_features = []

    async def create_bill_analysis(self, analysis):
        row = {
            "id": f"analysis-{len(self.analyses) + 1}",
            "created_at": "2026-03-21T10:00:00+00:00",
            **analysis,
        }
        self.analyses.append(row)
        return row

    async def get_latest_bill_analysis(self, user_id):
        matches = [row for row in self.analyses if row.get("user_id") == user_id]
        return matches[-1] if matches else None

    async def get_bill_analyses(self, user_id, *, limit=10):
        matches = [row for row in self.analyses if row.get("user_id") == user_id]
        matches.sort(key=lambda row: row.get("created_at") or "", reverse=True)
        return matches[:limit]

    async def get_bill_analysis(self, user_id, analysis_id):
        for row in self.analyses:
            if row.get("user_id") == user_id and row.get("id") == analysis_id:
                return row
        return None

    async def mark_user_feature_enabled(self, user_id, feature, *, last_used=None, first_upload_at=None):
        for row in self.user_features:
            if row.get("user_id") == user_id and row.get("feature") == feature:
                row["enabled"] = True
                row["last_used"] = last_used
                row["first_upload_at"] = row.get("first_upload_at") or first_upload_at or last_used
                return row

        row = {
            "id": f"feature-{len(self.user_features) + 1}",
            "user_id": user_id,
            "feature": feature,
            "enabled": True,
            "last_used": last_used,
            "first_upload_at": first_upload_at or last_used,
        }
        self.user_features.append(row)
        return row

    async def get_user_features(self, user_id):
        return [row for row in self.user_features if row.get("user_id") == user_id and row.get("enabled")]

    async def update(self, table, data, filters):
        assert table == "bill_analyses"
        updated = []
        for row in self.analyses:
            if all(row.get(key) == value for key, value in filters.items()):
                row.update(data)
                updated.append(row)
        return updated


def _build_client(fake_db: FakeBillAnalysisDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


@pytest.fixture(autouse=True)
def _stub_gemini_direct_bill_extraction(monkeypatch):
    async def _identity(parsed, content, filename, *, content_type=None):
        return parsed

    async def _no_extraction(content, filename, *, content_type=None):
        return None

    monkeypatch.setattr("app.bill_parser.enrich_parsed_bill_with_gemini", _identity)
    monkeypatch.setattr("app.bill_parser.extract_bill_with_gemini", _no_extraction)


def test_bill_analysis_record_preserves_all_service_rows():
    parsed = {
        "provider": "aws",
        "rows_parsed": 30,
        "total_spend": 465.0,
        "currency": "USD",
        "by_category": {"Other": 465.0},
        "raw_services": [
            {"service": f"Custom Service {index}", "cost": float(index + 1)}
            for index in range(30)
        ],
        "source_format": "csv",
        "source_parser": "pandas_csv_utf-8",
        "source_metadata": {},
    }

    record = _build_bill_analysis_record(
        filename="aws-large-bill.csv",
        parsed=parsed,
        opportunities=[],
        total_savings=0.0,
        aws_discount_pct=0.0,
        gcp_discount_pct=0.0,
        azure_discount_pct=0.0,
        user_id="user-1",
        executive_report=None,
        content_hash="hash",
    )

    assert len(record["top_services"]) == 30
    assert record["top_services"][0] == {"service": "Custom Service 0", "cost": 1.0}
    assert record["top_services"][-1] == {"service": "Custom Service 29", "cost": 30.0}


def test_upload_bill_accepts_pdf_and_persists_analysis(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    client = _build_client(fake_db)

    monkeypatch.setattr(
        "app.bill_parser.parse_bill",
        lambda content, filename: {
            "provider": "aws",
            "rows_parsed": 3,
            "total_spend": 180.0,
            "currency": "USD",
            "by_category": {"Compute": 120.5, "Storage": 40.25, "CDN": 19.25},
            "raw_services": [
                {"service": "Amazon EC2", "cost": 120.5},
                {"service": "Amazon S3", "cost": 40.25},
                {"service": "CloudFront", "cost": 19.25},
            ],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "source_metadata": {"line_items_detected": 3, "extractors_used": ["internal_text_layer"]},
        },
    )

    async def _fake_fetch_cross_cloud_prices(**kwargs):
        return [
            {
                "category": "Compute",
                "current_cloud": "AWS",
                "current_cost": 120.5,
                "recommended_cloud": "GCP",
                "recommended_cost": 92.0,
                "savings": 28.5,
                "savings_pct": 23.65,
            }
        ]

    async def _fake_analyze_arbitrage(**kwargs):
        return [
            {
                "category": "Compute",
                "current_cloud": "AWS",
                "current_cost": 120.5,
                "recommended_cloud": "GCP",
                "recommended_cost": 92.0,
                "savings": 28.5,
                "savings_pct": 23.65,
                "reasoning": "Move steady compute to a lower blended cost footprint.",
                "migration_risk": "Low",
            }
        ]

    async def _fake_generate_executive_report(**kwargs):
        return {
            "headline": "Compute is the biggest bill driver.",
            "waste_grade": "C",
            "waste_score": 24,
            "waste_grade_explanation": "Grade C reflects a meaningful but manageable waste signal.",
            "total_spend": 180.0,
            "existing_savings_active": 0.0,
            "additional_savings_min": 20.0,
            "additional_savings_max": 28.5,
            "optimised_bill_min": 151.5,
            "optimised_bill_max": 160.0,
            "annual_savings_min": 240.0,
            "annual_savings_max": 342.0,
            "reduction_pct_min": 11,
            "reduction_pct_max": 16,
            "findings": [
                {
                    "rank": 1,
                    "service": "Amazon EC2",
                    "monthly_cost": 120.5,
                    "pct_of_bill": 66.9,
                    "severity": "high",
                    "title": "Compute is carrying the biggest cost signal",
                    "what_we_found": "Amazon EC2 is the dominant spend line in this sample bill.",
                    "why_inefficient": "Steady-state compute should be challenged first.",
                    "how_to_fix": ["Step 1", "Step 2", "Step 3"],
                    "actions": [
                        {
                            "name": "Right-size EC2 baseline",
                            "difficulty": "Medium",
                            "time_required": "1 week",
                            "monthly_saving_min": 20.0,
                            "monthly_saving_max": 28.5,
                            "risk": "Low",
                        }
                    ],
                    "keep": False,
                }
            ],
            "quick_wins": [
                {
                    "action": "Right-size EC2 baseline",
                    "time": "1 week",
                    "saving": 28.5,
                    "risk": "Low",
                }
            ],
            "roadmap": [
                {
                    "phase": "Phase 1: Quick Wins",
                    "timeframe": "Week 1",
                    "actions": ["Right-size EC2 baseline"],
                    "expected_saving_min": 20.0,
                    "expected_saving_max": 28.5,
                }
            ],
            "cross_cloud_comparison": [
                {
                    "service": "Compute",
                    "aws_current": 120.5,
                    "aws_optimised": 92.0,
                    "gcp": 92.0,
                    "azure": 110.0,
                }
            ],
            "executive_summary": "Summary",
            "client_scripts": {
                "opening": "Opening",
                "explain_biggest_issue": "Explain",
                "handle_objection": "Objection",
                "closing": "Closing",
            },
            "implementation_timeline_days": 14,
            "confidence": "high",
            "benchmark_context": "Waste is below the 27% benchmark.",
        }

    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _fake_fetch_cross_cloud_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _fake_analyze_arbitrage)
    monkeypatch.setattr("app.bill_parser.generate_full_intelligence_report", _fake_generate_executive_report)
    monkeypatch.setattr(
        "app.api.routes.archive_uploaded_bill_to_gcs",
        lambda **kwargs: __import__("asyncio").sleep(0, result={
            "storage_provider": "gcs",
            "status": "stored",
            "original_filename": kwargs["filename"],
            "content_type": kwargs["content_type"] or "application/pdf",
            "size_bytes": len(kwargs["content"]),
            "sha256": kwargs["content_hash"],
            "bucket": "cloudfinops-bill-uploads",
            "object_path": "bill-uploads/user-1/2026/04/16/test-invoice.pdf",
            "stored_at": "2026-04-16T10:00:00+00:00",
        }),
    )

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={
            "aws_discount_pct": "5",
            "gcp_discount_pct": "7.5",
            "azure_discount_pct": "0",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "analysis-1"
    assert payload["analysis_id"] == "analysis-1"
    assert payload["filename"] == "invoice.pdf"
    assert payload["provider"] == "aws"
    assert payload["provider_detected"] == "AWS"
    assert payload["source_format"] == "pdf"
    assert payload["rows_parsed"] == 3
    assert payload["total_analyzed_spend"] == 180.0
    assert payload["total_potential_savings"] == 0.0
    assert payload["executive_report"]["verification_status"] == "source_grounded_unverified_savings"
    assert payload["executive_report"]["additional_savings_max"] == 0.0
    assert payload["executive_report"]["quick_wins"] == []
    assert payload["discounts_applied"] == {
        "AWS": "5.0%",
        "GCP": "7.5%",
        "Azure": "0.0%",
    }
    assert payload["source_metadata"]["raw_bill_file"]["status"] == "stored"
    assert payload["source_metadata"]["raw_bill_file"]["bucket"] == "cloudfinops-bill-uploads"
    assert fake_db.analyses[0]["user_id"] == "user-1"
    assert fake_db.user_features[0]["feature"] == "bill_analysis"
    assert fake_db.user_features[0]["user_id"] == "user-1"


def test_upload_bill_uses_gemini_direct_extraction_when_parser_cannot_read_bill(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    client = _build_client(fake_db)

    def _raise_value_error(content, filename):
        raise ValueError("Could not detect bill service/cost columns.")

    async def _fake_extract_bill_with_gemini(content, filename, *, content_type=None):
        return {
            "provider": "aws",
            "rows_parsed": 24,
            "total_spend": 2400.0,
            "currency": "USD",
            "by_category": {"Compute": 1400.0, "Storage": 1000.0},
            "raw_services": [
                {"service": "Amazon EC2", "cost": 1400.0},
                {"service": "Amazon S3", "cost": 1000.0},
            ],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_format": "pdf",
            "source_parser": "gemini_3_flash_direct_file",
            "source_metadata": {
                "line_items_detected": 24,
                "gemini_direct_file": {
                    "status": "extracted",
                    "model": "gemini-3-flash-preview",
                    "service_rows_detected": 2,
                },
            },
        }

    async def _fake_fetch_cross_cloud_prices(**kwargs):
        return []

    async def _fake_analyze_arbitrage(**kwargs):
        return []

    async def _fake_generate_executive_report(**kwargs):
        return {
            "headline": "Gemini extracted the detailed bill.",
            "waste_grade": "B",
            "waste_score": 12,
            "waste_grade_explanation": "Limited waste signal.",
            "total_spend": 2400.0,
            "existing_savings_active": 0.0,
            "additional_savings_min": 0.0,
            "additional_savings_max": 0.0,
            "optimised_bill_min": 2400.0,
            "optimised_bill_max": 2400.0,
            "annual_savings_min": 0.0,
            "annual_savings_max": 0.0,
            "reduction_pct_min": 0,
            "reduction_pct_max": 0,
            "findings": [],
            "quick_wins": [],
            "roadmap": [],
            "cross_cloud_comparison": [],
            "executive_summary": "Summary",
            "client_scripts": {
                "opening": "Opening",
                "explain_biggest_issue": "Explain",
                "handle_objection": "Objection",
                "closing": "Closing",
            },
            "implementation_timeline_days": 7,
            "confidence": "medium",
            "benchmark_context": "Baseline",
        }

    monkeypatch.setattr("app.bill_parser.parse_bill", _raise_value_error)
    monkeypatch.setattr("app.bill_parser.extract_bill_with_gemini", _fake_extract_bill_with_gemini)
    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _fake_fetch_cross_cloud_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _fake_analyze_arbitrage)
    monkeypatch.setattr("app.bill_parser.generate_full_intelligence_report", _fake_generate_executive_report)
    monkeypatch.setattr(
        "app.api.routes.archive_uploaded_bill_to_gcs",
        lambda **kwargs: __import__("asyncio").sleep(0, result={
            "storage_provider": "gcs",
            "status": "credentials_unavailable",
            "original_filename": kwargs["filename"],
            "content_type": kwargs["content_type"] or "application/pdf",
            "size_bytes": len(kwargs["content"]),
            "sha256": kwargs["content_hash"],
        }),
    )

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 scanned", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_parser"] == "gemini_3_flash_direct_file"
    assert payload["rows_parsed"] == 24
    assert payload["total_analyzed_spend"] == 2400.0
    assert payload["source_metadata"]["gemini_direct_file"]["status"] == "extracted"
    assert fake_db.analyses[0]["top_services"] == [
        {"service": "Amazon EC2", "cost": 1400.0},
        {"service": "Amazon S3", "cost": 1000.0},
    ]


def test_upload_bill_uses_gemini_direct_extraction_when_parser_times_out(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    client = _build_client(fake_db)

    def _slow_parse_bill(content, filename):
        time.sleep(0.05)
        return {
            "provider": "aws",
            "rows_parsed": 1,
            "total_spend": 10.0,
            "currency": "USD",
            "by_category": {"Compute": 10.0},
            "raw_services": [{"service": "Amazon EC2", "cost": 10.0}],
        }

    async def _fake_extract_bill_with_gemini(content, filename, *, content_type=None):
        return {
            "provider": "aws",
            "rows_parsed": 12,
            "total_spend": 1200.0,
            "currency": "USD",
            "by_category": {"Compute": 1200.0},
            "raw_services": [{"service": "Amazon EC2", "cost": 1200.0}],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_format": "pdf",
            "source_parser": "gemini_3_flash_direct_file",
            "source_metadata": {
                "line_items_detected": 12,
                "gemini_direct_file": {"status": "extracted"},
            },
        }

    async def _fake_fetch_cross_cloud_prices(**kwargs):
        return []

    async def _fake_analyze_arbitrage(**kwargs):
        return []

    async def _fake_generate_executive_report(**kwargs):
        return {
            "headline": "Gemini recovered the timed out bill.",
            "waste_grade": "B",
            "waste_score": 10,
            "waste_grade_explanation": "Limited waste signal.",
            "total_spend": 1200.0,
            "existing_savings_active": 0.0,
            "additional_savings_min": 0.0,
            "additional_savings_max": 0.0,
            "optimised_bill_min": 1200.0,
            "optimised_bill_max": 1200.0,
            "annual_savings_min": 0.0,
            "annual_savings_max": 0.0,
            "reduction_pct_min": 0,
            "reduction_pct_max": 0,
            "findings": [],
            "quick_wins": [],
            "roadmap": [],
            "cross_cloud_comparison": [],
            "executive_summary": "Summary",
            "client_scripts": {
                "opening": "Opening",
                "explain_biggest_issue": "Explain",
                "handle_objection": "Objection",
                "closing": "Closing",
            },
            "implementation_timeline_days": 7,
            "confidence": "medium",
            "benchmark_context": "Baseline",
        }

    monkeypatch.setattr("app.bill_parser.parse_bill", _slow_parse_bill)
    monkeypatch.setattr("app.api.routes._BILL_PARSE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr("app.bill_parser.extract_bill_with_gemini", _fake_extract_bill_with_gemini)
    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _fake_fetch_cross_cloud_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _fake_analyze_arbitrage)
    monkeypatch.setattr("app.bill_parser.generate_full_intelligence_report", _fake_generate_executive_report)
    monkeypatch.setattr(
        "app.api.routes.archive_uploaded_bill_to_gcs",
        lambda **kwargs: __import__("asyncio").sleep(0, result={
            "storage_provider": "gcs",
            "status": "credentials_unavailable",
            "original_filename": kwargs["filename"],
            "content_type": kwargs["content_type"] or "application/pdf",
            "size_bytes": len(kwargs["content"]),
            "sha256": kwargs["content_hash"],
        }),
    )

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 scanned", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_parser"] == "gemini_3_flash_direct_file"
    assert payload["rows_parsed"] == 12
    assert payload["total_analyzed_spend"] == 1200.0


def test_upload_bill_persists_deterministic_executive_report_when_generation_fails(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    client = _build_client(fake_db)

    monkeypatch.setattr(
        "app.bill_parser.parse_bill",
        lambda content, filename: {
            "provider": "aws",
            "rows_parsed": 82,
            "total_spend": 865.79,
            "currency": "USD",
            "by_category": {
                "Load Balancing": 209.2,
                "Database": 171.59,
                "Networking": 145.17,
                "Compute": 83.12,
            },
            "raw_services": [
                {"service": "Elastic Load Balancing", "cost": 209.2},
                {"service": "Relational Database Service", "cost": 171.59},
                {"service": "Virtual Private Cloud", "cost": 145.17},
                {"service": "Elastic Compute Cloud", "cost": 83.12},
            ],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "source_metadata": {"line_items_detected": 82, "extractors_used": ["pdfplumber"], "pdf_parser_version": "2026-03-22-rollup-fix"},
        },
    )

    async def _fake_fetch_cross_cloud_prices(**kwargs):
        return [
            {
                "category": "Load Balancing",
                "current_cloud": "AWS",
                "current_cost": 209.2,
                "recommended_cloud": "GCP",
                "recommended_cost": 167.36,
                "savings": 41.84,
                "savings_pct": 20.0,
            }
        ]

    async def _fake_analyze_arbitrage(**kwargs):
        return [
            {
                "category": "Load Balancing",
                "current_cloud": "AWS",
                "current_cost": 209.2,
                "recommended_cloud": "GCP",
                "recommended_cost": 167.36,
                "savings": 41.84,
                "savings_pct": 20.0,
                "reasoning": "Consolidate or right-size load balancers.",
                "migration_risk": "Low",
            }
        ]

    async def _raise_generate_full_intelligence_report(**kwargs):
        raise RuntimeError("Gemini unavailable")

    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _fake_fetch_cross_cloud_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _fake_analyze_arbitrage)
    monkeypatch.setattr("app.bill_parser.generate_full_intelligence_report", _raise_generate_full_intelligence_report)
    monkeypatch.setattr(
        "app.api.routes.archive_uploaded_bill_to_gcs",
        lambda **kwargs: __import__("asyncio").sleep(0, result={
            "storage_provider": "gcs",
            "status": "credentials_unavailable",
            "original_filename": kwargs["filename"],
            "content_type": kwargs["content_type"] or "application/pdf",
            "size_bytes": len(kwargs["content"]),
            "sha256": kwargs["content_hash"],
        }),
    )

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 test", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["executive_report"]["headline"]
    assert len(payload["executive_report"]["findings"]) >= 3
    assert payload["source_metadata"]["raw_bill_file"]["status"] == "credentials_unavailable"
    assert fake_db.analyses[0]["executive_report"]["headline"]
    assert fake_db.analyses[0]["executive_report"]["quick_wins"] == []
    assert fake_db.analyses[0]["executive_report"]["additional_savings_max"] == 0
    assert fake_db.analyses[0]["executive_report"]["verification_status"] == "source_grounded_unverified_savings"


def test_upload_bill_survives_raw_storage_failure_and_marks_analysis_metadata(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    client = _build_client(fake_db)

    monkeypatch.setattr(
        "app.bill_parser.parse_bill",
        lambda content, filename: {
            "provider": "aws",
            "rows_parsed": 1,
            "total_spend": 25.0,
            "currency": "USD",
            "by_category": {"Compute": 25.0},
            "raw_services": [{"service": "Amazon EC2", "cost": 25.0}],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "source_metadata": {"line_items_detected": 1},
        },
    )

    async def _fake_fetch_cross_cloud_prices(**kwargs):
        return []

    async def _fake_analyze_arbitrage(**kwargs):
        return []

    async def _fake_generate_executive_report(**kwargs):
        return {
            "headline": "No major repricing detected.",
            "waste_grade": "B",
            "waste_score": 12,
            "waste_grade_explanation": "Grade B reflects limited optimization headroom.",
            "total_spend": 25.0,
            "existing_savings_active": 0.0,
            "additional_savings_min": 0.0,
            "additional_savings_max": 0.0,
            "optimised_bill_min": 25.0,
            "optimised_bill_max": 25.0,
            "annual_savings_min": 0.0,
            "annual_savings_max": 0.0,
            "reduction_pct_min": 0,
            "reduction_pct_max": 0,
            "findings": [],
            "quick_wins": [],
            "roadmap": [],
            "cross_cloud_comparison": [],
            "executive_summary": "Summary",
            "client_scripts": {
                "opening": "Opening",
                "explain_biggest_issue": "Explain",
                "handle_objection": "Objection",
                "closing": "Closing",
            },
            "implementation_timeline_days": 7,
            "confidence": "medium",
            "benchmark_context": "Baseline",
        }

    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _fake_fetch_cross_cloud_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _fake_analyze_arbitrage)
    monkeypatch.setattr("app.bill_parser.generate_full_intelligence_report", _fake_generate_executive_report)
    monkeypatch.setattr(
        "app.api.routes.archive_uploaded_bill_to_gcs",
        lambda **kwargs: __import__("asyncio").sleep(0, result={
            "storage_provider": "gcs",
            "status": "failed",
            "original_filename": kwargs["filename"],
            "content_type": kwargs["content_type"] or "application/pdf",
            "size_bytes": len(kwargs["content"]),
            "sha256": kwargs["content_hash"],
            "bucket": "cloudfinops-bill-uploads",
            "object_path": "bill-uploads/user-1/failed-invoice.pdf",
        }),
    )

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 test", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_metadata"]["raw_bill_file"]["status"] == "failed"
    assert payload["source_metadata"]["raw_bill_file"]["object_path"] == "bill-uploads/user-1/failed-invoice.pdf"
    assert fake_db.analyses[0]["source_metadata"]["raw_bill_file"]["status"] == "failed"


def test_upload_bill_duplicate_recent_analysis_backfills_raw_file_metadata_before_reuse(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-existing",
            "user_id": "user-1",
            "status": "success",
            "source_type": "manual_upload",
            "filename": "invoice.pdf",
            "provider": "aws",
            "provider_detected": "AWS",
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "rows_parsed": 3,
            "total_analyzed_spend": 180.0,
            "total_potential_savings": 28.5,
            "currency": "USD",
            "spend_by_category": {"Compute": 120.5},
            "top_services": [{"service": "Amazon EC2", "cost": 120.5}],
            "discounts_applied": {"AWS": "5.0%", "GCP": "0.0%", "Azure": "0.0%"},
            "arbitrage_opportunities": [],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_metadata": {"content_hash": ""},
            "created_at": "2099-03-21T10:00:00+00:00",
        }
    )
    client = _build_client(fake_db)

    monkeypatch.setattr(
        "app.bill_parser.parse_bill",
        lambda content, filename: {
            "provider": "aws",
            "rows_parsed": 3,
            "total_spend": 180.0,
            "currency": "USD",
            "by_category": {"Compute": 120.5},
            "raw_services": [{"service": "Amazon EC2", "cost": 120.5}],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "source_metadata": {"line_items_detected": 3},
        },
    )
    monkeypatch.setattr(
        "app.api.routes.archive_uploaded_bill_to_gcs",
        lambda **kwargs: __import__("asyncio").sleep(0, result={
            "storage_provider": "gcs",
            "status": "stored",
            "original_filename": kwargs["filename"],
            "content_type": kwargs["content_type"] or "application/pdf",
            "size_bytes": len(kwargs["content"]),
            "sha256": kwargs["content_hash"],
            "bucket": "cloudfinops-bill-uploads",
            "object_path": "bill-uploads/user-1/reused-invoice.pdf",
            "stored_at": "2026-04-16T10:00:00+00:00",
        }),
    )

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 test", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "analysis-existing"
    assert payload["source_metadata"]["raw_bill_file"]["status"] == "stored"
    assert fake_db.analyses[-1]["source_metadata"]["raw_bill_file"]["object_path"] == "bill-uploads/user-1/reused-invoice.pdf"


def test_upload_bill_reprocesses_duplicate_when_current_parse_has_more_rows(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-existing",
            "user_id": "user-1",
            "status": "success",
            "source_type": "manual_upload",
            "filename": "invoice.pdf",
            "provider": "aws",
            "provider_detected": "AWS",
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "rows_parsed": 15,
            "total_analyzed_spend": 23.0,
            "total_potential_savings": 0.0,
            "currency": "USD",
            "spend_by_category": {"Compute": 23.0},
            "top_services": [
                {"service": f"Old row {index}", "cost": 1.0}
                for index in range(15)
            ],
            "discounts_applied": {"AWS": "0.0%", "GCP": "0.0%", "Azure": "0.0%"},
            "arbitrage_opportunities": [],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_metadata": {"content_hash": "", "line_items_detected": 15},
            "created_at": "2099-03-21T10:00:00+00:00",
        }
    )
    client = _build_client(fake_db)
    parsed_services = [
        {"service": f"Detailed AWS row {index}", "cost": 1.0}
        for index in range(23)
    ]

    monkeypatch.setattr(
        "app.bill_parser.parse_bill",
        lambda content, filename: {
            "provider": "aws",
            "rows_parsed": 23,
            "total_spend": 23.0,
            "currency": "USD",
            "by_category": {"Compute": 23.0},
            "raw_services": parsed_services,
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "source_metadata": {"line_items_detected": 23},
        },
    )

    async def _fake_fetch_cross_cloud_prices(**kwargs):
        return []

    async def _fake_analyze_arbitrage(**kwargs):
        return []

    async def _fake_generate_executive_report(**kwargs):
        return None

    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _fake_fetch_cross_cloud_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _fake_analyze_arbitrage)
    monkeypatch.setattr("app.bill_parser.generate_full_intelligence_report", _fake_generate_executive_report)
    monkeypatch.setattr(
        "app.api.routes.archive_uploaded_bill_to_gcs",
        lambda **kwargs: __import__("asyncio").sleep(0, result={
            "storage_provider": "gcs",
            "status": "stored",
            "original_filename": kwargs["filename"],
            "content_type": kwargs["content_type"] or "application/pdf",
            "size_bytes": len(kwargs["content"]),
            "sha256": kwargs["content_hash"],
            "bucket": "cloudfinops-bill-uploads",
            "object_path": "bill-uploads/user-1/richer-invoice.pdf",
            "stored_at": "2026-04-16T10:00:00+00:00",
        }),
    )

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 test", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "analysis-2"
    assert payload["rows_parsed"] == 23
    assert len(fake_db.analyses[-1]["top_services"]) == 23
    assert fake_db.analyses[-1]["top_services"][0]["service"] == "Detailed AWS row 0"


def test_get_latest_bill_analysis_repairs_stale_pdf_report_without_verified_savings():
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-stale",
            "user_id": "user-1",
            "status": "success",
            "source_type": "manual_upload",
            "filename": "aws.pdf",
            "provider": "aws",
            "provider_detected": "AWS",
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "rows_parsed": 23,
            "total_analyzed_spend": 4246.66,
            "total_potential_savings": 332.57,
            "currency": "USD",
            "spend_by_category": {"Compute": 816.91},
            "top_services": [{"service": "Amazon EC2", "cost": 816.91}],
            "discounts_applied": {"AWS": "0.0%", "GCP": "0.0%", "Azure": "0.0%"},
            "arbitrage_opportunities": [
                {
                    "category": "Compute",
                    "current_cloud": "AWS",
                    "current_cost": 816.91,
                    "recommended_cloud": "GCP",
                    "recommended_cost": 600.0,
                    "savings": 216.91,
                    "savings_pct": 26.6,
                }
            ],
            "executive_report": {
                "headline": "Amazon EC2 has recoverable savings.",
                "waste_grade": "A",
                "waste_score": 8,
                "waste_grade_explanation": "Validated savings.",
                "total_spend": 4246.66,
                "existing_savings_active": 0.0,
                "additional_savings_min": 0.0,
                "additional_savings_max": 332.57,
                "optimised_bill_min": 3914.09,
                "optimised_bill_max": 4246.66,
                "annual_savings_min": 0.0,
                "annual_savings_max": 3990.84,
                "reduction_pct_min": 0,
                "reduction_pct_max": 8,
                "findings": [],
                "quick_wins": [],
                "roadmap": [],
                "cross_cloud_comparison": [],
                "executive_summary": "Old report.",
                "client_scripts": {
                    "opening": "Opening",
                    "explain_biggest_issue": "Explain",
                    "handle_objection": "Handle",
                    "closing": "Close",
                },
                "implementation_timeline_days": 115,
                "confidence": "high",
                "benchmark_context": "Old benchmark.",
            },
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_metadata": {
                "line_items_detected": 23,
                "report_contract_version": "2026-03-23-executive-report-v2",
            },
            "created_at": "2026-03-21T10:00:00+00:00",
        }
    )
    client = _build_client(fake_db)

    response = client.get("/api/bill-analyses/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["executive_report"]["verification_status"] == "source_grounded_unverified_savings"
    assert payload["executive_report"]["additional_savings_max"] == 0.0
    assert payload["executive_report"]["quick_wins"] == []
    assert "No optimization savings are claimed" in payload["executive_report"]["headline"]
    assert fake_db.analyses[0]["executive_report"]["verification_status"] == "source_grounded_unverified_savings"


def test_get_latest_bill_analysis_reparses_archived_pdf_before_report_repair(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-archived-stale",
            "user_id": "user-1",
            "status": "success",
            "source_type": "manual_upload",
            "filename": "aws-large.pdf",
            "provider": "aws",
            "provider_detected": "AWS",
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "rows_parsed": 1,
            "total_analyzed_spend": 3254.01,
            "total_potential_savings": 0.02,
            "currency": "USD",
            "spend_by_category": {"Networking": 0.02},
            "top_services": [{"service": "Idle public IPv4 address", "cost": 0.02}],
            "discounts_applied": {"AWS": "0%", "GCP": "0%", "Azure": "0%"},
            "arbitrage_opportunities": [],
            "executive_report": {
                "headline": "Idle public IPv4 address release is the largest opportunity.",
                "waste_grade": "A",
                "waste_score": 8,
                "waste_grade_explanation": "Old report.",
                "total_spend": 3254.01,
                "existing_savings_active": 0.0,
                "additional_savings_min": 0.02,
                "additional_savings_max": 0.02,
                "optimised_bill_min": 3253.99,
                "optimised_bill_max": 3253.99,
                "annual_savings_min": 0.24,
                "annual_savings_max": 0.24,
                "reduction_pct_min": 0,
                "reduction_pct_max": 0,
                "findings": [],
                "quick_wins": [],
                "roadmap": [],
                "cross_cloud_comparison": [],
                "executive_summary": "Old report.",
                "client_scripts": {
                    "opening": "Opening",
                    "explain_biggest_issue": "Explain",
                    "handle_objection": "Handle",
                    "closing": "Close",
                },
                "implementation_timeline_days": 1,
                "confidence": "low",
                "benchmark_context": "Old benchmark.",
                "verification_status": "bill_line_rule_estimate",
            },
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_metadata": {
                "line_items_detected": 1,
                "report_contract_version": "2026-03-23-executive-report-v2",
                "raw_bill_file": {
                    "storage_provider": "gcs",
                    "status": "stored",
                    "original_filename": "aws-large.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 1200,
                    "sha256": "abc123",
                    "bucket": "cloudfinops-bill-uploads",
                    "object_path": "bill-uploads/user-1/aws-large.pdf",
                },
            },
            "created_at": "2026-03-21T10:00:00+00:00",
        }
    )
    client = _build_client(fake_db)

    async def _fake_download_archived_bill_from_gcs(raw_file_metadata):
        assert raw_file_metadata["status"] == "stored"
        return b"%PDF-1.4 archived", "application/pdf", "aws-large.pdf"

    def _fake_parse_bill(content, filename):
        assert content == b"%PDF-1.4 archived"
        assert filename == "aws-large.pdf"
        return {
            "provider": "aws",
            "rows_parsed": 383,
            "total_spend": 13623.29,
            "currency": "USD",
            "by_category": {"Storage": 3254.01},
            "raw_services": [
                {
                    "service": "Amazon Simple Storage Service S3 Standard Storage",
                    "cost": 3254.01,
                    "category": "Storage",
                    "page": 5,
                    "line_number": 42,
                    "line_type": "service_line",
                    "source_line": (
                        "Amazon Simple Storage Service S3 Standard Storage "
                        "$0.023 per GB-Mo 141,478.696 GB-Mo USD 3,254.01"
                    ),
                }
            ],
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "source_metadata": {
                "line_items_detected": 383,
                "pdf_parser_version": "2026-04-28-source-line-items",
            },
        }

    async def _identity_enrich(parsed, content, filename, *, content_type=None):
        return parsed

    monkeypatch.setattr(
        "app.api.routes.download_archived_bill_from_gcs",
        _fake_download_archived_bill_from_gcs,
    )
    monkeypatch.setattr("app.bill_parser.parse_bill", _fake_parse_bill)
    monkeypatch.setattr("app.bill_parser.enrich_parsed_bill_with_gemini", _identity_enrich)

    response = client.get("/api/bill-analyses/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows_parsed"] == 383
    assert payload["total_analyzed_spend"] == 13623.29
    assert payload["source_metadata"]["report_contract_version"] == "2026-04-28-bill-line-rule-estimate-v5"
    assert payload["executive_report"]["verification_status"] == "bill_line_rule_estimate"
    assert payload["executive_report"]["additional_savings_max"] == 1301.6
    assert payload["total_potential_savings"] == 1301.6
    assert payload["top_services"][0]["source_line"].startswith("Amazon Simple Storage Service")
    assert fake_db.analyses[0]["rows_parsed"] == 383


def test_upload_bill_maps_parser_value_error_to_422(monkeypatch):
    client = _build_client(FakeBillAnalysisDB())

    def _raise_value_error(content, filename):
        raise ValueError("Could not extract readable text from this PDF invoice")

    monkeypatch.setattr("app.bill_parser.parse_bill", _raise_value_error)

    async def _unused_fetch_cross_cloud_prices(**kwargs):
        raise AssertionError("pricing lookup should not run when parsing fails")

    async def _unused_analyze_arbitrage(**kwargs):
        raise AssertionError("arbitrage analysis should not run when parsing fails")

    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _unused_fetch_cross_cloud_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _unused_analyze_arbitrage)

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 broken", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Could not extract readable text from this PDF invoice"


def test_upload_bill_returns_504_when_pdf_parser_stalls(monkeypatch):
    client = _build_client(FakeBillAnalysisDB())

    def _slow_parse_bill(content, filename):
        time.sleep(0.05)
        return {
            "provider": "aws",
            "rows_parsed": 1,
            "total_spend": 10.0,
            "currency": "USD",
            "by_category": {"Compute": 10.0},
            "raw_services": [{"service": "Amazon EC2", "cost": 10.0}],
            "cloudfront_insights": None,
            "gpu_insights": None,
        }

    monkeypatch.setattr("app.bill_parser.parse_bill", _slow_parse_bill)
    monkeypatch.setattr("app.api.routes._BILL_PARSE_TIMEOUT_SECONDS", 0.01)

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", b"%PDF-1.4 test", "application/pdf")},
    )

    assert response.status_code == 504
    assert "Gemini direct extraction could not recover it" in response.json()["detail"]


def test_upload_bill_rejects_unsupported_extension():
    client = _build_client(FakeBillAnalysisDB())

    response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .csv, .xlsx, .xls, and .pdf files are supported."


def test_get_latest_bill_analysis_returns_user_owned_record():
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-9",
            "user_id": "user-1",
            "status": "success",
            "source_type": "manual_upload",
            "filename": "invoice.pdf",
            "provider": "aws",
            "provider_detected": "AWS",
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "rows_parsed": 3,
            "total_analyzed_spend": 180.0,
            "total_potential_savings": 28.5,
            "currency": "USD",
            "spend_by_category": {"Compute": 120.5},
            "top_services": [{"service": "Amazon EC2", "cost": 120.5}],
            "discounts_applied": {"AWS": "5.0%", "GCP": "7.5%", "Azure": "0.0%"},
            "arbitrage_opportunities": [],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_metadata": {"line_items_detected": 3},
            "created_at": "2026-03-21T10:00:00+00:00",
        }
    )
    client = _build_client(fake_db)

    response = client.get("/api/bill-analyses/latest")

    assert response.status_code == 200
    assert response.json()["id"] == "analysis-9"
    assert response.json()["analysis_id"] == "analysis-9"


def test_get_bill_analysis_enforces_user_owned_lookup():
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-10",
            "user_id": "user-2",
            "status": "success",
            "source_type": "manual_upload",
            "filename": "other.pdf",
            "provider": "aws",
            "provider_detected": "AWS",
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "rows_parsed": 1,
            "total_analyzed_spend": 10.0,
            "total_potential_savings": 0.0,
            "currency": "USD",
            "spend_by_category": {"Other": 10.0},
            "top_services": [{"service": "Other", "cost": 10.0}],
            "discounts_applied": {"AWS": "0.0%", "GCP": "0.0%", "Azure": "0.0%"},
            "arbitrage_opportunities": [],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_metadata": {},
            "created_at": "2026-03-21T10:00:00+00:00",
        }
    )
    client = _build_client(fake_db)

    response = client.get("/api/bill-analyses/analysis-10")

    assert response.status_code == 404
    assert response.json()["detail"] == "Bill analysis not found"


def test_get_user_features_returns_enabled_features():
    fake_db = FakeBillAnalysisDB()
    fake_db.user_features.extend(
        [
            {
                "id": "feature-1",
                "user_id": "user-1",
                "feature": "bill_analysis",
                "enabled": True,
                "last_used": "2026-03-22T09:00:00+00:00",
                "first_upload_at": "2026-03-20T09:00:00+00:00",
            },
            {
                "id": "feature-2",
                "user_id": "user-1",
                "feature": "beta_feature",
                "enabled": False,
                "last_used": "2026-03-22T09:00:00+00:00",
                "first_upload_at": "2026-03-20T09:00:00+00:00",
            },
        ]
    )
    client = _build_client(fake_db)

    response = client.get("/api/user/features")

    assert response.status_code == 200
    payload = response.json()
    assert payload["features"] == ["bill_analysis"]
    assert payload["feature_details"]["bill_analysis"]["first_upload_at"] == "2026-03-20T09:00:00+00:00"
