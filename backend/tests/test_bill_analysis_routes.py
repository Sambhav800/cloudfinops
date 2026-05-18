from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.auth import ClerkUser, get_current_user
from app.db import get_db_client


def _build_text_pdf(lines: list[str]) -> bytes:
    content_lines = [
        "BT",
        "/F1 12 Tf",
        "72 720 Td",
    ]

    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index > 0:
            content_lines.append("0 -18 Td")
        content_lines.append(f"({escaped}) Tj")

    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\n"
            b"endobj\n"
        ),
        b"4 0 obj\n<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]

    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj

    xref_offset = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
    pdf += f"{xref_offset}\n%%EOF\n".encode("ascii")
    return pdf


class FakeBillAnalysisDB:
    def __init__(self):
        self.analyses = [
            {
                "id": "analysis-other-user",
                "user_id": "user-2",
                "status": "success",
                "source_type": "manual_upload",
                "filename": "other.pdf",
                "provider": "aws",
                "provider_detected": "AWS",
                "source_format": "pdf",
                "source_parser": "pdf_invoice_parser",
                "rows_parsed": 2,
                "total_analyzed_spend": 100.0,
                "total_potential_savings": 25.0,
                "currency": "USD",
                "spend_by_category": {"Compute": 100.0},
                "top_services": [{"service": "Amazon EC2", "cost": 100.0}],
                "discounts_applied": {"AWS": "0%", "GCP": "0%", "Azure": "0%"},
                "arbitrage_opportunities": [],
                "cloudfront_insights": None,
                "gpu_insights": None,
                "source_metadata": {},
                "created_at": "2026-03-21T08:00:00+00:00",
            }
        ]

    async def create_bill_analysis(self, analysis):
        row = dict(analysis)
        row.setdefault("id", f"analysis-{len(self.analyses) + 1}")
        row.setdefault("created_at", f"2026-03-21T09:0{len(self.analyses)}:00+00:00")
        self.analyses.append(row)
        return row

    async def get_bill_analyses(self, user_id, *, limit=10):
        rows = [row for row in self.analyses if row.get("user_id") == user_id]
        rows.sort(key=lambda row: row.get("created_at") or "", reverse=True)
        return rows[:limit]

    async def get_bill_analysis(self, user_id, analysis_id):
        return next(
            (
                row
                for row in self.analyses
                if row.get("user_id") == user_id and row.get("id") == analysis_id
            ),
            None,
        )

    async def get_latest_bill_analysis(self, user_id):
        rows = await self.get_bill_analyses(user_id, limit=1)
        return rows[0] if rows else None

    async def update(self, table, data, filters):
        assert table == "bill_analyses"
        updated = []
        for row in self.analyses:
            if all(row.get(key) == value for key, value in filters.items()):
                row.update(data)
                updated.append(row)
        return updated


def _build_client(fake_db: FakeBillAnalysisDB, user_id: str = "user-1") -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id=user_id)
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


async def _fake_fetch_cross_cloud_prices(*args, **kwargs):
    return [
        {
            "category": "Compute",
            "current_cloud": "AWS",
            "current_cost": 123.45,
            "recommended_cloud": "GCP",
            "recommended_cost": 98.0,
            "savings": 25.45,
            "savings_pct": 20.61,
            "reasoning": "Compute pricing is lower on the target provider.",
            "migration_risk": "Low",
            "migration_note": "Stateless workloads migrate cleanly.",
            "all_cloud_costs": {"AWS": 123.45, "GCP": 98.0, "Azure": 118.0},
        }
    ]


async def _fake_analyze_arbitrage(*args, opportunities, **kwargs):
    return opportunities


async def _fake_generate_executive_report(*args, **kwargs):
    return {
        "headline": "Compute is the largest opportunity.",
        "waste_grade": "C",
        "waste_score": 24,
        "waste_grade_explanation": "Grade C reflects a measurable but tractable waste problem.",
        "total_spend": 169.12,
        "existing_savings_active": 0.0,
        "additional_savings_min": 18.0,
        "additional_savings_max": 25.45,
        "optimised_bill_min": 143.67,
        "optimised_bill_max": 151.12,
        "annual_savings_min": 216.0,
        "annual_savings_max": 305.4,
        "reduction_pct_min": 11,
        "reduction_pct_max": 15,
        "findings": [
            {
                "rank": 1,
                "service": "Amazon EC2",
                "monthly_cost": 123.45,
                "pct_of_bill": 73.0,
                "severity": "high",
                "title": "Compute is carrying too much baseline cost",
                "what_we_found": "Amazon EC2 is consuming $123.45/month, which is the majority of this test bill.",
                "why_inefficient": "The baseline is too large for the observed spend profile.",
                "how_to_fix": [
                    "Step 1: Review instance sizing.",
                    "Step 2: Schedule non-production capacity.",
                    "Step 3: Re-run billing after cleanup.",
                ],
                "actions": [
                    {
                        "name": "Right-size EC2 baseline",
                        "difficulty": "Medium",
                        "time_required": "1 week",
                        "monthly_saving_min": 18.0,
                        "monthly_saving_max": 25.45,
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
                "saving": 25.45,
                "risk": "Low",
            }
        ],
        "roadmap": [
            {
                "phase": "Phase 1: Quick Wins",
                "timeframe": "Week 1",
                "actions": ["Right-size EC2 baseline"],
                "expected_saving_min": 18.0,
                "expected_saving_max": 25.45,
            }
        ],
        "cross_cloud_comparison": [
            {
                "service": "Compute",
                "aws_current": 123.45,
                "aws_optimised": 98.0,
                "gcp": 98.0,
                "azure": 118.0,
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


def test_upload_bill_persists_pdf_analysis_and_exposes_list_routes(monkeypatch):
    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _fake_fetch_cross_cloud_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _fake_analyze_arbitrage)
    monkeypatch.setattr("app.bill_parser.generate_full_intelligence_report", _fake_generate_executive_report)

    fake_db = FakeBillAnalysisDB()
    client = _build_client(fake_db)

    pdf_bytes = _build_text_pdf(
        [
            "Amazon Web Services Invoice",
            "Amazon Elastic Compute Cloud 123.45",
            "Amazon S3 45.67",
            "Grand Total 169.12",
        ]
    )

    upload_response = client.post(
        "/api/scan/upload-bill",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
        data={
            "aws_discount_pct": "12.5",
            "gcp_discount_pct": "5",
            "azure_discount_pct": "0",
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()
    assert payload["id"] == "analysis-2"
    assert payload["analysis_id"] == "analysis-2"
    assert payload["source_type"] == "manual_upload"
    assert payload["provider_detected"] == "AWS"
    assert payload["source_format"] == "pdf"
    assert payload["total_analyzed_spend"] == 169.12
    assert payload["total_potential_savings"] == 0.0
    assert "No optimization savings are claimed" in payload["executive_report"]["headline"]
    assert payload["executive_report"]["verification_status"] == "source_grounded_unverified_savings"
    assert payload["executive_report"]["additional_savings_max"] == 0.0
    assert payload["executive_report"]["quick_wins"] == []
    assert payload["discounts_applied"] == {"AWS": "12.5%", "GCP": "5.0%", "Azure": "0.0%"}
    assert fake_db.analyses[-1]["user_id"] == "user-1"
    assert "Amazon" in payload["executive_report"]["findings"][0]["service"]
    assert payload["source_metadata"]["report_contract_version"] == "2026-04-28-bill-line-rule-estimate-v5"
    assert fake_db.analyses[-1]["existing_credits_and_savings"] == 0.0
    assert fake_db.analyses[-1]["savings_amount"] == 0.0

    latest_response = client.get("/api/bill-analyses/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == "analysis-2"

    list_response = client.get("/api/bill-analyses", params={"limit": 5})
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert [item["id"] for item in list_payload["analyses"]] == ["analysis-2"]
    assert [item["analysis_id"] for item in list_payload["analyses"]] == ["analysis-2"]
    assert list_payload["analyses"][0]["top_categories"] == ["Compute", "Storage"]

    detail_response = client.get("/api/bill-analyses/analysis-2")
    assert detail_response.status_code == 200
    assert detail_response.json()["filename"] == "invoice.pdf"
    assert detail_response.json()["analysis_id"] == "analysis-2"


def test_bill_analysis_detail_enforces_user_ownership():
    client = _build_client(FakeBillAnalysisDB(), user_id="user-1")

    response = client.get("/api/bill-analyses/analysis-other-user")

    assert response.status_code == 404
    assert response.json()["detail"] == "Bill analysis not found"


def test_bill_analysis_routes_hide_legacy_invalid_pdf_records():
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.extend(
        [
            {
                "id": "analysis-legacy-bad",
                "user_id": "user-1",
                "status": "success",
                "source_type": "manual_upload",
                "filename": "bad.pdf",
                "provider": "aws",
                "provider_detected": "AWS",
                "source_format": "pdf",
                "source_parser": "pdf_invoice_parser",
                "rows_parsed": 1206,
                "total_analyzed_spend": 14545.31,
                "total_potential_savings": 496.35,
                "currency": "USD",
                "spend_by_category": {"Other": 13625.44, "Database": 648.6},
                "top_services": [
                    {"service": "Service provider Total in USD", "cost": 1731.58},
                    {"service": "Estimated grand total", "cost": 865.79},
                ],
                "discounts_applied": {"AWS": "0%", "GCP": "0%", "Azure": "0%"},
                "arbitrage_opportunities": [],
                "cloudfront_insights": None,
                "gpu_insights": None,
                "source_metadata": {},
                "created_at": "2026-03-22T03:40:00+00:00",
            },
            {
                "id": "analysis-valid-pdf",
                "user_id": "user-1",
                "status": "success",
                "source_type": "manual_upload",
                "filename": "good.pdf",
                "provider": "aws",
                "provider_detected": "AWS",
                "source_format": "pdf",
                "source_parser": "pdf_invoice_parser",
                "rows_parsed": 82,
                "total_analyzed_spend": 865.79,
                "total_potential_savings": 25.0,
                "currency": "USD",
                "spend_by_category": {
                    "Load Balancing": 209.2,
                    "Database": 171.59,
                    "Networking": 145.17,
                    "Compute": 83.12,
                },
                "top_services": [
                    {"service": "Elastic Load Balancing", "cost": 209.2},
                ],
                "discounts_applied": {"AWS": "0%", "GCP": "0%", "Azure": "0%"},
                "arbitrage_opportunities": [],
                "cloudfront_insights": None,
                "gpu_insights": None,
                "source_metadata": {"pdf_parser_version": "2026-03-22-rollup-fix"},
                "created_at": "2026-03-22T04:00:00+00:00",
            },
        ]
    )
    client = _build_client(fake_db, user_id="user-1")

    list_response = client.get("/api/bill-analyses", params={"limit": 5})
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["analyses"]] == ["analysis-valid-pdf"]

    latest_response = client.get("/api/bill-analyses/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == "analysis-valid-pdf"

    detail_response = client.get("/api/bill-analyses/analysis-legacy-bad")
    assert detail_response.status_code == 404


def test_bill_analysis_detail_backfills_executive_report_when_missing():
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-missing-report",
            "user_id": "user-1",
            "status": "success",
            "source_type": "manual_upload",
            "filename": "good.pdf",
            "provider": "aws",
            "provider_detected": "AWS",
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "rows_parsed": 82,
            "total_analyzed_spend": 865.79,
            "total_potential_savings": 35.0,
            "currency": "USD",
            "spend_by_category": {
                "Load Balancing": 209.2,
                "Database": 171.59,
                "Networking": 145.17,
                "Compute": 83.12,
            },
            "top_services": [
                {"service": "Elastic Load Balancing", "cost": 209.2},
                {"service": "Relational Database Service", "cost": 171.59},
                {"service": "Virtual Private Cloud", "cost": 145.17},
            ],
            "discounts_applied": {"AWS": "0%", "GCP": "0%", "Azure": "0%"},
            "arbitrage_opportunities": [],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_metadata": {
                "pdf_parser_version": "2026-03-22-rollup-fix",
                "existing_credits_and_savings": 206.08,
            },
            "created_at": "2026-03-22T04:00:00+00:00",
        }
    )
    client = _build_client(fake_db, user_id="user-1")

    detail_response = client.get("/api/bill-analyses/analysis-missing-report")

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["executive_report"]["headline"]
    assert payload["executive_report"]["additional_savings_max"] == 0.0
    assert payload["executive_report"]["verification_status"] == "source_grounded_unverified_savings"
    assert len(payload["executive_report"]["findings"]) >= 3
    assert fake_db.analyses[1]["executive_report"]["headline"]
    assert payload["executive_report"]["existing_savings_active"] == 206.08
    assert fake_db.analyses[1]["existing_credits_and_savings"] == 206.08
    assert fake_db.analyses[1]["savings_amount"] == 206.08
    assert fake_db.analyses[1]["source_metadata"]["report_contract_version"] == "2026-04-28-bill-line-rule-estimate-v5"


def test_bill_analysis_list_backfills_executive_report_when_missing():
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-list-missing-report",
            "user_id": "user-1",
            "status": "success",
            "source_type": "manual_upload",
            "filename": "good.pdf",
            "provider": "aws",
            "provider_detected": "AWS",
            "source_format": "pdf",
            "source_parser": "pdf_invoice_parser",
            "rows_parsed": 82,
            "total_analyzed_spend": 865.79,
            "total_potential_savings": 35.0,
            "currency": "USD",
            "spend_by_category": {
                "Load Balancing": 209.2,
                "Database": 171.59,
                "Networking": 145.17,
                "Compute": 83.12,
            },
            "top_services": [
                {"service": "Elastic Load Balancing", "cost": 209.2},
                {"service": "Relational Database Service", "cost": 171.59},
                {"service": "Virtual Private Cloud", "cost": 145.17},
            ],
            "discounts_applied": {"AWS": "0%", "GCP": "0%", "Azure": "0%"},
            "arbitrage_opportunities": [],
            "cloudfront_insights": None,
            "gpu_insights": None,
            "source_metadata": {
                "pdf_parser_version": "2026-03-22-rollup-fix",
                "existing_credits_and_savings": 206.08,
            },
            "created_at": "2026-03-22T05:00:00+00:00",
        }
    )
    client = _build_client(fake_db, user_id="user-1")

    list_response = client.get("/api/bill-analyses", params={"limit": 5})

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["analyses"][0]["id"] == "analysis-list-missing-report"
    assert payload["analyses"][0]["executive_report"]["headline"]
    assert len(payload["analyses"][0]["executive_report"]["findings"]) >= 3
    assert fake_db.analyses[1]["executive_report"]["headline"]
    assert payload["analyses"][0]["executive_report"]["existing_savings_active"] == 206.08
    assert fake_db.analyses[1]["existing_credits_and_savings"] == 206.08


def test_bill_analysis_source_file_returns_user_owned_archived_bill(monkeypatch):
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-with-source-file",
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
            "source_metadata": {
                "raw_bill_file": {
                    "storage_provider": "gcs",
                    "status": "stored",
                    "original_filename": "invoice.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 1024,
                    "sha256": "abc123",
                    "bucket": "cloudfinops-bill-uploads",
                    "object_path": "bill-uploads/user-1/invoice.pdf",
                }
            },
            "created_at": "2026-03-22T05:00:00+00:00",
        }
    )
    client = _build_client(fake_db, user_id="user-1")

    async def _fake_download_archived_bill_from_gcs(raw_file_metadata):
        assert raw_file_metadata["status"] == "stored"
        return b"%PDF-1.4 archived", "application/pdf", "invoice.pdf"

    monkeypatch.setattr(
        "app.api.routes.download_archived_bill_from_gcs",
        _fake_download_archived_bill_from_gcs,
    )

    response = client.get("/api/bill-analyses/analysis-with-source-file/source-file")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 archived"
    assert response.headers["content-type"].startswith("application/pdf")
    assert 'filename="invoice.pdf"' in response.headers["content-disposition"]


def test_bill_analysis_source_file_returns_404_when_raw_file_is_missing():
    fake_db = FakeBillAnalysisDB()
    fake_db.analyses.append(
        {
            "id": "analysis-without-source-file",
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
            "source_metadata": {},
            "created_at": "2026-03-22T05:00:00+00:00",
        }
    )
    client = _build_client(fake_db, user_id="user-1")

    response = client.get("/api/bill-analyses/analysis-without-source-file/source-file")

    assert response.status_code == 404
    assert response.json()["detail"] == "Raw bill file is not available for this analysis"
